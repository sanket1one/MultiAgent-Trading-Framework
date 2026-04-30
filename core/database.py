from motor.motor_asyncio import AsyncIOMotorClient
import logging
from .config import settings

logger = logging.getLogger(__name__)


class Database:
    client: AsyncIOMotorClient = None


db = Database()


async def connect_to_mongo():
    logger.info("Connecting to MongoDB...")
    db.client = AsyncIOMotorClient(
        settings.mongodb_url,
        maxPoolSize=30,
        serverSelectionTimeoutMS=3000,
    )

    # Ensure indexes on startup for latency-critical queries
    database = db.client[settings.mongodb_db_name]
    await database.messages.create_index(
        [("session_id", 1), ("timestamp", 1)]
    )
    await database.messages.create_index(
        [("job_id", 1)], unique=True, sparse=True
    )
    logger.info("Connected to MongoDB — indexes ensured.")


async def close_mongo_connection():
    logger.info("Closing MongoDB connection...")
    if db.client:
        db.client.close()
    logger.info("MongoDB connection closed.")


def get_db():
    if db.client is None:
        raise ValueError("Database client not initialized")
    return db.client[settings.mongodb_db_name]
