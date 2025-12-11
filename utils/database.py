# utils/database.py
import logging
from typing import Optional, Any, List

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class Database:
    """
    Utilitaire DB basé sur psycopg, même logique que dans GeneralCommands.

    - Utilise une connection string de type :
      postgresql://user:password@host:port/database
    - Ouvre une nouvelle connexion pour chaque requête (comme dans ton cog).
    """

    def __init__(
        self,
        user: str,
        password: str,
        host: str,
        database: str,
        port: int = 5432,
    ):
        self._conn_string = (
            f"postgresql://{user}:{password}@{host}:{port}/{database}"
        )
        self._connected: bool = False  # flag logique, pas une vraie connexion persistante

    # ---------- GESTION "CONNEXION" (LOGIQUE) ----------

    async def connect(self):
        """
        Teste la connexion à la DB et met le flag interne à True si OK.
        Similaire à ton /db action=test.
        """
        try:
            logger.info(f"[DB] Test connexion avec : {self._conn_string}")
            with psycopg.connect(self._conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.fetchone()
            self._connected = True
            logger.info("[DB] Connexion PostgreSQL OK")
        except Exception as e:
            self._connected = False
            logger.error(f"[DB] Erreur de connexion PostgreSQL : {e}")
            raise

    async def close(self):
        """
        On n'a pas de pool ni de connexion persistante, donc on fait
        juste retomber le flag. Gardé pour compatibilité.
        """
        self._connected = False

    def is_connected(self) -> bool:
        """Retourne le flag logique de connexion (connect() a été appelé)."""
        return self._connected

    # ---------- MÉTHODES D'EXÉCUTION ----------

    async def execute(self, query: str, *args) -> None:
        """
        Exécute une requête sans retour (INSERT/UPDATE/DELETE...).

        Usage:
            await db.execute(
                "INSERT INTO table(col1, col2) VALUES (%s, %s)",
                val1, val2
            )
        """
        if not self._connected:
            logger.warning(
                "Tentative d'exécution d'une requête sans connect() préalable"
            )

        try:
            with psycopg.connect(self._conn_string) as conn:
                with conn.cursor() as cur:
                    # psycopg attend un tuple de paramètres -> args est déjà un tuple
                    cur.execute(query, args if args else None)
                conn.commit()
        except Exception as e:
            logger.error(f"[DB] Erreur execute() : {e} | query={query} args={args}")
            raise

    async def fetch(self, query: str, *args) -> List[Any]:
        """
        Exécute une requête SELECT et renvoie toutes les lignes.

        Renvoie une liste de dictionnaires avec noms de colonnes comme clés.

        Usage:
            rows = await db.fetch(
                "SELECT id, username FROM test_entries WHERE user_id = %s",
                user_id
            )
        """
        if not self._connected:
            logger.warning(
                "Tentative de fetch sans connect() préalable"
            )

        try:
            with psycopg.connect(self._conn_string) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, args if args else None)
                    rows = cur.fetchall()
            return rows
        except Exception as e:
            logger.error(f"[DB] Erreur fetch() : {e} | query={query} args={args}")
            raise

    async def fetchrow(self, query: str, *args) -> Optional[Any]:
        """
        Exécute une requête SELECT et renvoie une seule ligne (ou None).

        Renvoie un dictionnaire avec noms de colonnes comme clés.

        Usage:
            row = await db.fetchrow(
                "SELECT id, username FROM test_entries WHERE id = %s",
                entry_id
            )
        """
        if not self._connected:
            logger.warning(
                "Tentative de fetchrow sans connect() préalable"
            )

        try:
            with psycopg.connect(self._conn_string) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, args if args else None)
                    row = cur.fetchone()
            return row
        except Exception as e:
            logger.error(f"[DB] Erreur fetchrow() : {e} | query={query} args={args}")
            raise
