#!/bin/bash

# UVR API 本地停止脚本

echo "🛑 停止 UVR Audio Separation API 服务..."
echo ""

# 检查 PID 文件目录
if [ ! -d ".pids" ]; then
    echo "⚠️  未找到 .pids 目录，服务可能未运行"
    exit 0
fi

# 停止 API 服务器
if [ -f ".pids/api.pid" ]; then
    API_PID=$(cat .pids/api.pid)
    if ps -p $API_PID > /dev/null 2>&1; then
        echo "停止 API 服务器 (PID: $API_PID)..."
        kill $API_PID
        sleep 1
        # 如果进程还在运行，强制终止
        if ps -p $API_PID > /dev/null 2>&1; then
            kill -9 $API_PID
        fi
        echo "✓ API 服务器已停止"
    else
        echo "⚠️  API 服务器未运行"
    fi
    rm -f .pids/api.pid
fi

# 停止音频处理器
if [ -f ".pids/processor.pid" ]; then
    PROCESSOR_PID=$(cat .pids/processor.pid)
    if ps -p $PROCESSOR_PID > /dev/null 2>&1; then
        echo "停止音频处理器 (PID: $PROCESSOR_PID)..."
        kill $PROCESSOR_PID
        sleep 1
        if ps -p $PROCESSOR_PID > /dev/null 2>&1; then
            kill -9 $PROCESSOR_PID
        fi
        echo "✓ 音频处理器已停止"
    else
        echo "⚠️  音频处理器未运行"
    fi
    rm -f .pids/processor.pid
fi

# 停止 S3 上传器
if [ -f ".pids/uploader.pid" ]; then
    UPLOADER_PID=$(cat .pids/uploader.pid)
    if ps -p $UPLOADER_PID > /dev/null 2>&1; then
        echo "停止 S3 上传器 (PID: $UPLOADER_PID)..."
        kill $UPLOADER_PID
        sleep 1
        if ps -p $UPLOADER_PID > /dev/null 2>&1; then
            kill -9 $UPLOADER_PID
        fi
        echo "✓ S3 上传器已停止"
    else
        echo "⚠️  S3 上传器未运行"
    fi
    rm -f .pids/uploader.pid
fi

# 清理 PID 目录
rmdir .pids 2>/dev/null

echo ""
echo "✅ 所有服务已停止"
echo ""
echo "💡 提示："
echo "  - 重新启动: ./start_local.sh"
echo "  - 查看日志: tail -f logs/*.log"
echo ""
