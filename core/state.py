import redis.asyncio as aioredis
from typing import Optional
from core.config import settings

class RedisManager:
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None
    
    async def connect(self):
        self.client = aioredis.from_url(settings.redis_url, decode_responses=True, max_connections=10)
    
    async def disconnect(self):
        if self.client:
            await self.client.close()

# Singleton instance by default because fastapi cache the module on startup
redis_manager = RedisManager()