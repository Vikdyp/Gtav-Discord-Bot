# cogs\general\services\admin_commands_service.py
from typing import Optional, Any
from utils.database import Database

class TestEntryService:
    def __init__(self, db: Database):
        self.db = db

    async def ensure_table(self):
        sql = """
        CREATE TABLE IF NOT EXISTS test_entries (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
        await self.db.execute(sql)

    async def insert_entry(self, user_id: int, username: str, content: str) -> Optional[Any]:
        sql = """
        INSERT INTO test_entries (user_id, username, content)
        VALUES ($1, $2, $3)
        RETURNING id, created_at;
        """
        return await self.db.fetchrow(sql, user_id, username, content)

    async def get_recent_entries(self, limit: int = 5) -> list[Any]:
        sql = """
        SELECT id, username, content, created_at
        FROM test_entries
        ORDER BY created_at DESC
        LIMIT $1;
        """
        return await self.db.fetch(sql, limit)
