import redis
from app.config import settings

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_keepalive=True,
    retry_on_timeout=True,
    health_check_interval=30,
)