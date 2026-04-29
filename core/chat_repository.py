from datetime import datetime, timezone
from typing import List, Dict, Any
from .database import get_db

class ChatRepository:
    def __init__(self, collection_name: str = "messages"):
        self.collection_name = collection_name

    @property
    def collection(self):
        return get_db()[self.collection_name]

    async def save_message(self, session_id: str, role: str, content: str) -> Dict[str, Any]:
        """
        Save a chat message to the database.
        """
        message = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc)
        }
        result = await self.collection.insert_one(message)
        message["_id"] = str(result.inserted_id)
        return message

    async def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve chat history for a given session.
        """
        cursor = self.collection.find({"session_id": session_id}).sort("timestamp", 1).limit(limit)
        history = []
        async for document in cursor:
            document["_id"] = str(document["_id"])
            history.append(document)
        return history
