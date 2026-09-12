import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

MAX_ATTEMPTS = 5
LOCKOUT_TIME = 300  


def get_redis_key(username: str):
    return f"login_attempts:{username}"