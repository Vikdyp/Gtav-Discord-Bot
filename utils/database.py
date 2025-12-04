# utils/database.py
import asyncpg
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(
        self, user: str, password: str, host: str, database: str, port: int = 5432
    ):
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

    def is_connected(self) -> bool:
        """Vérifie si la base de données est connectée"""
        return self.pool is not None

    async def execute(self, query: str, *args) -> None:
        if self.pool is None:
            logger.warning(
                "Tentative d'exécution d'une requête sans connexion DB"
            )
            return
        async with self.pool.acquire() as conn:
            await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list[Any]:
        if self.pool is None:
            logger.warning(
                "Tentative de fetch sans connexion DB - Retourne liste vide"
            )
            return []
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> Optional[Any]:
        if self.pool is None:
            logger.warning(
                "Tentative de fetchrow sans connexion DB - Retourne None"
            )
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
