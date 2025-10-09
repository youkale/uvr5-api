#!/bin/bash

# UVR API 服务状态检查脚本

echo "📊 UVR Audio Separation API 服务状态"
echo "=================================================="
echo ""

# 检查 PID 文件目录
if [ ! -d ".pids" ]; then
    echo "❌ 服务未运行（未找到 .pids 目录）"
    echo ""
    echo "💡 启动服务: ./start_local.sh"
    exit 1
fi

RUNNING_COUNT=0
TOTAL_COUNT=3

# 检查 API 服务器
echo "1️⃣  API 服务器"
if [ -f ".pids/api.pid" ]; then
    API_PID=$(cat .pids/api.pid)
    if ps -p $API_PID > /dev/null 2>&1; then
        echo "   状态: ✅ 运行中"
        echo "   PID:  $API_PID"
        echo "   端口: 8000"
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    else
        echo "   状态: ❌ 已停止"
        echo "   PID:  $API_PID (进程不存在)"
    fi
else
    echo "   状态: ❌ 未启动（无 PID 文件）"
fi
echo ""

# 检查音频处理器
echo "2️⃣  音频处理器"
if [ -f ".pids/processor.pid" ]; then
    PROCESSOR_PID=$(cat .pids/processor.pid)
    if ps -p $PROCESSOR_PID > /dev/null 2>&1; then
        echo "   状态: ✅ 运行中"
        echo "   PID:  $PROCESSOR_PID"
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    else
        echo "   状态: ❌ 已停止"
        echo "   PID:  $PROCESSOR_PID (进程不存在)"
    fi
else
    echo "   状态: ❌ 未启动（无 PID 文件）"
fi
echo ""

# 检查 S3 上传器
echo "3️⃣  S3 上传器"
if [ -f ".pids/uploader.pid" ]; then
    UPLOADER_PID=$(cat .pids/uploader.pid)
    if ps -p $UPLOADER_PID > /dev/null 2>&1; then
        echo "   状态: ✅ 运行中"
        echo "   PID:  $UPLOADER_PID"
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    else
        echo "   状态: ❌ 已停止"
        echo "   PID:  $UPLOADER_PID (进程不存在)"
    fi
else
    echo "   状态: ❌ 未启动（无 PID 文件）"
fi
echo ""

echo "=================================================="
echo "总计: $RUNNING_COUNT/$TOTAL_COUNT 个服务运行中"
echo "=================================================="
echo ""

# 检查 API 可访问性
if [ $RUNNING_COUNT -gt 0 ]; then
    echo "🔗 测试 API 连接..."
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API 服务可访问"
    else
        echo "⚠️  API 服务无响应"
    fi
    echo ""
fi

echo "📋 快速操作："
echo "  查看日志:  tail -f logs/*.log"
echo "  停止服务:  ./stop_local.sh"
echo "  重启服务:  ./stop_local.sh && ./start_local.sh"
echo ""
