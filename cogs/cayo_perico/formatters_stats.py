# cogs/cayo_perico/formatters_stats.py
"""
Formatage des embeds pour les statistiques et leaderboards Cayo Perico.
"""

import discord
from typing import List, Dict, Optional
from datetime import datetime, timezone
from .formatters import format_money
from .optimizer import PRIMARY_TARGETS


def format_leaderboard_embed(
    leaderboard_type: str,
    data: List[Dict],
    guild: discord.Guild
) -> discord.Embed:
    """
    Génère un embed pour un leaderboard.

    Args:
        leaderboard_type: Type de leaderboard (total_earned, total_heists, etc.)
        data: Liste de dicts avec les données du leaderboard
        guild: Serveur Discord

    Returns:
        Embed Discord formaté
    """

    # Configuration des leaderboards
    config = {
        "total_earned": {
            "title": "🏆 Top Gains Totaux",
            "description": "Les joueurs ayant gagné le plus d'argent",
            "color": discord.Color.gold()
        },
        "total_heists": {
            "title": "📊 Top Braquages Complétés",
            "description": "Les joueurs les plus actifs",
            "color": discord.Color.blue()
        },
        "avg_gain": {
            "title": "💎 Top Gains Moyens",
            "description": "Les joueurs avec le meilleur gain moyen (minimum 5 braquages)",
            "color": discord.Color.purple()
        },
        "elite_count": {
            "title": "⭐ Top Défi Elite",
            "description": "Les joueurs ayant réussi le plus de Défi Elite",
            "color": discord.Color.orange()
        },
        "speed_run": {
            "title": "⚡ Top Speed Run",
            "description": "Les temps de mission les plus rapides",
            "color": discord.Color.red()
        }
    }

    cfg = config.get(leaderboard_type, {
        "title": "Classement",
        "description": "",
        "color": discord.Color.gold()
    })

    embed = discord.Embed(
        title=cfg["title"],
        description=cfg["description"],
        color=cfg["color"],
        timestamp=datetime.now(timezone.utc)
    )

    if not data:
        embed.description = "Aucune donnée disponible pour ce classement."
        embed.set_footer(text=f"Mise à jour automatique • {guild.name}")
        return embed

    # Médailles pour le podium
    medals = ["🥇", "🥈", "🥉"]

    leaderboard_lines = []

    for idx, entry in enumerate(data):
        rank = entry.get("rank", idx + 1)
        medal = medals[idx] if idx < 3 else f"`#{rank}`"

        # Récupérer le membre Discord
        user = guild.get_member(entry["discord_id"])
        username = user.display_name if user else f"Utilisateur {entry['discord_id']}"

        # Formater selon le type de leaderboard
        if leaderboard_type == "total_earned":
            value = format_money(int(entry["total_earned"]))
            extra = f"({entry['total_heists']} braquages)"

        elif leaderboard_type == "total_heists":
            value = f"{entry['total_heists']} braquages"
            extra = f"({format_money(int(entry['total_earned']))} gagnés)"

        elif leaderboard_type == "avg_gain":
            value = format_money(int(entry["avg_gain"]))
            extra = f"({entry['total_heists']} braquages)"

        elif leaderboard_type == "elite_count":
            elite_count = entry['elite_count']
            elite_rate = entry.get('elite_rate_percent', 0)
            value = f"{elite_count} Elite"
            extra = f"({elite_rate}% de réussite)"

        elif leaderboard_type == "speed_run":
            seconds = entry["best_mission_time_seconds"]
            minutes = seconds // 60
            secs = seconds % 60
            if minutes > 0:
                value = f"{minutes}min {secs}s"
            else:
                value = f"{secs}s"
            extra = f"({entry['total_heists']} braquages)"

        else:
            value = "N/A"
            extra = ""

        line = f"{medal} **{username}** - {value} {extra}"
        leaderboard_lines.append(line)

    embed.description = "\n".join(leaderboard_lines)
    embed.set_footer(text=f"Mise à jour automatique toutes les heures • {guild.name}")

    return embed


def format_profile_embed(
    profile: Optional[Dict],
    history: List[Dict],
    stats_by_primary: Dict[str, Dict],
    rank: int,
    user: discord.User
) -> discord.Embed:
    """
    Génère un embed de profil personnel.

    Args:
        profile: Stats de l'utilisateur
        history: Historique des braquages (limité à 5)
        stats_by_primary: Stats par type d'objectif primaire
        rank: Position dans le classement total_earned
        user: Utilisateur Discord

    Returns:
        Embed Discord formaté
    """

    if not profile:
        embed = discord.Embed(
            title=f"📊 Profil Cayo Perico - {user.display_name}",
            description="Aucune donnée disponible pour cet utilisateur sur ce serveur.",
            color=discord.Color.light_grey()
        )
        return embed

    embed = discord.Embed(
        title=f"📊 Profil Cayo Perico - {user.display_name}",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )

    # Section: Résumé général
    total_earned_fmt = format_money(int(profile['total_earned']))
    avg_gain_fmt = format_money(int(profile['avg_gain']))

    rank_text = f"#{rank}" if rank > 0 else "N/A"

    summary = (
        f"💰 **Total gagné:** {total_earned_fmt}\n"
        f"📊 **Braquages complétés:** {profile['total_heists']}\n"
        f"💎 **Gain moyen:** {avg_gain_fmt}\n"
        f"🎯 **Précision moyenne:** {profile['avg_accuracy']:.1f}%\n"
        f"🏆 **Position serveur:** {rank_text}"
    )

    embed.add_field(name="📈 Résumé Général", value=summary, inline=False)

    # Section: Records personnels
    best_gain_fmt = format_money(int(profile['best_gain']))

    best_time_text = "N/A"
    if profile['best_mission_time_seconds'] > 0:
        seconds = profile['best_mission_time_seconds']
        minutes = seconds // 60
        secs = seconds % 60
        if minutes > 0:
            best_time_text = f"{minutes}min {secs}s"
        else:
            best_time_text = f"{secs}s"

    elite_rate = profile.get('elite_rate_percent', 0)

    # Moyenne du coffre-fort (uniquement en tant que leader)
    avg_safe = profile.get('avg_safe_amount')
    if avg_safe and avg_safe > 0:
        avg_safe_fmt = format_money(int(avg_safe))
    else:
        avg_safe_fmt = "N/A"

    records = (
        f"🌟 **Meilleur gain:** {best_gain_fmt}\n"
        f"⚡ **Temps le plus rapide:** {best_time_text}\n"
        f"💰 **Coffre-fort moyen:** {avg_safe_fmt}\n"
        f"⭐ **Elite Challenge:** {profile['elite_count']}/{profile['total_heists']} ({elite_rate}%)"
    )

    embed.add_field(name="🏅 Records Personnels", value=records, inline=False)

    # Section: Objectif préféré
    if stats_by_primary:
        # Trouver l'objectif le plus fréquent
        preferred = max(stats_by_primary.items(), key=lambda x: x[1]['count'])
        primary_key = preferred[0]
        primary_stats = preferred[1]

        primary_name = PRIMARY_TARGETS.get(primary_key, {}).get("name", primary_key)
        avg_gain_primary = format_money(int(primary_stats['avg_gain']))

        preferred_text = (
            f"🎯 **{primary_name}**\n"
            f"Joué {primary_stats['count']} fois • Gain moyen: {avg_gain_primary}"
        )

        embed.add_field(name="💼 Objectif Préféré", value=preferred_text, inline=False)

    # Section: Historique récent
    if history:
        history_lines = []
        for h in history[:5]:
            # Format date
            date_str = h['finished_at'].strftime("%d/%m")

            # Primary target
            primary_name = PRIMARY_TARGETS.get(h['primary_loot'], {}).get("name", h['primary_loot'])

            # Gain
            gain_fmt = format_money(int(h['real_gain']))

            # Elite emoji
            elite_emoji = "⭐" if h['elite_challenge_completed'] else ""

            # Hard mode emoji
            hard_emoji = "🔥" if h['hard_mode'] else ""

            line = f"`{date_str}` {primary_name[:15]} - {gain_fmt} {elite_emoji}{hard_emoji}"
            history_lines.append(line)

        embed.add_field(
            name="📜 Historique Récent",
            value="\n".join(history_lines),
            inline=False
        )

    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"Joueur depuis le {profile['first_heist'].strftime('%d/%m/%Y')}")

    return embed


def format_comparison_embed(
    user1: discord.User,
    user2: discord.User,
    comparison: Dict
) -> discord.Embed:
    """
    Génère un embed de comparaison entre deux joueurs.

    Args:
        user1: Premier utilisateur Discord
        user2: Deuxième utilisateur Discord
        comparison: Dict avec {user1: stats, user2: stats}

    Returns:
        Embed Discord formaté
    """

    profile1 = comparison.get('user1')
    profile2 = comparison.get('user2')

    embed = discord.Embed(
        title=f"⚔️ Comparaison",
        description=f"**{user1.display_name}** vs **{user2.display_name}**",
        color=discord.Color.purple(),
        timestamp=datetime.now(timezone.utc)
    )

    # Si un des joueurs n'a pas de données
    if not profile1:
        embed.add_field(
            name=f"❌ {user1.display_name}",
            value="Aucune donnée disponible",
            inline=True
        )
    if not profile2:
        embed.add_field(
            name=f"❌ {user2.display_name}",
            value="Aucune donnée disponible",
            inline=True
        )

    if not profile1 or not profile2:
        return embed

    # Helper pour déterminer le gagnant
    def winner_emoji(val1, val2, higher_is_better=True):
        if higher_is_better:
            if val1 > val2:
                return "🥇", "🥈"
            elif val2 > val1:
                return "🥈", "🥇"
        else:  # Lower is better (pour le temps)
            if val1 < val2 and val1 > 0:
                return "🥇", "🥈"
            elif val2 < val1 and val2 > 0:
                return "🥈", "🥇"
        return "", ""

    # Total gagné
    emoji1, emoji2 = winner_emoji(profile1['total_earned'], profile2['total_earned'])
    field1_lines = [
        f"{emoji1} **Total gagné:** {format_money(int(profile1['total_earned']))}",
        f"**Braquages:** {profile1['total_heists']}",
        f"**Gain moyen:** {format_money(int(profile1['avg_gain']))}",
        f"**Précision:** {profile1['avg_accuracy']:.1f}%",
        f"**Elite:** {profile1['elite_count']}"
    ]

    field2_lines = [
        f"{emoji2} **Total gagné:** {format_money(int(profile2['total_earned']))}",
        f"**Braquages:** {profile2['total_heists']}",
        f"**Gain moyen:** {format_money(int(profile2['avg_gain']))}",
        f"**Précision:** {profile2['avg_accuracy']:.1f}%",
        f"**Elite:** {profile2['elite_count']}"
    ]

    embed.add_field(
        name=f"👤 {user1.display_name}",
        value="\n".join(field1_lines),
        inline=True
    )

    embed.add_field(
        name=f"👤 {user2.display_name}",
        value="\n".join(field2_lines),
        inline=True
    )

    return embed


def format_server_stats_embed(
    guild: discord.Guild,
    total_heists: int,
    total_earned: int,
    total_players: int,
    avg_per_day: float
) -> discord.Embed:
    """
    Génère un embed de statistiques serveur.

    Args:
        guild: Serveur Discord
        total_heists: Nombre total de braquages
        total_earned: Total gagné par le serveur
        total_players: Nombre de joueurs uniques
        avg_per_day: Moyenne de braquages par jour

    Returns:
        Embed Discord formaté
    """

    embed = discord.Embed(
        title=f"📊 Statistiques {guild.name} - Cayo Perico",
        description="Activité des 30 derniers jours",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )

    stats_text = (
        f"🎯 **Braquages complétés:** {total_heists}\n"
        f"💰 **Total gagné:** {format_money(total_earned)}\n"
        f"👥 **Joueurs actifs:** {total_players}\n"
        f"📈 **Moyenne/jour:** {avg_per_day:.1f} braquages"
    )

    embed.add_field(name="📊 Statistiques Globales", value=stats_text, inline=False)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text=f"{guild.name}")

    return embed
