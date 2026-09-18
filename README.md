# OpenList 目录树导出工具

通过 OpenList 的 HTTP API 扫描网盘目录，导出带层级线条的目录树文本。

## 功能

- 浏览器式文件夹选择（只显示文件夹，异步加载）
- 多路径合并输出到同一个 TXT，用分割线隔开
- 自动翻页、HTTP 重试、递归深度保护
- 默认输出到真实桌面，可一键打开输出文件夹
- 默认连接参数按 OpenList 官方文档设置（端口 5244，用户名 admin）

## 快速开始

### 方式一：下载 EXE（推荐新手）

1. 从 Releases 下载 `OpenList_Tree_Exporter_v1.0.zip`
2. 解压后双击 `setup.bat`
3. 填写你的 OpenList 密码，即可使用

### 方式二：使用 Python 脚本

```bash
# 1. 安装依赖
pip install httpx

# 2. 运行
python openlist_tree.py