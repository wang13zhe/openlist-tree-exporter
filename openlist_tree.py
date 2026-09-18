#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenList 目录树导出工具

通过 OpenList 的 HTTP API 扫描网盘目录，导出带层级线条的目录树文本。
支持多路径合并输出、浏览器式文件夹选择、异步加载、自动翻页与重试。

依赖：httpx
    pip install httpx

默认连接参数（按 OpenList 官方文档设置）：
    地址：http://127.0.0.1:5244
    用户名：admin
    密码：（留空，请填写你自己的密码）

官方默认端口为 5244，如果你修改过 OpenList 的配置，请在此处相应修改。
"""

import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk, simpledialog

import httpx


# ========== 常量 ==========
STALL_TIMEOUT = 60
MAX_DEPTH = 50
PAGE_SIZE = 2000
RETRY_COUNT = 3
RETRY_DELAY = 1.5

WINDOW_W = 760
WINDOW_H = 780

BG = "#f4f6fb"
CARD = "#ffffff"
ACCENT = "#3b82f6"
ACCENT_DARK = "#2563eb"
SUCCESS = "#10b981"
DANGER = "#ef4444"
TEXT = "#1f2937"
SUBTEXT = "#6b7280"
BORDER = "#e5e7eb"
TEXT_BG = "#fbfcfe"
HIGHLIGHT = "#eef4ff"


def get_desktop_path():
    try:
        import ctypes
        CSIDL_DESKTOPDIRECTORY = 0x0010
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(
            None, CSIDL_DESKTOPDIRECTORY, None, 0, buf)
        if buf.value:
            return buf.value
    except Exception:
        pass
    return str(Path.home() / "Desktop")


def center_window(root, width, height):
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")


class TreeWriter:
    def __init__(self, filepath):
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "w", encoding="utf-8")
        self.lines = 0

    def write(self, line):
        self.f.write(line + "\n")
        self.lines += 1

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass


class OpenListClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.http = httpx.Client(
            timeout=30,
            limits=httpx.Limits(max_keepalive_connections=5,
                                max_connections=10),
        )

    def close(self):
        try:
            self.http.close()
        except Exception:
            pass

    def login(self, username, password):
        r = self.http.post(
            f"{self.base_url}/api/auth/login",
            json={"username": username, "password": password},
        )
        data = r.json()
        if data.get("code") != 200:
            raise Exception(f"登录失败：{data.get('message')}")
        self.token = data["data"]["token"]

    def _headers(self):
        return {"Authorization": self.token, "Content-Type": "application/json"}

    def _post_with_retry(self, endpoint, payload):
        last_err = None
        for i in range(RETRY_COUNT):
            try:
                r = self.http.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers=self._headers(),
                )
                return r.json()
            except Exception as e:
                last_err = e
                if i < RETRY_COUNT - 1:
                    time.sleep(RETRY_DELAY)
        raise last_err

    def list_dir(self, path):
        all_items = []
        page = 1
        while True:
            data = self._post_with_retry("/api/fs/list", {
                "path": path,
                "page": page,
                "per_page": PAGE_SIZE,
                "refresh": False,
                "password": "",
            })
            if data.get("code") != 200:
                raise Exception(data.get("message", "list failed"))
            content = (data.get("data") or {}).get("content") or []
            if not content:
                break
            all_items.extend(content)
            if len(content) < PAGE_SIZE:
                break
            page += 1
            if page > 200:
                break
        return all_items

    def list_folders(self, path):
        return [it for it in self.list_dir(path) if it.get("is_dir")]


def scan_openlist_tree(client, root_path, writer,
                       should_stop=None, on_progress=None,
                       stall_timeout=STALL_TIMEOUT):
    root_name = root_path.rstrip("/").split("/")[-1] or "root"
    writer.write(f"{root_name}/")
    count = 0
    last_tick = time.time()
    stalled = False

    def walk(path, prefix, depth):
        nonlocal count, last_tick, stalled
        if should_stop and should_stop():
            return False
        if depth > MAX_DEPTH:
            writer.write(f"{prefix}└── [已达最大深度 {MAX_DEPTH}，停止]")
            return True
        if time.time() - last_tick > stall_timeout:
            stalled = True
            writer.write(f"{prefix}[扫描卡顿超时，已中止]")
            return False
        try:
            entries = client.list_dir(path)
        except Exception as e:
            writer.write(f"{prefix}└── [无法访问: {type(e).__name__}]")
            last_tick = time.time()
            return True

        try:
            entries.sort(key=lambda e: (
                not e.get("is_dir", False),
                str(e.get("name", "")).lower()))
        except Exception:
            pass

        n = len(entries)
        for i, entry in enumerate(entries):
            if should_stop and should_stop():
                return False
            if time.time() - last_tick > stall_timeout:
                stalled = True
                writer.write(f"{prefix}[扫描卡顿超时，已中止]")
                return False
            count += 1
            last_tick = time.time()
            if on_progress and count % 50 == 0:
                on_progress(count)
            is_last = (i == n - 1)
            connector = "└── " if is_last else "├── "
            is_dir = bool(entry.get("is_dir", False))
            name = str(entry.get("name", "?"))
            writer.write(f"{prefix}{connector}{name}{'/' if is_dir else ''}")
            if is_dir:
                child = path.rstrip("/") + "/" + name
                if not walk(child,
                            prefix + ("    " if is_last else "│   "),
                            depth + 1):
                    return False
        return True

    ok = walk(root_path, "", 0)
    if on_progress:
        on_progress(count)
    if stalled:
        return "stalled", count
    if not ok:
        return "stopped", count
    return "done", count


class OpenListBrowser(tk.Toplevel):
    def __init__(self, parent, client):
        super().__init__(parent)
        self.client = client
        self.result = None
        self.title("浏览 OpenList 文件夹")
        self.configure(bg=BG)
        self.geometry("560x600")
        self.transient(parent)
        self.grab_set()
        center_window(self, 560, 600)

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=14, pady=(12, 6))
        ttk.Label(top, text="选择要扫描的文件夹（只显示文件夹）",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="点击 ▸ 展开，选中后点“确定”。双击也可确认。",
                  style="TLabel", foreground=SUBTEXT).pack(anchor="w")

        card = tk.Frame(self, bg=BORDER)
        card.pack(fill="both", expand=True, padx=14, pady=(4, 8))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        style = ttk.Style()
        style.configure("Browser.Treeview",
                        background=CARD, fieldbackground=CARD,
                        foreground=TEXT, rowheight=26,
                        font=("Microsoft YaHei UI", 10))

        self.tree = ttk.Treeview(inner, show="tree",
                                 style="Browser.Treeview",
                                 selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True,
                       padx=(4, 0), pady=4)
        sb = ttk.Scrollbar(inner, orient="vertical",
                           command=self.tree.yview)
        sb.pack(side="right", fill="y", pady=4, padx=(0, 4))
        self.tree.config(yscrollcommand=sb.set)

        self.root_id = self.tree.insert("", "end", text="/ (根目录)",
                                        values=["/"], open=False)
        self.tree.insert(self.root_id, "end",
                         text="加载中…", values=[None])

        self.tree.bind("<<TreeviewOpen>>", self._on_open)
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Return>", lambda e: self._ok())

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Button(bottom, text="📋 复制当前路径",
                   command=self._copy_current,
                   style="Ghost.TButton").pack(side="left")
        ttk.Button(bottom, text="确定",
                   command=self._ok,
                   style="Success.TButton").pack(side="right")
        ttk.Button(bottom, text="取消",
                   command=self.destroy,
                   style="Ghost.TButton").pack(side="right", padx=8)

        self.tree.selection_set(self.root_id)
        self.tree.focus(self.root_id)
        self.after(100, self._expand_root)

    def _expand_root(self):
        self.tree.item(self.root_id, open=True)
        self._on_open_item(self.root_id)

    def _on_double(self, event):
        self.after(50, self._ok)

    def _on_open(self, event):
        item = self.tree.focus()
        if not item:
            return
        self._on_open_item(item)

    def _on_open_item(self, node):
        children = self.tree.get_children(node)
        if len(children) == 1:
            first = children[0]
            if self.tree.item(first, "text") == "加载中…":
                vals = self.tree.item(node, "values")
                if not vals or not vals[0]:
                    return
                path = vals[0]
                self._load_children_async(node, path)

    def _load_children_async(self, node, path):
        def worker():
            try:
                folders = self.client.list_folders(path)
                err = None
            except Exception as e:
                folders = []
                err = str(e)
            self.after(0, lambda: self._apply_children(
                node, path, folders, err))
        threading.Thread(target=worker, daemon=True).start()

    def _apply_children(self, node, path, folders, err):
        for child in self.tree.get_children(node):
            if self.tree.item(child, "text") == "加载中…":
                self.tree.delete(child)
        if err:
            self.tree.insert(node, "end",
                             text=f"[无法访问: {err}]", values=[None])
            return
        if not folders:
            self.tree.insert(node, "end",
                             text="(无子文件夹)", values=[None])
            return
        folders.sort(key=lambda x: str(x.get("name", "")).lower())
        for it in folders:
            name = str(it.get("name", "?"))
            child_path = path.rstrip("/") + "/" + name
            cid = self.tree.insert(node, "end", text=name,
                                   values=[child_path])
            self.tree.insert(cid, "end", text="加载中…",
                             values=[None])

    def _copy_current(self):
        sel = self.tree.focus()
        if not sel:
            return
        vals = self.tree.item(sel, "values")
        if vals and vals[0]:
            self.clipboard_clear()
            self.clipboard_append(vals[0])
            tmp = tk.Toplevel(self)
            tmp.overrideredirect(True)
            tmp.attributes("-topmost", True)
            tk.Label(tmp, text="已复制", bg=SUCCESS, fg="white",
                     font=("Microsoft YaHei UI", 9),
                     padx=8, pady=4).pack()
            x = self.winfo_pointerx() + 10
            y = self.winfo_pointery() + 10
            tmp.geometry(f"+{x}+{y}")
            tmp.after(700, tmp.destroy)

    def _ok(self):
        sel = self.tree.focus()
        if not sel:
            self.result = None
            self.destroy()
            return
        vals = self.tree.item(sel, "values")
        if vals and vals[0]:
            self.result = vals[0]
        self.destroy()


class OpenListTreeApp:
    def __init__(self, root):
        self.root = root
        root.title("OpenList 目录树导出工具")
        root.configure(bg=BG)
        root.resizable(False, False)
        center_window(root, WINDOW_W, WINDOW_H)

        self.url_var = tk.StringVar(value="http://127.0.0.1:5244")
        self.user_var = tk.StringVar(value="admin")
        self.pass_var = tk.StringVar(value="")

        self.output_dir = tk.StringVar(value=get_desktop_path())
        self.last_output_dir = None

        self.status = tk.StringVar(
            value="先测试连接，再添加要扫描的 OpenList 路径，然后开始扫描。")
        self.stop_flag = False
        self.scanning = False

        self._client = None
        self._client_sig = None

        self._setup_style()
        self._build_ui()

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        if self._client:
            self._client.close()
        self.root.destroy()

    def _set_status(self, msg, kind="info"):
        color = {"info": SUBTEXT, "ok": SUCCESS, "err": DANGER}.get(kind, SUBTEXT)
        self.status_label.config(fg=color)
        self.status.set(msg)

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD, relief="flat")
        style.configure("TLabel", background=BG, foreground=TEXT,
                        font=("Microsoft YaHei UI", 10))
        style.configure("Card.TLabel", background=CARD, foreground=TEXT,
                        font=("Microsoft YaHei UI", 10))
        style.configure("Sub.TLabel", background=CARD, foreground=SUBTEXT,
                        font=("Microsoft YaHei UI", 9))
        style.configure("Title.TLabel", background=BG, foreground=TEXT,
                        font=("Microsoft YaHei UI", 15, "bold"))
        style.configure("Section.TLabel", background=CARD,
                        foreground=ACCENT_DARK,
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Accent.TButton",
                        background=ACCENT, foreground="white",
                        borderwidth=0, focusthickness=0, padding=(14, 8),
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton",
                  background=[("active", ACCENT_DARK),
                              ("disabled", "#a9c4f5")],
                  foreground=[("disabled", "#f0f4fc")])
        style.configure("Success.TButton",
                        background=SUCCESS, foreground="white",
                        borderwidth=0, focusthickness=0, padding=(14, 8),
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Success.TButton",
                  background=[("active", "#0ea572"),
                              ("disabled", "#a5e0cb")],
                  foreground=[("disabled", "#f0fcf7")])
        style.configure("Danger.TButton",
                        background=DANGER, foreground="white",
                        borderwidth=0, focusthickness=0, padding=(14, 8),
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Danger.TButton",
                  background=[("active", "#dc2626"),
                              ("disabled", "#f2b3b3")],
                  foreground=[("disabled", "#fdf2f2")])
        style.configure("Ghost.TButton",
                        background=CARD, foreground=ACCENT_DARK,
                        borderwidth=1, relief="solid", focusthickness=0,
                        padding=(12, 6),
                        font=("Microsoft YaHei UI", 9))
        style.map("Ghost.TButton",
                  background=[("active", HIGHLIGHT)],
                  bordercolor=[("!disabled", ACCENT)])
        style.configure("TEntry", fieldbackground=TEXT_BG,
                        bordercolor=BORDER, lightcolor=BORDER,
                        darkcolor=BORDER, foreground=TEXT, padding=6)
        style.configure("Blue.Horizontal.TProgressbar",
                        troughcolor="#e6ebf5", bordercolor=BG,
                        background=ACCENT, lightcolor=ACCENT,
                        darkcolor=ACCENT, thickness=8)

    def _card(self, parent, title):
        outer = tk.Frame(parent, bg=BORDER)
        outer.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        if title:
            ttk.Label(inner, text=title, style="Section.TLabel").pack(
                anchor="w", padx=14, pady=(12, 4))
        return inner

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=20, pady=(18, 10))
        ttk.Label(header, text="OpenList 目录树导出工具",
                  style="Title.TLabel").pack(anchor="w")
        ttk.Label(header,
                  text="通过 OpenList 的 HTTP API 扫描网盘目录，导出带层级线条的目录树文本",
                  style="TLabel", foreground=SUBTEXT).pack(anchor="w")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=20)

        conn_card = self._card(body, "OpenList 连接")
        row1 = tk.Frame(conn_card, bg=CARD)
        row1.pack(fill="x", padx=14, pady=(2, 6))
        ttk.Label(row1, text="地址", style="Card.TLabel",
                  width=6).pack(side="left")
        ttk.Entry(row1, textvariable=self.url_var).pack(
            side="left", fill="x", expand=True)
        row2 = tk.Frame(conn_card, bg=CARD)
        row2.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Label(row2, text="用户名", style="Card.TLabel",
                  width=6).pack(side="left")
        ttk.Entry(row2, textvariable=self.user_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Label(row2, text="密码", style="Card.TLabel",
                  width=5).pack(side="left")
        ttk.Entry(row2, textvariable=self.pass_var, show="*").pack(
            side="left", fill="x", expand=True)
        row3 = tk.Frame(conn_card, bg=CARD)
        row3.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Button(row3, text="🔌 测试连接 / 列出根挂载点",
                   command=self.test_connection,
                   style="Accent.TButton").pack(side="left")

        path_card = self._card(body, "扫描路径（OpenList 虚拟路径，每行一个）")
        list_frame = tk.Frame(path_card, bg=CARD)
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        self.paths_text = tk.Text(
            list_frame, height=6, wrap="none",
            font=("Consolas", 10), relief="flat",
            bg=TEXT_BG, fg=TEXT, insertbackground=ACCENT,
            selectbackground=HIGHLIGHT, selectforeground=TEXT,
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, padx=8, pady=6)
        self.paths_text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_frame, orient="vertical",
                           command=self.paths_text.yview)
        sb.pack(side="right", fill="y")
        self.paths_text.config(yscrollcommand=sb.set)

        btn_row = tk.Frame(path_card, bg=CARD)
        btn_row.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Button(btn_row, text="＋ 浏览并添加路径",
                   command=self.browse_add_path,
                   style="Accent.TButton").pack(side="left")
        ttk.Button(btn_row, text="手动输入",
                   command=self.manual_add_path,
                   style="Ghost.TButton").pack(side="left", padx=8)
        ttk.Button(btn_row, text="从根目录批量添加",
                   command=self.add_from_root,
                   style="Ghost.TButton").pack(side="left")
        ttk.Button(btn_row, text="清空列表",
                   command=self._clear_paths,
                   style="Ghost.TButton").pack(side="left", padx=8)

        out_card = self._card(body, "输出目录（本地）")
        out_frame = tk.Frame(out_card, bg=CARD)
        out_frame.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Entry(out_frame, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(out_frame, text="浏览…",
                   command=self.choose_output_dir,
                   style="Ghost.TButton").pack(side="left")
        out_row2 = tk.Frame(out_card, bg=CARD)
        out_row2.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Button(out_row2, text="📂 打开输出文件夹",
                   command=self.open_output_folder,
                   style="Accent.TButton").pack(side="left")

        act_card = self._card(body, None)
        act_row = tk.Frame(act_card, bg=CARD)
        act_row.pack(fill="x", padx=14, pady=12)
        self.start_btn = ttk.Button(act_row, text="▶ 开始扫描",
                                    command=self.start_scan,
                                    style="Success.TButton")
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(act_row, text="■ 停止",
                                   command=self.stop_scan,
                                   style="Danger.TButton",
                                   state="disabled")
        self.stop_btn.pack(side="left", padx=8)

        self.progress = ttk.Progressbar(
            act_card, mode="indeterminate",
            style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=14, pady=(0, 4))

        self.status_label = tk.Label(
            act_card, textvariable=self.status,
            bg=CARD, fg=SUBTEXT, anchor="w", justify="left",
            wraplength=WINDOW_W - 80,
            font=("Microsoft YaHei UI", 9))
        self.status_label.pack(fill="x", padx=14, pady=(0, 12))

    def _clear_paths(self):
        self.paths_text.delete("1.0", "end")

    def _append_path(self, d):
        content = self.paths_text.get("1.0", "end").strip()
        if content:
            self.paths_text.insert("end", "\n" + d)
        else:
            self.paths_text.insert("end", d)
        self.paths_text.see("end")

    def browse_add_path(self):
        client, ok = self._make_client()
        if not ok:
            return
        browser = OpenListBrowser(self.root, client)
        self.root.wait_window(browser)
        if browser.result:
            self._append_path(browser.result)
            self._set_status(f"✓ 已添加路径：{browser.result}", "ok")

    def manual_add_path(self):
        d = simpledialog.askstring(
            "手动输入 OpenList 路径",
            "输入要扫描的 OpenList 虚拟路径（例如 /123云盘/YZ-1）：",
            initialvalue="/")
        if not d:
            return
        d = d.strip()
        if not d.startswith("/"):
            d = "/" + d
        self._append_path(d)

    def add_from_root(self):
        client, ok = self._make_client()
        if not ok:
            return
        try:
            items = client.list_dir("/")
        except Exception as e:
            self._set_status(f"✗ 获取根目录失败：{e}", "err")
            return
        added = ["/" + it.get("name", "")
                 for it in items if it.get("is_dir")]
        if not added:
            self._set_status("根目录下没有文件夹。", "info")
            return
        self._append_path("\n".join(added))
        self._set_status(f"✓ 已添加 {len(added)} 个根挂载点。", "ok")

    def choose_output_dir(self):
        current = self.output_dir.get().strip()
        initial = current if current and Path(current).is_dir() else ""
        d = filedialog.askdirectory(title="选择输出目录", initialdir=initial)
        if d:
            self.output_dir.set(d)

    def open_output_folder(self):
        target = self.last_output_dir or self.output_dir.get().strip() \
            or get_desktop_path()
        if not Path(target).is_dir():
            self._set_status(f"✗ 文件夹不存在：{target}", "err")
            return
        try:
            os.startfile(target)
            self._set_status(f"✓ 已打开：{target}", "ok")
        except Exception as e:
            self._set_status(f"✗ 打开失败：{e}", "err")

    def _make_client(self):
        url = self.url_var.get().strip()
        user = self.user_var.get().strip()
        pwd = self.pass_var.get()
        if not url:
            self._set_status("✗ 请先填写 OpenList 地址。", "err")
            return None, False
        sig = (url, user, pwd)
        if self._client and self._client_sig == sig:
            return self._client, True
        if self._client:
            self._client.close()
        client = OpenListClient(url)
        try:
            client.login(user, pwd)
        except Exception as e:
            client.close()
            self._set_status(f"✗ {e}", "err")
            return None, False
        self._client = client
        self._client_sig = sig
        return client, True

    def test_connection(self):
        self._set_status("正在连接…", "info")
        self.root.update_idletasks()
        client, ok = self._make_client()
        if not ok:
            return
        try:
            items = client.list_dir("/")
        except Exception as e:
            self._set_status(f"✗ 连接成功但列目录失败：{e}", "err")
            return
        names = [it.get("name") for it in items if it.get("is_dir")]
        if names:
            self._set_status(
                f"✓ 连接成功。根目录下 {len(names)} 个挂载点："
                + "、".join(names[:8])
                + ("…" if len(names) > 8 else ""), "ok")
        else:
            self._set_status("✓ 连接成功。根目录为空。", "ok")

    def start_scan(self):
        if self.scanning:
            return
        raw = self.paths_text.get("1.0", "end").strip()
        paths = []
        for line in raw.splitlines():
            line = line.strip().strip('"').strip("'")
            if not line:
                continue
            if not line.startswith("/"):
                line = "/" + line
            paths.append(line)
        if not paths:
            self._set_status("⚠ 没有有效的 OpenList 路径，请先添加。", "err")
            return

        out = self.output_dir.get().strip() or get_desktop_path()
        self.output_dir.set(out)
        out_dir = Path(out)
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._set_status(f"⚠ 无法创建输出目录：{e}", "err")
            return

        client, ok = self._make_client()
        if not ok:
            return

        self.scanning = True
        self.stop_flag = False
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress.start(12)
        self._set_status(f"正在扫描 {len(paths)} 个路径…", "info")

        threading.Thread(
            target=self._scan_worker,
            args=(client, paths, out_dir),
            daemon=True).start()

    def stop_scan(self):
        if self.scanning:
            self.stop_flag = True
            self._set_status("正在停止…", "info")

    def _scan_worker(self, client, paths, out_dir):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = out_dir / f"OpenList_目录树_{stamp}.txt"
        results = []
        writer = None
        try:
            writer = TreeWriter(out_file)
            writer.f.write(f"# OpenList 目录树导出\n")
            writer.f.write(f"# OpenList：{client.base_url}\n")
            writer.f.write(
                f"# 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n")
            writer.f.write(f"# 共 {len(paths)} 个路径\n\n")

            for idx, path in enumerate(paths, 1):
                if self.stop_flag:
                    break
                if idx > 1:
                    writer.write("")
                    writer.write("=" * 72)
                    writer.write("")
                writer.write(f"# [{idx}/{len(paths)}] {path}")
                writer.write("")

                def progress_cb(n, name=path, i=idx, total=len(paths)):
                    self.root.after(0, lambda: self._set_status(
                        f"正在扫描 [{i}/{total}] {name}，已处理 {n} 项…",
                        "info"))

                try:
                    reason, count = scan_openlist_tree(
                        client, path, writer,
                        should_stop=lambda: self.stop_flag,
                        on_progress=progress_cb,
                    )
                    results.append((path, count, reason))
                except Exception as e:
                    writer.write(f"[扫描出错: {e}]")
                    results.append((path, 0, f"error:{e}"))
                writer.write("")

            writer.close()
            writer = None
            self.last_output_dir = str(out_dir)
            self.root.after(0, lambda: self._scan_done(results, out_file))
        except Exception as e:
            if writer:
                try:
                    writer.close()
                except Exception:
                    pass
            self.root.after(0, lambda e=e: self._scan_error(e))

    def _scan_done(self, results, out_file):
        self.scanning = False
        self.progress.stop()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

        if not results:
            self._set_status("未扫描任何路径。", "info")
            return

        total = sum(r[1] for r in results)
        ok_n = sum(1 for r in results if r[2] == "done")
        errs = [r for r in results if str(r[2]).startswith("error")]

        if errs:
            self._set_status(
                f"完成 {ok_n}/{len(results)}，共 {total} 项。"
                f"有 {len(errs)} 个失败：{errs[0][2]}", "err")
        else:
            self._set_status(
                f"✓ 完成：{ok_n}/{len(results)} 个路径，共 {total} 项。"
                f"输出文件：{out_file.name}", "ok")

    def _scan_error(self, e):
        self.scanning = False
        self.progress.stop()
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._set_status(f"✗ 出错：{e}", "err")


def main():
    root = tk.Tk()
    OpenListTreeApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())