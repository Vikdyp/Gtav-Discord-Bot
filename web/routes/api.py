"""
Routes API pour récupérer les données en JSON (pour AJAX).
"""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

from web.services.web_stats_service import WebStatsService

router = APIRouter(prefix="/api", tags=["api"])


def get_stats_service(request: Request) -> WebStatsService:
    """Helper pour obtenir le service de stats."""
    db = request.app.state.db
    return WebStatsService(db)


@router.get("/dashboard")
async def get_dashboard_data(request: Request, guild_id: Optional[int] = None):
    """
    Récupère toutes les données pour le dashboard principal.

    Returns:
        JSON avec server_stats, leaderboards, recent_heists
    """
    try:
        service = get_stats_service(request)
        data = await service.get_dashboard_stats(guild_id)

        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard/{leaderboard_type}")
async def get_leaderboard(
    request: Request,
    leaderboard_type: str,
    guild_id: Optional[int] = None,
    limit: int = 10
):
    """
    Récupère un leaderboard spécifique.

    Args:
        leaderboard_type: Type de leaderboard (total_earned, total_heists, avg_gain, elite_count, speed_run)
        guild_id: ID du serveur Discord (optionnel)
        limit: Nombre de joueurs à retourner (défaut: 10)
    """
    try:
        service = get_stats_service(request)

        if guild_id is None:
            guild_id = await service.get_default_guild_id()

        if guild_id is None:
            raise HTTPException(status_code=404, detail="Aucun serveur Discord trouvé")

        # Récupérer le leaderboard approprié
        leaderboard_methods = {
            "total_earned": service.stats_service.get_top_total_earned,
            "total_heists": service.stats_service.get_top_total_heists,
            "avg_gain": service.stats_service.get_top_avg_gain,
            "elite_count": service.stats_service.get_top_elite_count,
            "speed_run": service.stats_service.get_top_speed_run,
        }

        if leaderboard_type not in leaderboard_methods:
            raise HTTPException(status_code=400, detail=f"Type de leaderboard invalide: {leaderboard_type}")

        method = leaderboard_methods[leaderboard_type]
        data = await method(guild_id, limit=limit)

        return {
            "success": True,
            "data": data,
            "leaderboard_type": leaderboard_type
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{discord_id}")
async def get_user_profile(request: Request, discord_id: int, guild_id: Optional[int] = None):
    """
    Récupère le profil complet d'un utilisateur.

    Args:
        discord_id: ID Discord de l'utilisateur
        guild_id: ID du serveur Discord (optionnel)
    """
    try:
        service = get_stats_service(request)
        data = await service.get_user_profile(discord_id, guild_id)

        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])

        return {
            "success": True,
            "data": data
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activity")
async def get_activity_data(request: Request, guild_id: Optional[int] = None, days: int = 30):
    """
    Récupère les données d'activité pour les graphiques.

    Args:
        guild_id: ID du serveur Discord (optionnel)
        days: Nombre de jours d'historique (défaut: 30)
    """
    try:
        service = get_stats_service(request)
        data = await service.get_activity_data(guild_id, days)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gains")
async def get_gains_data(request: Request, guild_id: Optional[int] = None, days: int = 30):
    """
    Récupère les gains quotidiens pour les graphiques.

    Args:
        guild_id: ID du serveur Discord (optionnel)
        days: Nombre de jours d'historique (défaut: 30)
    """
    try:
        service = get_stats_service(request)
        data = await service.get_gains_by_day(guild_id, days)

        return {
            "success": True,
            "data": data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
