# OpenList 目录树导出工具

通过 OpenList 的 HTTP API 扫描网盘目录，导出带层级线条的目录树文本。

## 功能

- 浏览器式文件夹选择（只显示文件夹，异步加载）
- 多路径合并输出到同一个 TXT，用分割线隔开
- 自动翻页、HTTP 重试、递归深度保护
- 默认输出到真实桌面，可一键打开输出文件夹
- 默认连接参数按本机 OpenList 的实际配置预填（`http://127.0.0.1:8081`，用户名 `admin`）

## 连接配置（本机基准）

本机 OpenList 把 `http_port` 改成了 **8081**（不是官方默认的 5244），
配置见 `C:\Users\Admin\openlist\data\config.json`。程序默认值已按这个改好。

两种登录方式，任选其一：

### 方式 A：用户名 + 密码（GUI 里填）

地址和用户名已预填，只需在「密码」框里填 OpenList 管理员密码，点「测试连接」。

### 方式 B：管理员 token（推荐，不用知道密码）

```bash
# 1. 取 token（在 openlist.exe 所在目录执行）
cd C:\Users\Admin\openlist
.\openlist.exe admin token

# 2. 设为环境变量（当前 PowerShell 会话）
$env:OPENLIST_TOKEN = 'openlist-xxxx...'

# 3. 启动，程序会跳过登录直接调 API
python openlist_tree.py
```

token 就是 `Authorization` 头的值，**不带** `Bearer ` 前缀。
设置了 `OPENLIST_TOKEN` 时，地址和用户名密码框都不参与认证，程序用 `/api/me` 校验 token。

可用环境变量覆盖默认连接参数（换机器时不用改代码）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENLIST_URL` | `http://127.0.0.1:8081` | OpenList 地址 |
| `OPENLIST_USER` | `admin` | 用户名（密码登录时用） |
| `OPENLIST_TOKEN` | 空 | 设置后走 token 认证 |

## 快速开始

### 方式一：下载 EXE（推荐新手）

1. 从 Releases 下载 `OpenList_Tree_Exporter_v1.0.zip`
2. 解压后双击 `setup.bat`
3. 按上面「连接配置」填密码或设 token，即可使用

### 方式二：使用 Python 脚本

```bash
# 1. 安装依赖
pip install httpx

# 2. 运行
python openlist_tree.py
```

## 依赖

- `httpx`（`pip install httpx`）
- Python 3.10+（用到 f-string 与类型注解；本机实测 3.14.8）
