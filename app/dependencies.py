from core.state import redis_manager

async def get_redis():
    return redis_manager.client