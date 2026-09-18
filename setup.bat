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

:: 3. 启动程序
echo [2/2] 正在启动 OpenList 目录树导出工具...
echo.
python openlist_tree.py
if %errorlevel% neq 0 (
    echo [错误] 程序启动失败。
    pause
    exit /b 1
)