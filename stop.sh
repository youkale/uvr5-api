#!/bin/bash

set -e

echo "🛑 Stopping UVR Audio Separation API Service..."

docker-compose down

echo "✅ All services stopped successfully."
echo ""
echo "💡 To start again: ./start.sh"
echo "🧹 To clean volumes: docker-compose down -v"
