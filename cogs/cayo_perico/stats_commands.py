# cogs/cayo_perico/stats_commands.py
"""
Commandes slash pour les statistiques Cayo Perico.
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
    generate_activity_chart,
    generate_gains_by_week_chart
)


class CayoStatsCommands(commands.GroupCog, name="cayo-stats"):
    """Commandes de statistiques Cayo Perico."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats_service = CayoStatsService(getattr(bot, "db", None))
        self.logger = logger
        super().__init__()

    @app_commands.command(name="profile", description="Voir le profil Cayo Perico d'un joueur")
    @app_commands.describe(user="Joueur à afficher (défaut: toi-même)")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        """
        Affiche le profil d'un joueur avec statistiques et graphique de progression.

        Args:
            interaction: Interaction Discord
            user: Utilisateur cible (optionnel, défaut = auteur de la commande)
        """
        # Vérifier que la base de données est disponible
        if self.stats_service.db is None:
            await interaction.response.send_message(
                "❌ La base de données n'est pas disponible.",
                ephemeral=True
            )
            return

        # Vérifier que la commande est utilisée dans un serveur
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Cette commande doit être utilisée dans un serveur.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        target_user = user or interaction.user

        try:
            # Récupérer les données
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

            # Générer l'embed
            embed = format_profile_embed(profile, history[:5], stats_by_primary, rank, target_user)

            # Générer le graphique de progression
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

        except Exception as e:
            self.logger.error(f"[Stats] Erreur lors de l'affichage du profil: {e}")
            await interaction.followup.send(
                f"❌ Une erreur s'est produite lors de la récupération du profil.",
                ephemeral=True
            )

    @app_commands.command(name="compare", description="Comparer deux joueurs")
    @app_commands.describe(
        user1="Premier joueur",
        user2="Deuxième joueur (défaut: toi-même)"
    )
    async def compare(
        self,
        interaction: discord.Interaction,
        user1: discord.User,
        user2: Optional[discord.User] = None
    ):
        """
        Compare les statistiques de deux joueurs.

        Args:
            interaction: Interaction Discord
            user1: Premier utilisateur
            user2: Deuxième utilisateur (optionnel, défaut = auteur de la commande)
        """
        if self.stats_service.db is None:
            await interaction.response.send_message(
                "❌ La base de données n'est pas disponible.",
                ephemeral=True
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Cette commande doit être utilisée dans un serveur.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        target_user2 = user2 or interaction.user

        try:
            # Récupérer les données de comparaison
            comparison = await self.stats_service.compare_users(
                user1.id, target_user2.id, interaction.guild.id
            )

            # Générer l'embed
            embed = format_comparison_embed(user1, target_user2, comparison)

            await interaction.followup.send(embed=embed)
            self.logger.info(f"[Stats] Comparaison affichée: {user1.display_name} vs {target_user2.display_name}")

        except Exception as e:
            self.logger.error(f"[Stats] Erreur lors de la comparaison: {e}")
            await interaction.followup.send(
                f"❌ Une erreur s'est produite lors de la comparaison.",
                ephemeral=True
            )

    @app_commands.command(name="server", description="Statistiques et graphiques du serveur")
    async def server(self, interaction: discord.Interaction):
        """
        Affiche les statistiques globales du serveur avec graphiques.

        Args:
            interaction: Interaction Discord
        """
        if self.stats_service.db is None:
            await interaction.response.send_message(
                "❌ La base de données n'est pas disponible.",
                ephemeral=True
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Cette commande doit être utilisée dans un serveur.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            # Récupérer l'activité journalière
            activity_data = await self.stats_service.get_server_activity_by_day(
                interaction.guild.id, days=30
            )

            # Calculer les stats globales
            total_heists = sum(d['count'] for d in activity_data)
            avg_per_day = total_heists / len(activity_data) if activity_data else 0

            # Compter les joueurs uniques ayant participé
            query_players = """
                SELECT COUNT(DISTINCT u.discord_id) as count
                FROM users u
                INNER JOIN cayo_participants cp ON u.id = cp.user_id
                INNER JOIN cayo_heists h ON cp.heist_id = h.id
                WHERE h.guild_id = %s AND h.status = 'finished'
            """
            row = await self.stats_service.db.fetchrow(query_players, interaction.guild.id)
            total_players = row['count'] if row else 0

            # Calculer le total gagné
            query_earned = """
                SELECT SUM(r.real_gain) as total
                FROM cayo_results r
                INNER JOIN cayo_heists h ON r.heist_id = h.id
                WHERE h.guild_id = %s AND h.status = 'finished'
            """
            row = await self.stats_service.db.fetchrow(query_earned, interaction.guild.id)
            total_earned = int(row['total']) if row and row['total'] else 0

            # Générer l'embed
            embed = format_server_stats_embed(
                interaction.guild,
                total_heists,
                total_earned,
                total_players,
                avg_per_day
            )

            # Générer le graphique d'activité
            chart_buffer = generate_activity_chart(activity_data)

            if chart_buffer:
                file = discord.File(chart_buffer, filename="activity.png")
                embed.set_image(url="attachment://activity.png")
                await interaction.followup.send(embed=embed, file=file)
                self.logger.info(f"[Stats] Statistiques serveur affichées pour {interaction.guild.name}")
            else:
                await interaction.followup.send(embed=embed)
                self.logger.info(f"[Stats] Statistiques serveur affichées (sans graphique)")

        except Exception as e:
            self.logger.error(f"[Stats] Erreur lors de l'affichage des stats serveur: {e}")
            await interaction.followup.send(
                f"❌ Une erreur s'est produite lors de la récupération des statistiques.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Fonction appelée par discord.ext.commands pour charger le cog."""
    await bot.add_cog(CayoStatsCommands(bot))
    logger.info("Cog CayoStatsCommands chargé")
