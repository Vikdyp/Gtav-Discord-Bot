# cogs/gta/services/cayo_perico_service.py

from typing import Optional, Any, Dict, List

from utils.database import Database
from utils.logging_config import logger


class CayoPericoService:
    """
    Service qui encapsule toute la logique PostgreSQL pour la fonctionnalité Cayo Perico.
    Aucune logique Discord ici, uniquement de la BDD et de la logique métier.
    """

    def __init__(self, db: Optional[Database]):
        self.db = db

    async def _ensure_tables(self) -> None:
        """
        Crée les tables nécessaires si elles n'existent pas.
        - users
        - cayo_heists
        - cayo_participants
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        # Table users (utilisateur Discord -> id interne)
        create_users_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            discord_id  BIGINT NOT NULL UNIQUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        # Table des braquages Cayo
        create_heists_sql = """
        CREATE TABLE IF NOT EXISTS cayo_heists (
            id              SERIAL PRIMARY KEY,
            guild_id        BIGINT NOT NULL,
            channel_id      BIGINT NOT NULL,
            message_id      BIGINT NOT NULL,

            leader_user_id  INTEGER NOT NULL REFERENCES users(id),

            primary_loot    TEXT NOT NULL,
            secondary_loot  JSONB NOT NULL,

            estimated_loot  INTEGER,
            final_loot      INTEGER,
            status          TEXT NOT NULL DEFAULT 'pending',

            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        # Table des participants
        create_participants_sql = """
        CREATE TABLE IF NOT EXISTS cayo_participants (
            id          SERIAL PRIMARY KEY,
            heist_id    INTEGER NOT NULL REFERENCES cayo_heists(id) ON DELETE CASCADE,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            role        TEXT,
            bag_plan    JSONB,
            joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        # Contrainte d'unicité pour éviter les doublons (un user par heist)
        unique_participant_sql = """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM   pg_constraint
                WHERE  conname = 'uq_cayo_participant'
            ) THEN
                ALTER TABLE cayo_participants
                ADD CONSTRAINT uq_cayo_participant UNIQUE (heist_id, user_id);
            END IF;
        END$$;
        """

        # Index utiles
        index_heists_status_sql = """
        CREATE INDEX IF NOT EXISTS idx_cayo_heists_guild_status
        ON cayo_heists (guild_id, status);
        """
        index_heists_message_sql = """
        CREATE INDEX IF NOT EXISTS idx_cayo_heists_message
        ON cayo_heists (guild_id, channel_id, message_id);
        """

        await self.db.execute(create_users_sql)
        await self.db.execute(create_heists_sql)
        await self.db.execute(create_participants_sql)
        await self.db.execute(unique_participant_sql)
        await self.db.execute(index_heists_status_sql)
        await self.db.execute(index_heists_message_sql)

    async def _get_or_create_user(self, discord_id: int) -> int:
        """
        Retourne l'ID interne (users.id) pour un discord_id.
        Crée la ligne si elle n'existe pas.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        await self._ensure_tables()

        select_sql = """
        SELECT id
        FROM users
        WHERE discord_id = %s;
        """

        row = await self.db.fetchrow(select_sql, discord_id)
        if row:
            return row[0]

        insert_sql = """
        INSERT INTO users (discord_id)
        VALUES (%s)
        RETURNING id;
        """

        row = await self.db.fetchrow(insert_sql, discord_id)
        if row is None:
            raise RuntimeError("Impossible de créer l'utilisateur en BDD")
        user_id = row[0]
        logger.info(f"[Cayo] Nouvel utilisateur créé (discord_id={discord_id}, id={user_id})")
        return user_id

    async def create_heist(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        leader_discord_id: int,
        primary_loot: str,
        secondary_loot: Dict[str, int],
        estimated_loot: Optional[int] = None,
    ) -> int:
        """
        Crée un braquage Cayo Perico et renvoie son ID.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        await self._ensure_tables()

        leader_user_id = await self._get_or_create_user(leader_discord_id)

        insert_sql = """
        INSERT INTO cayo_heists (
            guild_id, channel_id, message_id,
            leader_user_id,
            primary_loot, secondary_loot, estimated_loot
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """

        row = await self.db.fetchrow(
            insert_sql,
            guild_id,
            channel_id,
            message_id,
            leader_user_id,
            primary_loot,
            secondary_loot,
            estimated_loot,
        )

        if row is None:
            raise RuntimeError("Impossible de créer le braquage Cayo Perico")

        heist_id = row[0]
        logger.info(f"[Cayo] Braquage créé (id={heist_id}, guild={guild_id})")
        return heist_id

    async def add_participant(self, heist_id: int, user_discord_id: int) -> None:
        """
        Ajoute un participant à un braquage.
        Ignore silencieusement si le participant est déjà présent.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        await self._ensure_tables()

        user_id = await self._get_or_create_user(user_discord_id)

        insert_sql = """
        INSERT INTO cayo_participants (heist_id, user_id)
        VALUES (%s, %s)
        ON CONFLICT (heist_id, user_id) DO NOTHING;
        """

        await self.db.execute(insert_sql, heist_id, user_id)
        logger.info(f"[Cayo] Participant {user_discord_id} ajouté au heist {heist_id}")

    async def remove_participant(self, heist_id: int, user_discord_id: int) -> None:
        """
        Supprime un participant d'un braquage.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        await self._ensure_tables()

        user_id = await self._get_or_create_user(user_discord_id)

        delete_sql = """
        DELETE FROM cayo_participants
        WHERE heist_id = %s AND user_id = %s;
        """

        await self.db.execute(delete_sql, heist_id, user_id)
        logger.info(f"[Cayo] Participant {user_discord_id} retiré du heist {heist_id}")

    async def mark_ready(self, heist_id: int) -> None:
        """
        Passe le braquage en statut 'ready'.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        await self._ensure_tables()

        update_sql = """
        UPDATE cayo_heists
        SET status = 'ready',
            updated_at = NOW()
        WHERE id = %s;
        """

        await self.db.execute(update_sql, heist_id)
        logger.info(f"[Cayo] Heist {heist_id} marqué comme prêt")

    async def close_heist(self, heist_id: int, final_loot: Optional[int] = None) -> None:
        """
        Passe le braquage en statut 'finished' et enregistre éventuellement le butin final.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        await self._ensure_tables()

        update_sql = """
        UPDATE cayo_heists
        SET status = 'finished',
            final_loot = %s,
            updated_at = NOW()
        WHERE id = %s;
        """

        await self.db.execute(update_sql, final_loot, heist_id)
        logger.info(f"[Cayo] Heist {heist_id} terminé (final_loot={final_loot})")

    async def get_heist_by_message(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Récupère un heist à partir de son message Discord.
        Retourne un dict avec leader_id = discord_id (pas l'id interne).
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        await self._ensure_tables()

        select_sql = """
        SELECT
            h.id,
            h.guild_id,
            h.channel_id,
            h.message_id,
            u.discord_id AS leader_discord_id,
            h.primary_loot,
            h.secondary_loot,
            h.estimated_loot,
            h.final_loot,
            h.status,
            h.created_at,
            h.updated_at
        FROM cayo_heists h
        JOIN users u ON h.leader_user_id = u.id
        WHERE h.guild_id = %s
          AND h.channel_id = %s
          AND h.message_id = %s;
        """

        row = await self.db.fetchrow(select_sql, guild_id, channel_id, message_id)

        if row is None:
            return None

        return {
            "id": row[0],
            "guild_id": row[1],
            "channel_id": row[2],
            "message_id": row[3],
            # IMPORTANT : côté Cog, on manipule toujours des discord_id
            "leader_id": row[4],
            "primary_loot": row[5],
            "secondary_loot": row[6],
            "estimated_loot": row[7],
            "final_loot": row[8],
            "status": row[9],
            "created_at": row[10],
            "updated_at": row[11],
        }

    async def get_participants(self, heist_id: int) -> List[int]:
        """
        Retourne la liste des user_id Discord participants à un heist.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        await self._ensure_tables()

        select_sql = """
        SELECT u.discord_id
        FROM cayo_participants p
        JOIN users u ON p.user_id = u.id
        WHERE p.heist_id = %s
        ORDER BY p.joined_at ASC;
        """

        rows = await self.db.fetch(select_sql, heist_id)
        return [row[0] for row in rows]
