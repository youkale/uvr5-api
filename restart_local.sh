#!/bin/bash

# UVR API 本地重启脚本

echo "🔄 重启 UVR Audio Separation API 服务..."
echo ""

# 停止服务
./stop_local.sh

echo ""
echo "⏳ 等待 3 秒..."
sleep 3
echo ""

# 启动服务
./start_local.sh
