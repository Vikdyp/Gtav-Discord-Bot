# utils/database.py
import logging
from typing import Optional, Any, List

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

# Utiliser le logger principal "lester" pour une meilleure visibilité
logger = logging.getLogger("lester")


class Database:
    """
    Utilitaire DB basé sur psycopg avec pool de connexions.

    - Utilise une connection string de type :
      postgresql://user:password@host:port/database
    - Utilise un pool de connexions pour optimiser les performances
    - Pool min: 2 connexions, max: 10 connexions
    """

    def __init__(
        self,
        user: str,
        password: str,
        host: str,
        database: str,
        port: int = 5432,
    ):
        # Stocke la connexion complète et une version masquée pour les logs
        self._conn_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self._safe_conn_string = f"postgresql://{user}:****@{host}:{port}/{database}"
        self._pool: Optional[AsyncConnectionPool] = None
        self._connected: bool = False

    # ---------- GESTION "CONNEXION" (LOGIQUE) ----------

    async def connect(self):
        """
        Initialise le pool de connexions et teste la connexion à la DB.
        Le pool maintient des connexions persistantes réutilisables.
        """
        try:
            logger.info(f"[DB] Initialisation du pool de connexions : {self._safe_conn_string}")

            # Création du pool avec min 2 et max 10 connexions
            self._pool = AsyncConnectionPool(
                conninfo=self._conn_string,
                min_size=2,
                max_size=10,
                timeout=30.0,
                open=False
            )

            # Ouverture du pool
            await self._pool.open()

            # Test de connexion
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1;")
                    await cur.fetchone()

            self._connected = True
            logger.info("[DB] Pool de connexions PostgreSQL initialisé avec succès (min=2, max=10)")
        except Exception as e:
            self._connected = False
            logger.error(f"[DB] Erreur d'initialisation du pool PostgreSQL : {e}")
            raise

    async def close(self):
        """
        Ferme proprement le pool de connexions.
        """
        if self._pool:
            await self._pool.close()
            logger.info("[DB] Pool de connexions fermé")
        self._connected = False

    def is_connected(self) -> bool:
        """Retourne le flag logique de connexion (connect() a été appelé)."""
        return self._connected

    # ---------- MÉTHODES D'EXÉCUTION ----------

    async def execute(self, query: str, *args) -> None:
        """
        Exécute une requête sans retour (INSERT/UPDATE/DELETE...).
        Utilise une connexion du pool pour optimiser les performances.

        Usage:
            await db.execute(
                "INSERT INTO table(col1, col2) VALUES (%s, %s)",
                val1, val2
            )
        """
        if not self._connected or not self._pool:
            logger.warning(
                "Tentative d'exécution d'une requête sans connect() préalable"
            )
            raise RuntimeError("Base de données non connectée")

        try:
            async with self._pool.connection() as conn:
                async with conn.cursor() as cur:
                    # psycopg attend un tuple de paramètres -> args est déjà un tuple
                    await cur.execute(query, args if args else None)
                await conn.commit()
        except Exception as e:
            logger.error(f"[DB] Erreur execute() : {e} | query={query} args={args}")
            raise

    async def fetch(self, query: str, *args) -> List[Any]:
        """
        Exécute une requête SELECT et renvoie toutes les lignes.
        Utilise une connexion du pool pour optimiser les performances.

        Renvoie une liste de dictionnaires avec noms de colonnes comme clés.

        Usage:
            rows = await db.fetch(
                "SELECT id, username FROM test_entries WHERE user_id = %s",
                user_id
            )
        """
        if not self._connected or not self._pool:
            logger.warning(
                "Tentative de fetch sans connect() préalable"
            )
            raise RuntimeError("Base de données non connectée")

        try:
            async with self._pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(query, args if args else None)
                    rows = await cur.fetchall()
            return rows
        except Exception as e:
            logger.error(f"[DB] Erreur fetch() : {e} | query={query} args={args}")
            raise

    async def fetchrow(self, query: str, *args) -> Optional[Any]:
        """
        Exécute une requête SELECT et renvoie une seule ligne (ou None).
        Utilise une connexion du pool pour optimiser les performances.

        Renvoie un dictionnaire avec noms de colonnes comme clés.

        Usage:
            row = await db.fetchrow(
                "SELECT id, username FROM test_entries WHERE id = %s",
                entry_id
            )
        """
        if not self._connected or not self._pool:
            logger.warning(
                "Tentative de fetchrow sans connect() préalable"
            )
            raise RuntimeError("Base de données non connectée")

        try:
            async with self._pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(query, args if args else None)
                    row = await cur.fetchone()
            return row
        except Exception as e:
            logger.error(f"[DB] Erreur fetchrow() : {e} | query={query} args={args}")
            raise
