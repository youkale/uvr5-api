#!/bin/bash

set -e

echo "🎵 Starting UVR Audio Separation API Service..."
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Using default configuration."
    echo "   Create a .env file with your configuration for production use."
    echo ""
fi

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Create necessary directories
mkdir -p temp output

echo "🚀 Starting services with Docker Compose..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service status
echo ""
echo "✅ Service status:"
docker-compose ps

echo ""
echo "📋 Service Information:"
echo "  API Server:    http://localhost:8000"
echo "  Health Check:  curl http://localhost:8000/health"
echo "  Auth:          Basic Auth (see .env for credentials)"
echo ""
echo "📖 View logs:"
echo "  All services:   docker-compose logs -f"
echo "  Redis:          docker-compose logs -f redis"
echo "  API only:       docker-compose logs -f api"
echo "  Processor:      docker-compose logs -f processor"
echo "  Uploader:       docker-compose logs -f uploader"
echo ""
echo "🔍 Redis CLI:"
echo "  docker exec -it uvr-redis redis-cli"
echo ""
echo "🛑 To stop:      ./stop.sh"
echo ""

# Follow logs
read -p "View logs now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose logs -f
fi
