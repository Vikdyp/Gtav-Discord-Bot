# utils/database.py
import asyncpg
from typing import Optional, Any


class Database:
    def __init__(self, user: str, password: str, host: str, database: str, port: int = 5432):
        self._dsn = {
            "user": user,
            "password": password,
            "database": database,
            "host": host,
            "port": port,
        }
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        if self.pool is None:
            self.pool = await asyncpg.create_pool(**self._dsn)

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def execute(self, query: str, *args) -> None:
        assert self.pool is not None, "Database pool is not initialized"
        async with self.pool.acquire() as conn:
            await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list[Any]:
        assert self.pool is not None, "Database pool is not initialized"
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[Any]:
        assert self.pool is not None, "Database pool is not initialized"
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
