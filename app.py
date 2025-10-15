#!/usr/bin/env python3
"""
UVR Audio Separation API Server
Flask-based REST API with Basic Auth and Redis Priority Queue
"""

import os
import uuid
import time
import json
import logging
import requests
from flask import Flask, request, jsonify
from flask_httpauth import HTTPBasicAuth
import config
from redis_queue import create_redis_client, RedisPriorityQueue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
auth = HTTPBasicAuth()

# Initialize Redis client and task queue
redis_client = None
task_queue = None

def get_redis_queue():
    """Get or create Redis task queue"""
    global redis_client, task_queue
    if redis_client is None or task_queue is None:
        try:
            redis_client = create_redis_client(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                password=config.REDIS_PASSWORD
            )
            task_queue = RedisPriorityQueue(redis_client, config.REDIS_TASK_QUEUE)
            logger.info("Redis task queue initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis task queue: {str(e)}")
            raise
    return task_queue

@auth.verify_password
def verify_password(username, password):
    """Verify Basic Auth credentials"""
    if username == config.BASIC_AUTH_USERNAME and password == config.BASIC_AUTH_PASSWORD:
        return username
    return None

def download_audio(audio_url, task_uuid):
    """
    Download audio from URL to local temporary file
    在 API 阶段下载，提前发现错误
    """
    try:
        logger.info(f"[{task_uuid}] Downloading audio from URL: {audio_url}")

        # Create temp file in temp directory
        filename = f"{task_uuid}_input.wav"
        local_path = os.path.join(config.TEMP_DIR, filename)

        # Download the file
        response = requests.get(audio_url, timeout=30, stream=True)
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get('content-type', '')
        if not any(audio_type in content_type.lower() for audio_type in ['audio', 'wav', 'mp3', 'flac']):
            logger.warning(f"[{task_uuid}] Downloaded file may not be audio: {content_type}")

        # Save to local file
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"[{task_uuid}] Audio downloaded to: {local_path}")
        return local_path

    except Exception as e:
        logger.error(f"[{task_uuid}] Failed to download audio from URL {audio_url}: {e}")
        raise Exception(f"Failed to download audio: {str(e)}")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint - no auth required"""
    health_status = {
        "status": "healthy",
        "timestamp": int(time.time()),
        "components": {}
    }

    # Check Redis connection
    try:
        if redis_client:
            redis_client.ping()
            queue_size = task_queue.size() if task_queue else 0
            health_status['components']['redis'] = {
                'status': 'healthy',
                'task_queue_size': queue_size
            }
        else:
            health_status['components']['redis'] = {'status': 'not_initialized'}
    except Exception as e:
        health_status['status'] = 'degraded'
        health_status['components']['redis'] = {
            'status': 'unhealthy',
            'error': str(e)
        }

    return jsonify(health_status), 200

@app.route('/generate', methods=['POST'])
@auth.login_required
def generate():
    """
    Audio separation endpoint

    Request body:
    {
        "audio": "https://example.com/audio.wav",
        "hook_url": "https://example.com/callback",
        "priority": 3  // Optional: 1-5, default=3 (1=lowest, 5=highest)
    }

    Response:
    {
        "message": "Task has been queued for processing",
        "status": "queued",
        "task_uuid": "uuid-string",
        "priority": 3
    }
    """
    # Check request content type
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    # Get request data
    data = request.get_json()

    # Validate required fields
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    audio_url = data.get('audio')
    hook_url = data.get('hook_url')
    priority = data.get('priority', config.DEFAULT_PRIORITY)

    if not audio_url:
        return jsonify({"error": "audio field is required"}), 400

    if not hook_url:
        return jsonify({"error": "hook_url field is required"}), 400

    # Validate priority
    if not isinstance(priority, int) or priority < 1 or priority > 5:
        return jsonify({"error": "priority must be an integer between 1 and 5 (1=lowest, 5=highest)"}), 400

    # Validate URLs
    if not audio_url.startswith(('http://', 'https://')):
        return jsonify({"error": "audio must be a valid HTTP(S) URL"}), 400

    if not hook_url.startswith(('http://', 'https://')):
        return jsonify({"error": "hook_url must be a valid HTTP(S) URL"}), 400

    # Generate task UUID
    task_uuid = str(uuid.uuid4())

    # Download audio file (前置到 API 阶段)
    try:
        local_audio_path = download_audio(audio_url, task_uuid)
    except Exception as e:
        logger.error(f"[{task_uuid}] Download failed: {str(e)}")
        return jsonify({
            "error": "Failed to download audio file",
            "details": str(e)
        }), 400

    # Create task data (使用本地路径而不是 URL)
    task_data = {
        'task_uuid': task_uuid,
        'audio_path': local_audio_path,  # 改为本地路径
        'hook_url': hook_url,
        'priority': priority,
        'timestamp': int(time.time())
    }

    # Send to Redis priority queue
    try:
        queue = get_redis_queue()
        success = queue.enqueue(task_data, priority=priority)

        if not success:
            raise Exception("Failed to enqueue task")

        logger.info(f"Task {task_uuid} queued successfully with priority {priority}")

    except Exception as e:
        logger.error(f"Redis error for task {task_uuid}: {str(e)}")
        # Clean up downloaded file on failure
        if os.path.exists(local_audio_path):
            try:
                os.remove(local_audio_path)
            except Exception:
                pass
        return jsonify({"error": "Failed to queue task"}), 500

    # Return response
    return jsonify({
        "message": "Task has been queued for processing",
        "status": "queued",
        "task_uuid": task_uuid,
        "priority": priority
    }), 200

@app.errorhandler(401)
def unauthorized(error):
    """Handle unauthorized access"""
    return jsonify({"error": "Unauthorized access"}), 401

@app.errorhandler(404)
def not_found(error):
    """Handle not found errors"""
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500

def shutdown_handler():
    """Cleanup on shutdown"""
    global redis_client
    if redis_client:
        redis_client.close()
        logger.info("Redis client closed")

if __name__ == '__main__':
    import atexit
    atexit.register(shutdown_handler)

    logger.info(f"Starting UVR API server on {config.API_HOST}:{config.API_PORT}")
    app.run(
        host=config.API_HOST,
        port=config.API_PORT,
        debug=False
    )
