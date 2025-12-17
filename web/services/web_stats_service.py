"""
Service web pour les statistiques Cayo Perico.
Wrapper autour de CayoStatsService pour le dashboard web.
"""
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ajouter le dossier parent pour importer les services du bot
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cogs.cayo_perico.services.stats_service import CayoStatsService
from cogs.cayo_perico.services.cayo_perico_service import CayoPericoService
from utils.database import Database
from utils.logging_config import logger


class WebStatsService:
    """Service pour les statistiques web du dashboard."""

    def __init__(self, db: Optional[Database]):
        self.db = db
        self.stats_service = CayoStatsService(db)
        self.cayo_service = CayoPericoService(db)
        self.logger = logger

    async def get_default_guild_id(self) -> Optional[int]:
        """
        Récupère le premier guild_id disponible dans la base de données.
        Utile quand il n'y a qu'un seul serveur Discord.
        """
        if self.db is None:
            return None

        query = """
            SELECT guild_id
            FROM cayo_heists
            WHERE status = 'finished'
            ORDER BY finished_at DESC
            LIMIT 1
        """

        try:
            row = await self.db.fetchrow(query)
            return row['guild_id'] if row else None
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du guild_id: {e}")
            return None

    async def get_dashboard_stats(self, guild_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Récupère toutes les statistiques nécessaires pour le dashboard principal.

        Returns:
            Dict contenant:
            - server_stats: Stats globales du serveur
            - leaderboards: Top 10 de chaque catégorie
            - recent_heists: 10 derniers braquages
        """
        if guild_id is None:
            guild_id = await self.get_default_guild_id()

        if guild_id is None:
            return {
                "server_stats": {},
                "leaderboards": {},
                "recent_heists": [],
                "error": "Aucune donnée disponible"
            }

        try:
            # Stats serveur
            server_stats = await self._get_server_stats(guild_id)

            # Leaderboards
            leaderboards = {
                "total_earned": await self.stats_service.get_top_total_earned(guild_id, limit=10),
                "total_heists": await self.stats_service.get_top_total_heists(guild_id, limit=10),
                "avg_gain": await self.stats_service.get_top_avg_gain(guild_id, limit=10),
                "elite_count": await self.stats_service.get_top_elite_count(guild_id, limit=10),
                "speed_run": await self.stats_service.get_top_speed_run(guild_id, limit=10),
            }

            # Braquages récents
            recent_heists = await self._get_recent_heists(guild_id, limit=10)

            return {
                "server_stats": server_stats,
                "leaderboards": leaderboards,
                "recent_heists": recent_heists,
                "guild_id": guild_id
            }

        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des stats dashboard: {e}")
            return {
                "server_stats": {},
                "leaderboards": {},
                "recent_heists": [],
                "error": str(e)
            }

    async def _get_server_stats(self, guild_id: int) -> Dict[str, Any]:
        """
        Récupère les statistiques globales du serveur.

        Note: Cette requête compte les statistiques UNIQUES par braquage, pas par participant.
        - total_heists: nombre de braquages uniques
        - total_earned: somme des gains totaux de tous les braquages (final_loot)
        - avg_gain: gain moyen par braquage
        - elite_completed: nombre de braquages avec elite challenge (pas de participations)
        """
        query = """
            SELECT
                COUNT(h.id) as total_heists,
                COALESCE(SUM(h.final_loot), 0) as total_earned,
                COALESCE(AVG(h.final_loot), 0) as avg_gain,
                COUNT(CASE WHEN h.elite_challenge_completed THEN 1 END) as elite_completed,
                COALESCE(AVG(h.mission_time_seconds), 0) as avg_mission_time
            FROM cayo_heists h
            WHERE h.guild_id = %s AND h.status = 'finished'
        """

        # Compter les joueurs uniques séparément pour éviter la cartesian product
        players_query = """
            SELECT COUNT(DISTINCT cp.user_id) as total_players
            FROM cayo_participants cp
            INNER JOIN cayo_heists h ON cp.heist_id = h.id
            WHERE h.guild_id = %s AND h.status = 'finished'
        """

        row = await self.db.fetchrow(query, guild_id)
        players_row = await self.db.fetchrow(players_query, guild_id)

        return {
            "total_heists": row['total_heists'] or 0,
            "total_players": players_row['total_players'] or 0,
            "total_earned": float(row['total_earned'] or 0),
            "avg_gain": float(row['avg_gain'] or 0),
            "elite_completed": row['elite_completed'] or 0,
            "avg_mission_time": float(row['avg_mission_time'] or 0)
        }

    async def _get_recent_heists(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les braquages récents avec détails."""
        query = """
            SELECT
                h.id,
                h.primary_loot,
                h.hard_mode,
                h.elite_challenge_completed,
                h.final_loot,
                h.mission_time_seconds,
                h.finished_at,
                u.discord_id as leader_discord_id,
                u.username as leader_username,
                u.display_name as leader_display_name,
                COUNT(cp.user_id) as player_count
            FROM cayo_heists h
            LEFT JOIN users u ON h.leader_user_id = u.id
            LEFT JOIN cayo_participants cp ON h.id = cp.heist_id
            WHERE h.guild_id = %s AND h.status = 'finished'
            GROUP BY h.id, u.discord_id, u.username, u.display_name
            ORDER BY h.finished_at DESC
            LIMIT %s
        """

        rows = await self.db.fetch(query, guild_id, limit)
        return [dict(row) for row in rows]

    async def get_user_profile(self, discord_id: int, guild_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Récupère le profil complet d'un utilisateur.

        Returns:
            Dict contenant:
            - profile: Stats du profil utilisateur
            - history: Historique des braquages
            - stats_by_primary: Stats par type de cible
            - rankings: Classements dans chaque catégorie
        """
        if guild_id is None:
            guild_id = await self.get_default_guild_id()

        if guild_id is None:
            return {"error": "Aucune donnée disponible"}

        try:
            # Profil utilisateur
            profile = await self.stats_service.get_user_profile(discord_id, guild_id)

            # Historique
            history = await self.stats_service.get_user_heist_history(discord_id, limit=20)

            # Stats par cible primaire
            stats_by_primary = await self.stats_service.get_user_stats_by_primary(discord_id)

            # Rankings
            rankings = {}
            for category in ["total_earned", "total_heists", "avg_gain", "elite_count", "speed_run"]:
                rank_data = await self.stats_service.get_user_rank(discord_id, guild_id, category)
                if rank_data:
                    rankings[category] = rank_data

            return {
                "profile": profile,
                "history": history,
                "stats_by_primary": stats_by_primary,
                "rankings": rankings,
                "discord_id": discord_id,
                "guild_id": guild_id
            }

        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du profil utilisateur: {e}")
            return {"error": str(e)}

    async def get_activity_data(self, guild_id: Optional[int] = None, days: int = 30) -> List[Dict[str, Any]]:
        """Récupère les données d'activité pour les graphiques."""
        if guild_id is None:
            guild_id = await self.get_default_guild_id()

        if guild_id is None:
            return []

        try:
            activity = await self.stats_service.get_server_activity_by_day(guild_id, days=days)
            return activity
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération de l'activité: {e}")
            return []

    async def get_gains_by_week(self, guild_id: Optional[int] = None, weeks: int = 12) -> List[Dict[str, Any]]:
        """Récupère les gains hebdomadaires pour les graphiques."""
        if guild_id is None:
            guild_id = await self.get_default_guild_id()

        if guild_id is None:
            return []

        try:
            gains = await self.stats_service.get_server_gains_by_week(guild_id, weeks=weeks)
            return gains
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des gains: {e}")
            return []
