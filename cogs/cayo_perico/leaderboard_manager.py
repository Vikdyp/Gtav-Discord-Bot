# cogs/cayo_perico/leaderboard_manager.py
"""
Gestion des leaderboards auto-mis à jour dans les forums Discord.
"""

from typing import Dict, List
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.logging_config import logger
from .services.stats_service import CayoStatsService
from .formatters_stats import format_leaderboard_embed


class LeaderboardManager(commands.Cog):
    """Gère les leaderboards auto-mis à jour dans un forum."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.stats_service = CayoStatsService(getattr(bot, "db", None))
        self.logger = logger

        # Types de leaderboards avec configuration
        self.leaderboard_types = {
            "total_earned": {
                "name": "🏆 Top Gains Totaux",
                "description": "Les joueurs ayant gagné le plus d'argent"
            },
            "total_heists": {
                "name": "📊 Top Braquages Complétés",
                "description": "Les joueurs les plus actifs"
            },
            "avg_gain": {
                "name": "💎 Top Gains Moyens",
                "description": "Les meilleurs gains moyens (min. 5 braquages)"
            },
            "elite_count": {
                "name": "⭐ Top Défi Elite",
                "description": "Les champions du Défi Elite"
            },
            "speed_run": {
                "name": "⚡ Top Speed Run",
                "description": "Les temps de mission les plus rapides"
            }
        }

    async def cog_load(self):
        """Démarre les tâches périodiques au chargement du cog."""
        if self.stats_service.db is not None:
            self.update_leaderboards.start()
            self.logger.info("[Leaderboards] Tâche périodique démarrée (toutes les heures)")
        else:
            self.logger.warning("[Leaderboards] Base de données non disponible, tâche périodique non démarrée")

    async def cog_unload(self):
        """Arrête les tâches périodiques."""
        self.update_leaderboards.cancel()
        self.logger.info("[Leaderboards] Tâche périodique arrêtée")

    @tasks.loop(hours=1)
    async def update_leaderboards(self):
        """Met à jour tous les leaderboards toutes les heures."""
        self.logger.info("[Leaderboards] Début de la mise à jour automatique")

        try:
            # Récupérer tous les serveurs ayant des leaderboards configurés
            guild_ids = await self.stats_service.get_all_leaderboard_guilds()

            for guild_id in guild_ids:
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    self.logger.warning(f"[Leaderboards] Guild {guild_id} non trouvé")
                    continue

                try:
                    await self._update_guild_leaderboards(guild)
                except Exception as e:
                    self.logger.error(f"[Leaderboards] Erreur pour {guild.name}: {e}")

            self.logger.info("[Leaderboards] Mise à jour automatique terminée")

        except Exception as e:
            self.logger.error(f"[Leaderboards] Erreur globale lors de la mise à jour: {e}")

    @update_leaderboards.before_loop
    async def before_update_leaderboards(self):
        """Attend que le bot soit prêt avant de démarrer."""
        await self.bot.wait_until_ready()
        self.logger.info("[Leaderboards] Bot prêt, tâche de mise à jour en attente de démarrage")

    async def _update_guild_leaderboards(self, guild: discord.Guild):
        """
        Met à jour les leaderboards d'un serveur.

        Args:
            guild: Serveur Discord
        """

        for lb_type in self.leaderboard_types.keys():
            try:
                # Récupérer le message stocké en DB
                lb_msg_info = await self.stats_service.get_leaderboard_message(guild.id, lb_type)

                if not lb_msg_info:
                    continue  # Pas de leaderboard configuré pour ce type

                # Fetch le forum channel
                forum_channel = guild.get_channel(lb_msg_info['forum_channel_id'])
                if not forum_channel:
                    self.logger.warning(
                        f"[Leaderboards] Forum channel {lb_msg_info['forum_channel_id']} non trouvé pour {guild.name}"
                    )
                    continue

                if not isinstance(forum_channel, discord.ForumChannel):
                    self.logger.warning(
                        f"[Leaderboards] Channel {lb_msg_info['forum_channel_id']} n'est pas un ForumChannel"
                    )
                    continue

                # Fetch le thread
                thread = forum_channel.get_thread(lb_msg_info['thread_id'])
                if not thread:
                    # Essayer de fetch le thread
                    try:
                        thread = await forum_channel.fetch_channel(lb_msg_info['thread_id'])
                    except discord.NotFound:
                        self.logger.warning(
                            f"[Leaderboards] Thread {lb_msg_info['thread_id']} non trouvé pour {guild.name}"
                        )
                        continue

                # Fetch le message
                try:
                    message = await thread.fetch_message(lb_msg_info['message_id'])
                except discord.NotFound:
                    self.logger.warning(
                        f"[Leaderboards] Message {lb_msg_info['message_id']} non trouvé pour {guild.name}/{lb_type}"
                    )
                    continue

                # Récupérer les données du leaderboard
                data = await self._get_leaderboard_data(guild.id, lb_type)

                # Générer le nouvel embed
                embed = format_leaderboard_embed(lb_type, data, guild)

                # Mettre à jour le message
                await message.edit(embed=embed)

                # Update timestamp en DB
                await self.stats_service.update_leaderboard_timestamp(guild.id, lb_type)

                self.logger.info(f"[Leaderboards] {guild.name} - {lb_type} mis à jour")

            except Exception as e:
                self.logger.error(f"[Leaderboards] Erreur {lb_type} pour {guild.name}: {e}")

    async def _get_leaderboard_data(self, guild_id: int, lb_type: str) -> List[Dict]:
        """
        Récupère les données pour un type de leaderboard.

        Args:
            guild_id: ID du serveur
            lb_type: Type de leaderboard

        Returns:
            Liste de dicts avec les données du leaderboard
        """
        if lb_type == "total_earned":
            return await self.stats_service.get_top_total_earned(guild_id)
        elif lb_type == "total_heists":
            return await self.stats_service.get_top_total_heists(guild_id)
        elif lb_type == "avg_gain":
            return await self.stats_service.get_top_avg_gain(guild_id)
        elif lb_type == "elite_count":
            return await self.stats_service.get_top_elite_count(guild_id)
        elif lb_type == "speed_run":
            return await self.stats_service.get_top_speed_run(guild_id)
        return []

    @app_commands.command(
        name="cayo-leaderboard-setup",
        description="[Admin] Configurer les leaderboards Cayo Perico dans un forum"
    )
    @app_commands.describe(forum_channel="Canal forum où créer les leaderboards")
    @app_commands.default_permissions(administrator=True)
    async def setup_leaderboards(
        self,
        interaction: discord.Interaction,
        forum_channel: discord.ForumChannel
    ):
        """
        Crée les threads de leaderboard dans un forum.

        Args:
            interaction: Interaction Discord
            forum_channel: Forum Discord où créer les threads
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

        await interaction.response.defer(ephemeral=True)

        created_count = 0
        errors = []

        for lb_type, config in self.leaderboard_types.items():
            try:
                # Récupérer les données initiales
                data = await self._get_leaderboard_data(interaction.guild.id, lb_type)

                # Générer l'embed initial
                embed = format_leaderboard_embed(lb_type, data, interaction.guild)

                # Créer le thread avec le premier message
                thread, message = await forum_channel.create_thread(
                    name=config["name"],
                    content="**Leaderboard Cayo Perico**",
                    embed=embed,
                    auto_archive_duration=10080  # 7 jours
                )

                # Sauvegarder en DB
                await self.stats_service.save_leaderboard_message(
                    guild_id=interaction.guild.id,
                    forum_channel_id=forum_channel.id,
                    thread_id=thread.id,
                    message_id=message.id,
                    leaderboard_type=lb_type
                )

                created_count += 1
                self.logger.info(f"[Leaderboards] Thread créé: {config['name']} dans {forum_channel.name}")

            except Exception as e:
                self.logger.error(f"[Leaderboards] Erreur création {lb_type}: {e}")
                errors.append(f"{config['name']}: {str(e)[:50]}")

        # Réponse finale
        if created_count == len(self.leaderboard_types):
            await interaction.followup.send(
                f"✅ **{created_count}/{len(self.leaderboard_types)} leaderboards créés** dans {forum_channel.mention}\n\n"
                f"Les leaderboards seront mis à jour automatiquement toutes les heures.",
                ephemeral=True
            )
        else:
            error_msg = "\n".join(errors) if errors else "Erreurs inconnues"
            await interaction.followup.send(
                f"⚠️ **{created_count}/{len(self.leaderboard_types)} leaderboards créés**\n\n"
                f"**Erreurs:**\n{error_msg}",
                ephemeral=True
            )

    @app_commands.command(
        name="cayo-leaderboard-refresh",
        description="[Admin] Force la mise à jour immédiate de tous les leaderboards"
    )
    @app_commands.default_permissions(administrator=True)
    async def refresh_leaderboards(self, interaction: discord.Interaction):
        """
        Force la mise à jour immédiate de tous les leaderboards du serveur.

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

        await interaction.response.defer(ephemeral=True)

        try:
            await self._update_guild_leaderboards(interaction.guild)
            await interaction.followup.send(
                "✅ Leaderboards mis à jour avec succès !",
                ephemeral=True
            )
            self.logger.info(f"[Leaderboards] Mise à jour forcée pour {interaction.guild.name}")

        except Exception as e:
            self.logger.error(f"[Leaderboards] Erreur lors de la mise à jour forcée: {e}")
            await interaction.followup.send(
                f"❌ Une erreur s'est produite lors de la mise à jour.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Fonction appelée par discord.ext.commands pour charger le cog."""
    await bot.add_cog(LeaderboardManager(bot))
    logger.info("Cog LeaderboardManager chargé")
