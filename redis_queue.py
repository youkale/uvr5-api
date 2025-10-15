#!/usr/bin/env python3
"""
Redis Priority Queue Implementation
Based on Redis ZSet for priority queue management
Reference: https://github.com/youkale/index-tts/blob/main/api_server.py
"""

import json
import time
import logging
from typing import Dict, Any, Optional
import redis

logger = logging.getLogger(__name__)


class RedisPriorityQueue:
    """
    Redis-based priority queue using ZSet

    Priority levels: 1-5
    - 1: Lowest priority
    - 5: Highest priority
    - 3: Default priority (medium)

    Score calculation: timestamp * (6 - priority)
    Lower score = higher priority (processed first)
    """

    def __init__(self, redis_client: redis.Redis, queue_name: str):
        """
        Initialize priority queue

        Args:
            redis_client: Redis client instance
            queue_name: Name of the queue (Redis ZSet key)
        """
        self.redis_client = redis_client
        self.queue_name = queue_name

    def calculate_score(self, priority: int = 3) -> float:
        """
        Calculate score for priority queue

        Lower score = higher priority (processed first)
        priority 5 -> weight 1, priority 1 -> weight 5

        Args:
            priority: Priority level (1-5)

        Returns:
            float: Calculated score
        """
        timestamp = time.time()
        # Invert priority: priority 5 -> weight 1, priority 1 -> weight 5
        priority_weight = 6 - priority
        return timestamp * priority_weight

    def enqueue(self, task_data: Dict[str, Any], priority: int = 3) -> bool:
        """
        Add task to priority queue

        Args:
            task_data: Task data dictionary
            priority: Priority level (1-5, default=3)

        Returns:
            bool: True if task was added successfully
        """
        try:
            # Validate priority
            if not isinstance(priority, int) or priority < 1 or priority > 5:
                logger.warning(f"Invalid priority {priority}, using default priority 3")
                priority = 3

            score = self.calculate_score(priority)
            task_json = json.dumps(task_data)

            # Use zadd to add task with score
            result = self.redis_client.zadd(self.queue_name, {task_json: score})

            logger.info(
                f"Enqueued task {task_data.get('task_uuid', 'unknown')} "
                f"to queue '{self.queue_name}' with priority {priority}, score {score:.2f}"
            )
            return result > 0

        except Exception as e:
            logger.error(f"Failed to enqueue task to '{self.queue_name}': {e}")
            return False

    def dequeue(self, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """
        Get highest priority task from queue

        Args:
            timeout: Blocking timeout in seconds (0 = non-blocking)

        Returns:
            Optional[Dict]: Task data or None if queue is empty
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                if timeout > 0:
                    # Blocking pop with timeout
                    result = self.redis_client.bzpopmin(self.queue_name, timeout=timeout)
                    if result:
                        queue_name, task_json, score = result
                        task_data = json.loads(task_json)
                        logger.info(
                            f"Dequeued task {task_data.get('task_uuid', 'unknown')} "
                            f"from queue '{self.queue_name}' with score {score:.2f}"
                        )
                        return task_data
                else:
                    # Non-blocking pop
                    result = self.redis_client.zpopmin(self.queue_name, count=1)
                    if result:
                        task_json, score = result[0]
                        task_data = json.loads(task_json)
                        logger.info(
                            f"Dequeued task {task_data.get('task_uuid', 'unknown')} "
                            f"from queue '{self.queue_name}' with score {score:.2f}"
                        )
                        return task_data

                return None

            except redis.TimeoutError as e:
                retry_count += 1
                logger.warning(
                    f"Redis timeout in dequeue (attempt {retry_count}/{max_retries}): {e}"
                )
                if retry_count >= max_retries:
                    logger.error(f"Max retries reached for dequeue from '{self.queue_name}'")
                    return None
                time.sleep(min(retry_count * 2, 10))  # Exponential backoff

            except redis.ConnectionError as e:
                retry_count += 1
                logger.error(
                    f"Redis connection error in dequeue (attempt {retry_count}/{max_retries}): {e}"
                )
                if retry_count >= max_retries:
                    logger.error(f"Max retries reached for dequeue from '{self.queue_name}'")
                    raise
                time.sleep(min(retry_count * 2, 10))

            except Exception as e:
                logger.error(f"Unexpected error in dequeue from '{self.queue_name}': {e}")
                return None

        return None

    def size(self) -> int:
        """
        Get the number of tasks in the queue

        Returns:
            int: Number of tasks in queue
        """
        try:
            return self.redis_client.zcard(self.queue_name)
        except Exception as e:
            logger.error(f"Failed to get queue size for '{self.queue_name}': {e}")
            return 0

    def clear(self) -> bool:
        """
        Clear all tasks from the queue

        Returns:
            bool: True if queue was cleared successfully
        """
        try:
            self.redis_client.delete(self.queue_name)
            logger.info(f"Queue '{self.queue_name}' cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear queue '{self.queue_name}': {e}")
            return False

    def peek(self, count: int = 1) -> list:
        """
        Peek at the highest priority tasks without removing them

        Args:
            count: Number of tasks to peek at

        Returns:
            list: List of task data dictionaries
        """
        try:
            results = self.redis_client.zrange(
                self.queue_name, 0, count - 1, withscores=True
            )
            tasks = []
            for task_json, score in results:
                task_data = json.loads(task_json)
                task_data['_score'] = score
                tasks.append(task_data)
            return tasks
        except Exception as e:
            logger.error(f"Failed to peek queue '{self.queue_name}': {e}")
            return []


def create_redis_client(
    host: str,
    port: int,
    db: int = 0,
    password: Optional[str] = None,
    socket_timeout: int = 30,
    socket_connect_timeout: int = 10,
    retry_on_timeout: bool = True,
    health_check_interval: int = 30
) -> redis.Redis:
    """
    Create and initialize Redis client with connection pooling

    Args:
        host: Redis host
        port: Redis port
        db: Redis database number
        password: Redis password (optional)
        socket_timeout: Socket timeout in seconds
        socket_connect_timeout: Socket connect timeout in seconds
        retry_on_timeout: Retry on timeout
        health_check_interval: Health check interval in seconds

    Returns:
        redis.Redis: Redis client instance

    Raises:
        redis.ConnectionError: If connection fails
    """
    try:
        redis_config = {
            'host': host,
            'port': port,
            'db': db,
            'decode_responses': True,
            'socket_connect_timeout': socket_connect_timeout,
            'socket_timeout': socket_timeout,
            'socket_keepalive': True,
            'socket_keepalive_options': {},
            'retry_on_timeout': retry_on_timeout,
            'health_check_interval': health_check_interval
        }

        if password:
            redis_config['password'] = password

        redis_client = redis.Redis(**redis_config)

        # Test connection
        redis_client.ping()
        logger.info(f"Redis client connected to {host}:{port}/{db}")

        return redis_client

    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis at {host}:{port}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Redis client: {e}")
        raise
