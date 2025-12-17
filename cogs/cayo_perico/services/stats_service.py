# cogs/cayo_perico/services/stats_service.py
"""
Service pour gérer les statistiques et leaderboards Cayo Perico.
"""

from typing import Optional, List, Dict
from utils.database import Database
from utils.logging_config import logger


class CayoStatsService:
    """Service pour les statistiques et leaderboards Cayo Perico."""

    def __init__(self, db: Optional[Database]):
        self.db = db
        self.logger = logger

    def _ensure_db(self):
        """Vérifie que la base de données est disponible."""
        if self.db is None:
            raise RuntimeError("Base de données non disponible")

    # ==================== LEADERBOARDS ====================

    async def get_top_total_earned(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """
        Récupère le top des joueurs par total gagné.

        Args:
            guild_id: ID du serveur Discord
            limit: Nombre de joueurs à retourner

        Returns:
            Liste de dicts avec rank, discord_id, total_earned, total_heists, avg_gain
        """
        self._ensure_db()

        query = """
            WITH guild_users AS (
                -- Récupérer les utilisateurs qui ont participé à au moins un braquage sur ce serveur
                SELECT DISTINCT u.id as user_id
                FROM users u
                INNER JOIN cayo_participants cp ON u.id = cp.user_id
                INNER JOIN cayo_heists h ON cp.heist_id = h.id
                WHERE h.guild_id = %s AND h.status = 'finished'
            )
            SELECT
                s.discord_id,
                u.username,
                u.display_name,
                s.total_earned,
                s.total_heists,
                s.avg_gain,
                RANK() OVER (ORDER BY s.total_earned DESC) as rank
            FROM cayo_user_stats s
            INNER JOIN guild_users gu ON s.user_id = gu.user_id
            INNER JOIN users u ON s.user_id = u.id
            WHERE s.total_heists > 0
            ORDER BY s.total_earned DESC
            LIMIT %s
        """

        rows = await self.db.fetch(query, guild_id, limit)
        return [dict(row) for row in rows]

    async def get_top_total_heists(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Récupère le top des joueurs par nombre de braquages complétés."""
        self._ensure_db()

        query = """
            WITH guild_users AS (
                SELECT DISTINCT u.id as user_id
                FROM users u
                INNER JOIN cayo_participants cp ON u.id = cp.user_id
                INNER JOIN cayo_heists h ON cp.heist_id = h.id
                WHERE h.guild_id = %s AND h.status = 'finished'
            )
            SELECT
                s.discord_id,
                u.username,
                u.display_name,
                s.total_heists,
                s.total_earned,
                s.avg_gain,
                RANK() OVER (ORDER BY s.total_heists DESC) as rank
            FROM cayo_user_stats s
            INNER JOIN guild_users gu ON s.user_id = gu.user_id
            INNER JOIN users u ON s.user_id = u.id
            WHERE s.total_heists > 0
            ORDER BY s.total_heists DESC
            LIMIT %s
        """

        rows = await self.db.fetch(query, guild_id, limit)
        return [dict(row) for row in rows]

    async def get_top_avg_gain(self, guild_id: int, limit: int = 10, min_heists: int = 3) -> List[Dict]:
        """
        Récupère le top des joueurs par gain moyen.

        Args:
            guild_id: ID du serveur
            limit: Nombre de joueurs
            min_heists: Nombre minimum de braquages pour être éligible (défaut: 3)
        """
        self._ensure_db()

        query = """
            WITH guild_users AS (
                SELECT DISTINCT u.id as user_id
                FROM users u
                INNER JOIN cayo_participants cp ON u.id = cp.user_id
                INNER JOIN cayo_heists h ON cp.heist_id = h.id
                WHERE h.guild_id = %s AND h.status = 'finished'
            )
            SELECT
                s.discord_id,
                u.username,
                u.display_name,
                s.avg_gain,
                s.total_heists,
                s.total_earned,
                RANK() OVER (ORDER BY s.avg_gain DESC) as rank
            FROM cayo_user_stats s
            INNER JOIN guild_users gu ON s.user_id = gu.user_id
            INNER JOIN users u ON s.user_id = u.id
            WHERE s.total_heists >= %s
            ORDER BY s.avg_gain DESC
            LIMIT %s
        """

        rows = await self.db.fetch(query, guild_id, min_heists, limit)
        return [dict(row) for row in rows]

    async def get_top_elite_count(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Récupère le top des joueurs par nombre de Défi Elite réussis."""
        self._ensure_db()

        query = """
            WITH guild_users AS (
                SELECT DISTINCT u.id as user_id
                FROM users u
                INNER JOIN cayo_participants cp ON u.id = cp.user_id
                INNER JOIN cayo_heists h ON cp.heist_id = h.id
                WHERE h.guild_id = %s AND h.status = 'finished'
            )
            SELECT
                s.discord_id,
                u.username,
                u.display_name,
                s.elite_count,
                s.total_heists,
                CAST(s.elite_count * 100.0 / NULLIF(s.total_heists, 0) AS INTEGER) as elite_rate_percent,
                RANK() OVER (ORDER BY s.elite_count DESC) as rank
            FROM cayo_user_stats s
            INNER JOIN guild_users gu ON s.user_id = gu.user_id
            INNER JOIN users u ON s.user_id = u.id
            WHERE s.elite_count > 0
            ORDER BY s.elite_count DESC
            LIMIT %s
        """

        rows = await self.db.fetch(query, guild_id, limit)
        return [dict(row) for row in rows]

    async def get_top_speed_run(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Récupère le top des joueurs par temps de mission le plus rapide."""
        self._ensure_db()

        query = """
            WITH guild_users AS (
                SELECT DISTINCT u.id as user_id
                FROM users u
                INNER JOIN cayo_participants cp ON u.id = cp.user_id
                INNER JOIN cayo_heists h ON cp.heist_id = h.id
                WHERE h.guild_id = %s AND h.status = 'finished'
            )
            SELECT
                s.discord_id,
                u.username,
                u.display_name,
                s.best_mission_time_seconds,
                s.total_heists,
                s.total_earned,
                RANK() OVER (ORDER BY s.best_mission_time_seconds ASC) as rank
            FROM cayo_user_stats s
            INNER JOIN guild_users gu ON s.user_id = gu.user_id
            INNER JOIN users u ON s.user_id = u.id
            WHERE s.best_mission_time_seconds > 0
            ORDER BY s.best_mission_time_seconds ASC
            LIMIT %s
        """

        rows = await self.db.fetch(query, guild_id, limit)
        return [dict(row) for row in rows]

    # ==================== PROFIL PERSONNEL ====================

    async def get_user_profile(self, discord_id: int, guild_id: int) -> Optional[Dict]:
        """
        Récupère le profil complet d'un joueur.

        Returns:
            Dict avec toutes les stats de cayo_user_stats
        """
        self._ensure_db()

        # Vérifier que l'utilisateur a participé à au moins un braquage sur ce serveur
        check_query = """
            SELECT COUNT(*) as count
            FROM users u
            INNER JOIN cayo_participants cp ON u.id = cp.user_id
            INNER JOIN cayo_heists h ON cp.heist_id = h.id
            WHERE u.discord_id = %s AND h.guild_id = %s AND h.status = 'finished'
        """

        check_row = await self.db.fetchrow(check_query, discord_id, guild_id)
        if not check_row or check_row['count'] == 0:
            return None

        # Récupérer les stats complètes
        query = """
            SELECT
                s.discord_id,
                s.total_heists,
                s.avg_gain,
                s.avg_accuracy,
                s.total_earned,
                s.best_gain,
                s.first_heist,
                s.last_heist,
                s.elite_count,
                s.best_mission_time_seconds,
                s.avg_safe_amount,
                CAST(s.elite_count * 100.0 / NULLIF(s.total_heists, 0) AS INTEGER) as elite_rate_percent
            FROM cayo_user_stats s
            INNER JOIN users u ON s.user_id = u.id
            WHERE u.discord_id = %s
        """

        row = await self.db.fetchrow(query, discord_id)
        return dict(row) if row else None

    async def get_user_heist_history(self, discord_id: int, limit: int = 10) -> List[Dict]:
        """
        Récupère l'historique des braquages d'un joueur.

        Returns:
            Liste de dicts avec heist_id, primary_loot, hard_mode, predicted_gain,
            real_gain, difference, accuracy_percent, elite_challenge, finished_at
        """
        self._ensure_db()

        query = """
            SELECT
                h.id as heist_id,
                h.primary_loot,
                h.hard_mode,
                h.elite_challenge_completed,
                h.finished_at,
                h.mission_time_seconds,
                r.predicted_gain,
                r.real_gain,
                r.difference,
                r.accuracy_percent
            FROM cayo_results r
            INNER JOIN cayo_heists h ON r.heist_id = h.id
            INNER JOIN users u ON r.user_id = u.id
            WHERE u.discord_id = %s AND h.status = 'finished'
            ORDER BY h.finished_at DESC
            LIMIT %s
        """

        rows = await self.db.fetch(query, discord_id, limit)
        return [dict(row) for row in rows]

    async def get_user_stats_by_primary(self, discord_id: int) -> Dict[str, Dict]:
        """
        Récupère les statistiques d'un joueur par type d'objectif primaire.

        Returns:
            Dict avec {primary_type: {count, total_earned, avg_gain, elite_count}}
        """
        self._ensure_db()

        query = """
            SELECT
                h.primary_loot,
                COUNT(*) as count,
                SUM(r.real_gain) as total_earned,
                AVG(r.real_gain) as avg_gain,
                COUNT(CASE WHEN h.elite_challenge_completed THEN 1 END) as elite_count
            FROM cayo_results r
            INNER JOIN cayo_heists h ON r.heist_id = h.id
            INNER JOIN users u ON r.user_id = u.id
            WHERE u.discord_id = %s AND h.status = 'finished'
            GROUP BY h.primary_loot
            ORDER BY count DESC
        """

        rows = await self.db.fetch(query, discord_id)

        result = {}
        for row in rows:
            result[row['primary_loot']] = {
                'count': row['count'],
                'total_earned': row['total_earned'],
                'avg_gain': row['avg_gain'],
                'elite_count': row['elite_count']
            }

        return result

    async def get_user_rank(self, discord_id: int, guild_id: int, category: str) -> int:
        """
        Récupère la position d'un joueur dans un classement.

        Args:
            discord_id: ID Discord du joueur
            guild_id: ID du serveur
            category: Type de classement (total_earned, total_heists, avg_gain, etc.)

        Returns:
            Position du joueur (1 = premier), 0 si pas trouvé
        """
        self._ensure_db()

        # Mapper les catégories aux colonnes SQL
        column_map = {
            'total_earned': 's.total_earned DESC',
            'total_heists': 's.total_heists DESC',
            'avg_gain': 's.avg_gain DESC',
            'elite_count': 's.elite_count DESC',
            'speed_run': 's.best_mission_time_seconds ASC'
        }

        if category not in column_map:
            return 0

        order_clause = column_map[category]

        query = f"""
            WITH guild_users AS (
                SELECT DISTINCT u.id as user_id
                FROM users u
                INNER JOIN cayo_participants cp ON u.id = cp.user_id
                INNER JOIN cayo_heists h ON cp.heist_id = h.id
                WHERE h.guild_id = %s AND h.status = 'finished'
            ),
            ranked AS (
                SELECT
                    s.discord_id,
                    RANK() OVER (ORDER BY {order_clause}) as rank
                FROM cayo_user_stats s
                INNER JOIN guild_users gu ON s.user_id = gu.user_id
                WHERE s.total_heists > 0
            )
            SELECT rank
            FROM ranked
            WHERE discord_id = %s
        """

        row = await self.db.fetchrow(query, guild_id, discord_id)
        return row['rank'] if row else 0

    # ==================== COMPARAISON ====================

    async def compare_users(self, discord_id1: int, discord_id2: int, guild_id: int) -> Dict:
        """
        Compare les statistiques de deux joueurs.

        Returns:
            Dict avec {user1: stats, user2: stats}
        """
        self._ensure_db()

        user1_profile = await self.get_user_profile(discord_id1, guild_id)
        user2_profile = await self.get_user_profile(discord_id2, guild_id)

        return {
            'user1': user1_profile,
            'user2': user2_profile
        }

    # ==================== ANALYSES SERVEUR ====================

    async def get_server_activity_by_day(self, guild_id: int, days: int = 30) -> List[Dict]:
        """
        Récupère l'activité du serveur par jour (nombre de braquages/jour).

        Returns:
            Liste de dicts avec {date, count}
        """
        self._ensure_db()

        query = """
            SELECT
                DATE(finished_at) as date,
                COUNT(*) as count
            FROM cayo_heists
            WHERE guild_id = %s
              AND status = 'finished'
              AND finished_at >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(finished_at)
            ORDER BY date ASC
        """

        rows = await self.db.fetch(query, guild_id, days)
        return [dict(row) for row in rows]

    async def get_server_gains_by_week(self, guild_id: int, weeks: int = 12) -> List[Dict]:
        """
        Récupère les gains totaux du serveur par semaine.

        Returns:
            Liste de dicts avec {week_start, total_gains, total_heists}
        """
        self._ensure_db()

        query = """
            SELECT
                DATE_TRUNC('week', h.finished_at) as week_start,
                SUM(r.real_gain) as total_gains,
                COUNT(DISTINCT h.id) as total_heists
            FROM cayo_heists h
            INNER JOIN cayo_results r ON h.id = r.heist_id
            WHERE h.guild_id = %s
              AND h.status = 'finished'
              AND h.finished_at >= NOW() - INTERVAL '%s weeks'
            GROUP BY DATE_TRUNC('week', h.finished_at)
            ORDER BY week_start ASC
        """

        rows = await self.db.fetch(query, guild_id, weeks)
        return [dict(row) for row in rows]

    async def get_global_avg_safe_amount(self) -> int:
        """
        Récupère la moyenne globale des coffres-forts (tous joueurs, tous braquages).

        Cette valeur est utilisée pour les estimations de gains lors de la création
        d'un nouveau braquage, au lieu d'utiliser une valeur fixe.

        Returns:
            Moyenne des coffres-forts en GTA$, ou 60000 par défaut si aucune donnée
        """
        self._ensure_db()

        query = """
            SELECT AVG(safe_amount) as avg_safe
            FROM cayo_heists
            WHERE safe_amount IS NOT NULL
              AND safe_amount > 0
              AND status = 'finished'
        """

        row = await self.db.fetchrow(query)
        if row and row['avg_safe']:
            avg = int(row['avg_safe'])
            self.logger.info(f"[Stats] Moyenne globale du coffre-fort: {avg} GTA$")
            return avg

        self.logger.info("[Stats] Aucune donnée de coffre-fort, utilisation de la valeur par défaut: 60000 GTA$")
        return 60000  # Valeur par défaut

    # ==================== GESTION MESSAGES LEADERBOARD ====================

    async def save_leaderboard_message(
        self,
        guild_id: int,
        forum_channel_id: int,
        thread_id: int,
        message_id: int,
        leaderboard_type: str
    ) -> None:
        """
        Enregistre un message de leaderboard en base de données.

        Args:
            guild_id: ID du serveur Discord
            forum_channel_id: ID du forum channel
            thread_id: ID du thread
            message_id: ID du message
            leaderboard_type: Type de leaderboard (total_earned, etc.)
        """
        self._ensure_db()

        query = """
            INSERT INTO cayo_leaderboard_messages
                (guild_id, forum_channel_id, thread_id, message_id, leaderboard_type, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (guild_id, leaderboard_type)
            DO UPDATE SET
                forum_channel_id = EXCLUDED.forum_channel_id,
                thread_id = EXCLUDED.thread_id,
                message_id = EXCLUDED.message_id,
                updated_at = NOW()
        """

        await self.db.execute(query, guild_id, forum_channel_id, thread_id, message_id, leaderboard_type)
        self.logger.info(f"[Stats] Leaderboard message enregistré: {leaderboard_type} pour guild {guild_id}")

    async def get_leaderboard_message(self, guild_id: int, leaderboard_type: str) -> Optional[Dict]:
        """
        Récupère les informations d'un message de leaderboard.

        Returns:
            Dict avec forum_channel_id, thread_id, message_id, updated_at
        """
        self._ensure_db()

        query = """
            SELECT
                forum_channel_id,
                thread_id,
                message_id,
                updated_at
            FROM cayo_leaderboard_messages
            WHERE guild_id = %s AND leaderboard_type = %s
        """

        row = await self.db.fetchrow(query, guild_id, leaderboard_type)
        return dict(row) if row else None

    async def update_leaderboard_timestamp(self, guild_id: int, leaderboard_type: str) -> None:
        """Met à jour le timestamp de dernière mise à jour d'un leaderboard."""
        self._ensure_db()

        query = """
            UPDATE cayo_leaderboard_messages
            SET updated_at = NOW()
            WHERE guild_id = %s AND leaderboard_type = %s
        """

        await self.db.execute(query, guild_id, leaderboard_type)

    async def get_all_leaderboard_guilds(self) -> List[int]:
        """
        Récupère la liste de tous les guild_id ayant au moins un leaderboard configuré.

        Returns:
            Liste de guild_id
        """
        self._ensure_db()

        query = """
            SELECT DISTINCT guild_id
            FROM cayo_leaderboard_messages
            ORDER BY guild_id
        """

        rows = await self.db.fetch(query)
        return [row['guild_id'] for row in rows]
