# cogs/general/services/admin_commands_service.py

from typing import List, Optional, Tuple, Any

from utils.database import Database
from utils.logging_config import logger


class AdminCommandsService:
    """
    Service qui encapsule toute la logique PostgreSQL pour les commandes /db.
    Ne contient AUCUNE logique Discord.
    """

    def __init__(self, db: Optional[Database]):
        self.db = db
        if self.db is None:
            logger.warning(
                "AdminCommandsService initialisé sans base de données (db=None)"
            )

    # ---------- UTILITAIRE INTERNE ----------

    async def _ensure_table(self) -> None:
        """
        Crée la table de test si elle n'existe pas.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans AdminCommandsService")

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS test_entries (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
        await self.db.execute(create_table_sql)
        logger.info("[DB] Table test_entries vérifiée/créée")

    # ---------- MÉTHODES PUBLIQUES UTILISÉES PAR LE COG ----------

    async def test_connection(self) -> int:
        """
        Teste la connexion à PostgreSQL.
        Retourne le résultat de SELECT 1 (normalement 1) ou lève une exception.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans AdminCommandsService")

        logger.info("[DB] Test de connexion PostgreSQL via service")

        # Si tu veux être strict tu peux vérifier is_connected(), sinon on part du principe
        # que BotManager.setup_hook() a déjà appelé db.connect().
        row = await self.db.fetchrow("SELECT 1;")
        if row is None:
            raise RuntimeError("SELECT 1 n'a retourné aucune ligne")
        logger.info("[DB] Connexion PostgreSQL OK (SELECT 1)")
        return row[0]

    async def save_message(
        self,
        user_id: int,
        username: str,
        content: str,
    ) -> Tuple[int, Any]:
        """
        Insère un message dans test_entries.
        Retourne (entry_id, created_at).
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans AdminCommandsService")

        await self._ensure_table()

        insert_sql = """
        INSERT INTO test_entries (user_id, username, content)
        VALUES (%s, %s, %s)
        RETURNING id, created_at;
        """

        row = await self.db.fetchrow(
            insert_sql,
            user_id,
            username,
            content,
        )

        if row is None:
            raise RuntimeError("INSERT n'a retourné aucune ligne (RETURNING)")

        entry_id, created_at = row
        logger.info(
            f"[DB] Entrée ajoutée id={entry_id} user={username} content={content}"
        )
        return entry_id, created_at

    async def get_last_entries(self, limit: int = 5) -> List[tuple]:
        """
        Récupère les dernières entrées de test_entries.
        Retourne une liste de tuples (id, username, content, created_at).
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans AdminCommandsService")

        await self._ensure_table()

        select_sql = """
        SELECT id, username, content, created_at
        FROM test_entries
        ORDER BY created_at DESC
        LIMIT %s;
        """

        rows = await self.db.fetch(select_sql, limit)
        logger.info("[DB] Lecture des dernières entrées test_entries")
        return rows
