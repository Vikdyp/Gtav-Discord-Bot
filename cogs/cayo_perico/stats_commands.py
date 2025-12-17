# cogs/cayo_perico/stats_commands.py
"""
Commande slash unique pour les statistiques Cayo Perico.
"""

from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands

from utils.logging_config import logger
from .services.stats_service import CayoStatsService
from .formatters_stats import (
    format_profile_embed,
    format_comparison_embed,
    format_server_stats_embed
)
from .charts import (
    generate_progression_chart,
    generate_activity_chart
)


class CayoStatsCommands(commands.Cog):
    """Commande /cayo-stats regroupée (profil, comparaison, stats serveur)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats_service = CayoStatsService(getattr(bot, "db", None))
        self.logger = logger

    @app_commands.command(
        name="cayo-stats",
        description="Afficher les stats Cayo : profil, comparaison ou stats serveur"
    )
    @app_commands.describe(
        action="Type de stats à afficher",
        user="Joueur cible (pour profil ou comparaison)",
        user2="Deuxième joueur (pour comparaison)"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="profil", value="profile"),
            app_commands.Choice(name="compare", value="compare"),
            app_commands.Choice(name="server", value="server"),
        ]
    )
    async def stats(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        user: Optional[discord.User] = None,
        user2: Optional[discord.User] = None
    ):
        # Vérifier DB et guild
        if self.stats_service.db is None:
            await interaction.response.send_message("❌ La base de données n'est pas disponible.", ephemeral=True)
            return
        if not interaction.guild:
            await interaction.response.send_message("❌ Cette commande doit être utilisée dans un serveur.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            if action.value == "profile":
                await self._handle_profile(interaction, user or interaction.user)
            elif action.value == "compare":
                target1 = user or interaction.user
                target2 = user2 or interaction.user
                await self._handle_compare(interaction, target1, target2)
            else:  # server
                await self._handle_server(interaction)
        except Exception as e:
            self.logger.error(f"[Stats] Erreur action {action.value}: {e}")
            await interaction.followup.send("❌ Une erreur s'est produite lors de la récupération des statistiques.", ephemeral=True)

    async def _handle_profile(self, interaction: discord.Interaction, target_user: discord.User):
        profile = await self.stats_service.get_user_profile(target_user.id, interaction.guild.id)
        if not profile:
            await interaction.followup.send(
                f"❌ {target_user.display_name} n'a pas encore participé à de braquage Cayo Perico sur ce serveur.",
                ephemeral=True
            )
            return

        history = await self.stats_service.get_user_heist_history(target_user.id, limit=10)
        stats_by_primary = await self.stats_service.get_user_stats_by_primary(target_user.id)
        rank = await self.stats_service.get_user_rank(target_user.id, interaction.guild.id, "total_earned")

        embed = format_profile_embed(profile, history[:5], stats_by_primary, rank, target_user)

        if history:
            chart_buffer = generate_progression_chart(history, target_user.display_name)
            if chart_buffer:
                file = discord.File(chart_buffer, filename="progression.png")
                embed.set_image(url="attachment://progression.png")
                await interaction.followup.send(embed=embed, file=file)
                self.logger.info(f"[Stats] Profil affiché pour {target_user.display_name}")
                return

        await interaction.followup.send(embed=embed)
        self.logger.info(f"[Stats] Profil affiché pour {target_user.display_name} (sans graphique)")

    async def _handle_compare(self, interaction: discord.Interaction, user1: discord.User, user2: discord.User):
        comparison = await self.stats_service.compare_users(user1.id, user2.id, interaction.guild.id)
        embed = format_comparison_embed(user1, user2, comparison)
        await interaction.followup.send(embed=embed)
        self.logger.info(f"[Stats] Comparaison affichée: {user1.display_name} vs {user2.display_name}")

    async def _handle_server(self, interaction: discord.Interaction):
        activity_data = await self.stats_service.get_server_activity_by_day(interaction.guild.id, days=30)
        total_heists = sum(d['count'] for d in activity_data)
        avg_per_day = total_heists / len(activity_data) if activity_data else 0

        query_players = """
            SELECT COUNT(DISTINCT u.discord_id) as count
            FROM users u
            INNER JOIN cayo_participants cp ON u.id = cp.user_id
            INNER JOIN cayo_heists h ON cp.heist_id = h.id
            WHERE h.guild_id = %s AND h.status = 'finished'
        """
        row = await self.stats_service.db.fetchrow(query_players, interaction.guild.id)
        total_players = row['count'] if row else 0

        query_earned = """
            SELECT SUM(r.real_gain) as total
            FROM cayo_results r
            INNER JOIN cayo_heists h ON r.heist_id = h.id
            WHERE h.guild_id = %s AND h.status = 'finished'
        """
        row = await self.stats_service.db.fetchrow(query_earned, interaction.guild.id)
        total_earned = int(row['total']) if row and row['total'] else 0

        embed = format_server_stats_embed(
            interaction.guild,
            total_heists,
            total_earned,
            total_players,
            avg_per_day
        )

        chart_buffer = generate_activity_chart(activity_data)
        if chart_buffer:
            file = discord.File(chart_buffer, filename="activity.png")
            embed.set_image(url="attachment://activity.png")
            await interaction.followup.send(embed=embed, file=file)
            self.logger.info(f"[Stats] Statistiques serveur affichées pour {interaction.guild.name}")
        else:
            await interaction.followup.send(embed=embed)
            self.logger.info(f"[Stats] Statistiques serveur affichées (sans graphique)")


async def setup(bot: commands.Bot):
    """Fonction appelée par discord.ext.commands pour charger le cog."""
    await bot.add_cog(CayoStatsCommands(bot))
    logger.info("Cog CayoStatsCommands chargé")
