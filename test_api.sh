#!/bin/bash

# Test script for UVR API

API_URL="http://localhost:8000"
USERNAME="${BASIC_AUTH_USERNAME:-admin}"
PASSWORD="${BASIC_AUTH_PASSWORD:-password}"

echo "🧪 Testing UVR Audio Separation API"
echo "===================================="
echo ""

# Test 1: Health Check
echo "1️⃣  Testing health check..."
response=$(curl -s -w "\n%{http_code}" "$API_URL/health")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" -eq 200 ]; then
    echo "✅ Health check passed"
    echo "   Response: $body"
else
    echo "❌ Health check failed (HTTP $http_code)"
    echo "   Response: $body"
fi
echo ""

# Test 2: Unauthorized Access
echo "2️⃣  Testing unauthorized access..."
response=$(curl -s -w "\n%{http_code}" "$API_URL/generate" -X POST)
http_code=$(echo "$response" | tail -n1)

if [ "$http_code" -eq 401 ]; then
    echo "✅ Unauthorized access blocked correctly"
else
    echo "⚠️  Unexpected response (HTTP $http_code)"
fi
echo ""

# Test 3: Generate Request
echo "3️⃣  Testing audio separation request..."
response=$(curl -s -w "\n%{http_code}" -u "$USERNAME:$PASSWORD" \
    -X POST "$API_URL/generate" \
    -H "Content-Type: application/json" \
    -d '{
        "audio": "https://tts.luckyshort.net/seg_001.wav",
        "hook_url": "https://api.vibevibe.vip/webhook"
    }')

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" -eq 200 ]; then
    echo "✅ Request accepted"
    echo "   Response: $body"

    # Extract task_uuid
    task_uuid=$(echo "$body" | grep -o '"task_uuid":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$task_uuid" ]; then
        echo "   Task UUID: $task_uuid"
    fi
else
    echo "❌ Request failed (HTTP $http_code)"
    echo "   Response: $body"
fi
echo ""

echo "===================================="
echo "✨ Testing complete!"
echo ""
echo "📋 Check logs with: docker-compose logs -f"
