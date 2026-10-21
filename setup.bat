@echo off
chcp 65001 >nul
title OpenList 目录树导出工具 - 环境配置
echo ==========================================
echo   OpenList 目录树导出工具 - 一键配置
echo ==========================================
echo.

:: 1. 检测 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python。
    echo.
    echo 请先安装 Python 3.10 或更高版本：https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"。
    pause
    exit /b 1
)
echo [OK] 已检测到 Python：
python --version
echo.

:: 2. 安装依赖
echo [1/2] 正在安装依赖 httpx...
pip install httpx -q
if %errorlevel% neq 0 (
    echo [错误] httpx 安装失败，请检查网络或 pip 配置。
    pause
    exit /b 1
)
echo [OK] httpx 安装完成。
echo.

:: 3. 连接方式（本机 OpenList 在 8081，不是官方默认的 5244）
echo [2/3] 连接配置
if defined OPENLIST_TOKEN (
    echo [OK] 已检测到 OPENLIST_TOKEN，将用 token 免密登录。
) else (
    echo 未设置 OPENLIST_TOKEN。可以二选一：
    echo    A^) 直接启动，在界面里填管理员密码
    echo    B^) 先取 token 再启动（推荐）：
    echo       cd /d "C:\Users\Admin\openlist"
    echo       openlist.exe admin token
    echo       set OPENLIST_TOKEN=openlist-xxxx...
)
echo.
echo 默认地址：http://127.0.0.1:8081（可用 OPENLIST_URL 覆盖）
echo.

:: 4. 启动程序
echo [3/3] 正在启动 OpenList 目录树导出工具...
echo.
python openlist_tree.py
if %errorlevel% neq 0 (
    echo [错误] 程序启动失败。
    pause
    exit /b 1
)
