"""Basic connection example.
"""

import redis

_redis_client = None

def get_redis():
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.Redis(
            host='redis-14738.crce216.sa-east-1-2.ec2.cloud.redislabs.com',
            port=14738,
            decode_responses=True,
            username="default",
            password="CE3qT6jtGcErfsdkl4vQT9tnxz5QcHce",
        )

    return _redis_client




