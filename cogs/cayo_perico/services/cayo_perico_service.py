# cogs/cayo_perico/services/cayo_perico_service.py
"""
Service pour la fonctionnalité Cayo Perico.

IMPORTANT: Ce service ne crée PAS les tables automatiquement.
Les tables doivent être créées via les migrations SQL :
    1. Utiliser /migrate action:"Voir le statut" pour vérifier
    2. Utiliser /migrate action:"Appliquer Cayo Perico V2" pour créer les tables

Tables requises :
    - users (table de base)
    - cayo_heists (avec colonnes V2: hard_mode, safe_amount, optimized_plan)
    - cayo_participants
    - cayo_results (pour les statistiques)
"""

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

    async def _get_or_create_user(self, discord_id: int) -> int:
        """
        Retourne l'ID interne (users.id) pour un discord_id.
        Crée la ligne si elle n'existe pas.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

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

    async def has_active_heist(self, leader_discord_id: int) -> bool:
        """
        Vérifie si un leader a déjà un braquage actif (pending ou ready).

        Args:
            leader_discord_id: ID Discord du leader

        Returns:
            True si un braquage actif existe, False sinon
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        # Récupérer l'ID interne du leader (ne pas créer s'il n'existe pas)
        select_user_sql = """
        SELECT id
        FROM users
        WHERE discord_id = %s;
        """

        user_row = await self.db.fetchrow(select_user_sql, leader_discord_id)
        if user_row is None:
            return False  # Si l'utilisateur n'existe pas, pas de braquage actif

        leader_user_id = user_row[0]

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM cayo_heists
            WHERE leader_user_id = %s
              AND status IN ('pending', 'ready')
        );
        """

        row = await self.db.fetchrow(query, leader_user_id)
        return row[0] if row else False

    async def create_heist(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        leader_discord_id: int,
        primary_loot: str,
        secondary_loot: Dict[str, int],
        estimated_loot: Optional[int] = None,
        office_paintings: int = 0,
        hard_mode: bool = False,
    ) -> int:
        """
        Crée un braquage Cayo Perico et renvoie son ID.

        Args:
            office_paintings: Nombre de tableaux dans le bureau (0-2, accessibles en solo)

        Raises:
            ValueError: Si le leader a déjà un braquage actif
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        # Vérifier qu'il n'y a pas déjà un braquage actif pour ce leader
        if await self.has_active_heist(leader_discord_id):
            raise ValueError("Tu as déjà un braquage actif. Termine-le avant d'en créer un nouveau.")

        leader_user_id = await self._get_or_create_user(leader_discord_id)

        import json

        insert_sql = """
        INSERT INTO cayo_heists (
            guild_id, channel_id, message_id,
            leader_user_id,
            primary_loot, secondary_loot, estimated_loot, office_paintings, hard_mode
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """

        row = await self.db.fetchrow(
            insert_sql,
            guild_id,
            channel_id,
            message_id,
            leader_user_id,
            primary_loot,
            json.dumps(secondary_loot),
            estimated_loot,
            office_paintings,
            hard_mode,
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

        user_id = await self._get_or_create_user(user_discord_id)

        delete_sql = """
        DELETE FROM cayo_participants
        WHERE heist_id = %s AND user_id = %s;
        """

        await self.db.execute(delete_sql, heist_id, user_id)
        logger.info(f"[Cayo] Participant {user_discord_id} retiré du heist {heist_id}")

    async def mark_ready(self, heist_id: int) -> None:
        """
        Passe le braquage en statut 'ready' et enregistre l'horodatage.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        update_sql = """
        UPDATE cayo_heists
        SET status = 'ready',
            ready_at = NOW(),
            updated_at = NOW()
        WHERE id = %s;
        """

        await self.db.execute(update_sql, heist_id)
        logger.info(f"[Cayo] Heist {heist_id} marqué comme prêt")

    async def close_heist(
        self,
        heist_id: int,
        final_loot: Optional[int] = None,
        elite_completed: bool = False,
        finished_at: Optional[Any] = None
    ) -> None:
        """
        Passe le braquage en statut 'finished' et enregistre les informations finales.

        Args:
            heist_id: ID du braquage
            final_loot: Butin final total (optionnel)
            elite_completed: True si le défi Elite a été validé
            finished_at: Horodatage de fin (datetime, optionnel, NOW() par défaut)
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        # Si finished_at n'est pas fourni, utiliser NOW()
        if finished_at is None:
            update_sql = """
            UPDATE cayo_heists
            SET status = 'finished',
                final_loot = %s,
                elite_challenge_completed = %s,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = %s;
            """
            await self.db.execute(update_sql, final_loot, elite_completed, heist_id)
        else:
            update_sql = """
            UPDATE cayo_heists
            SET status = 'finished',
                final_loot = %s,
                elite_challenge_completed = %s,
                finished_at = %s,
                updated_at = NOW()
            WHERE id = %s;
            """
            await self.db.execute(update_sql, final_loot, elite_completed, finished_at, heist_id)

        logger.info(f"[Cayo] Heist {heist_id} terminé (final_loot={final_loot}, elite={elite_completed})")

    async def delete_heist(self, heist_id: int) -> None:
        """
        Supprime complètement un braquage de la base de données.
        Les participants sont automatiquement supprimés (CASCADE).
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        delete_sql = """
        DELETE FROM cayo_heists
        WHERE id = %s;
        """

        await self.db.execute(delete_sql, heist_id)
        logger.info(f"[Cayo] Heist {heist_id} supprimé")

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
            h.updated_at,
            h.hard_mode,
            h.office_paintings
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
            "hard_mode": row[12] if row[12] is not None else False,
            "office_paintings": row[13] if row[13] else 0,
        }

    async def get_participants(self, heist_id: int) -> List[int]:
        """
        Retourne la liste des user_id Discord participants à un heist.
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        select_sql = """
        SELECT u.discord_id
        FROM cayo_participants p
        JOIN users u ON p.user_id = u.id
        WHERE p.heist_id = %s
        ORDER BY p.joined_at ASC;
        """

        rows = await self.db.fetch(select_sql, heist_id)
        return [row[0] for row in rows]

    async def update_optimized_plan(self, heist_id: int, optimized_plan: List[Dict]) -> None:
        """
        Met à jour le plan de sac optimisé d'un braquage.

        Args:
            heist_id: ID du braquage
            optimized_plan: Plan généré par optimizer.optimize_bags()
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        import json

        update_sql = """
        UPDATE cayo_heists
        SET optimized_plan = %s,
            updated_at = NOW()
        WHERE id = %s;
        """

        await self.db.execute(update_sql, json.dumps(optimized_plan), heist_id)
        logger.info(f"[Cayo] Plan optimisé mis à jour pour heist {heist_id}")

    async def save_real_gains(
        self,
        heist_id: int,
        real_gains: Dict[int, int]
    ) -> None:
        """
        Sauvegarde les gains réels de chaque participant.

        Args:
            heist_id: ID du braquage
            real_gains: {discord_id: montant_réel}
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        # Récupérer le heist avec le plan prévu
        heist = await self.get_heist_by_id(heist_id)
        if heist is None:
            raise ValueError(f"Heist {heist_id} non trouvé")

        optimized_plan = heist.get("optimized_plan") or []
        participants = await self.get_participants(heist_id)

        # Sauvegarder pour chaque participant
        for idx, participant_discord_id in enumerate(participants):
            user_id = await self._get_or_create_user(participant_discord_id)

            # Récupérer le gain prévu depuis le plan
            predicted_gain = 0
            if idx < len(optimized_plan):
                predicted_gain = optimized_plan[idx].get("total_value", 0)

            real_gain = real_gains.get(participant_discord_id, 0)

            insert_sql = """
            INSERT INTO cayo_results (heist_id, user_id, predicted_gain, real_gain)
            VALUES (%s, %s, %s, %s);
            """

            await self.db.execute(insert_sql, heist_id, user_id, predicted_gain, real_gain)

        logger.info(f"[Cayo] Gains réels sauvegardés pour heist {heist_id}")

    async def get_heist_by_id(self, heist_id: int) -> Optional[Dict[str, Any]]:
        """
        Récupère un heist par son ID.

        Args:
            heist_id: ID du braquage

        Returns:
            Dict avec les infos du heist ou None
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

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
            h.hard_mode,
            h.safe_amount,
            h.optimized_plan,
            h.created_at,
            h.updated_at,
            h.ready_at,
            h.finished_at,
            h.elite_challenge_completed,
            h.custom_shares,
            h.office_paintings
        FROM cayo_heists h
        JOIN users u ON h.leader_user_id = u.id
        WHERE h.id = %s;
        """

        row = await self.db.fetchrow(select_sql, heist_id)

        if row is None:
            return None

        return {
            "id": row[0],
            "guild_id": row[1],
            "channel_id": row[2],
            "message_id": row[3],
            "leader_id": row[4],
            "primary_loot": row[5],
            "secondary_loot": row[6],
            "estimated_loot": row[7],
            "final_loot": row[8],
            "status": row[9],
            "hard_mode": row[10],
            "safe_amount": row[11],
            # JSONB PostgreSQL retourne déjà un dict/list Python avec psycopg
            "optimized_plan": row[12] if row[12] else [],
            "created_at": row[13],
            "updated_at": row[14],
            "ready_at": row[15],
            "finished_at": row[16],
            "elite_challenge_completed": row[17],
            "custom_shares": row[18] if row[18] else None,
            "office_paintings": row[19] if row[19] else 0,
        }

    async def get_user_statistics(self, discord_id: int) -> Dict[str, Any]:
        """
        Récupère les statistiques d'un utilisateur.

        Args:
            discord_id: ID Discord de l'utilisateur

        Returns:
            Dict avec les stats
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        select_sql = """
        SELECT
            COUNT(DISTINCT r.heist_id) as total_heists,
            COALESCE(AVG(r.real_gain), 0) as avg_gain,
            COALESCE(AVG(r.accuracy_percent), 0) as avg_accuracy,
            COALESCE(SUM(r.real_gain), 0) as total_earned
        FROM users u
        LEFT JOIN cayo_results r ON u.id = r.user_id
        WHERE u.discord_id = %s
        GROUP BY u.id;
        """

        row = await self.db.fetchrow(select_sql, discord_id)

        if row is None:
            return {
                "total_heists": 0,
                "avg_gain": 0,
                "avg_accuracy": 0.0,
                "total_earned": 0,
            }

        return {
            "total_heists": row[0] or 0,
            "avg_gain": int(row[1]) if row[1] else 0,
            "avg_accuracy": round(float(row[2]), 2) if row[2] else 0.0,
            "total_earned": int(row[3]) if row[3] else 0,
        }

    async def update_custom_shares(self, heist_id: int, shares: Dict[int, float]) -> None:
        """
        Met à jour les parts personnalisées pour un braquage.

        Args:
            heist_id: ID du braquage
            shares: Dictionnaire {discord_id: pourcentage}
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        import json

        # Convertir les clés en string pour JSONB
        shares_json = {str(k): v for k, v in shares.items()}

        update_sql = """
        UPDATE cayo_heists
        SET custom_shares = %s,
            updated_at = NOW()
        WHERE id = %s;
        """

        await self.db.execute(update_sql, json.dumps(shares_json), heist_id)
        logger.info(f"[Cayo] Parts personnalisées mises à jour pour heist {heist_id}")

    async def get_custom_shares(self, heist_id: int) -> Optional[Dict[int, float]]:
        """
        Récupère les parts personnalisées d'un braquage.

        Args:
            heist_id: ID du braquage

        Returns:
            {discord_id: pourcentage} ou None si parts par défaut
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        select_sql = """
        SELECT custom_shares
        FROM cayo_heists
        WHERE id = %s;
        """

        row = await self.db.fetchrow(select_sql, heist_id)

        if row is None or row[0] is None:
            return None

        import json

        # Convertir les clés string en int
        shares_json = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return {int(k): v for k, v in shares_json.items()}

    async def is_participant(self, heist_id: int, user_discord_id: int) -> bool:
        """
        Vérifie si un utilisateur est participant à un braquage.

        Args:
            heist_id: ID du braquage
            user_discord_id: ID Discord de l'utilisateur

        Returns:
            True si participant, False sinon
        """
        if self.db is None:
            raise RuntimeError("Base de données non disponible dans CayoPericoService")

        user_id = await self._get_or_create_user(user_discord_id)

        select_sql = """
        SELECT EXISTS (
            SELECT 1
            FROM cayo_participants
            WHERE heist_id = %s AND user_id = %s
        );
        """

        row = await self.db.fetchrow(select_sql, heist_id, user_id)
        return row[0] if row else False

    async def get_or_create_user_id(self, discord_id: int) -> int:
        """
        Récupère ou crée un user_id depuis un discord_id.
        Méthode publique exposée pour les autres services (ex: notifications).

        Args:
            discord_id: ID Discord de l'utilisateur

        Returns:
            ID interne de l'utilisateur (users.id)
        """
        return await self._get_or_create_user(discord_id)
