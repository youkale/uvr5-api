#!/bin/bash

# UVR 模型下载脚本（Shell 包装器）

set -e

echo "🎵 UVR 模型下载工具"
echo "===================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python3"
    exit 1
fi

# 检查并安装 tqdm
if ! python3 -c "import tqdm" 2>/dev/null; then
    echo "📦 安装依赖: tqdm..."
    pip3 install tqdm
fi

# 检查并安装 requests
if ! python3 -c "import requests" 2>/dev/null; then
    echo "📦 安装依赖: requests..."
    pip3 install requests
fi

# 运行 Python 脚本
python3 download_models.py "$@"
