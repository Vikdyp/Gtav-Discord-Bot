# cogs/cayo_perico/notification_manager.py
"""
Gestion des notifications automatiques pour les cooldowns Cayo Perico.
"""

from typing import List, Dict
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone, timedelta

from utils.logging_config import logger
from .services.cayo_perico_service import CayoPericoService


class NotificationManager(commands.Cog):
    """Gère les notifications de cooldown et hard mode."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = CayoPericoService(getattr(bot, "db", None))
        self.logger = logger

        # Cooldowns selon nombre de joueurs (en minutes)
        self.COOLDOWN_SOLO_MINUTES = 144  # 2h24 pour solo
        self.COOLDOWN_MULTI_MINUTES = 48  # 48min pour 2+ joueurs
        self.HARD_MODE_WINDOW_MINUTES = 48  # 48min window pour hard mode

    async def cog_load(self):
        """Démarre les tâches périodiques au chargement du cog."""
        if self.service.db is not None:
            self.check_cooldowns.start()
            self.logger.info("[Notifications] Tâche de vérification des cooldowns démarrée (toutes les 5 min)")
        else:
            self.logger.warning("[Notifications] Base de données non disponible, tâche non démarrée")

    async def cog_unload(self):
        """Arrête les tâches périodiques."""
        self.check_cooldowns.cancel()
        self.logger.info("[Notifications] Tâche de vérification des cooldowns arrêtée")

    @tasks.loop(minutes=5)
    async def check_cooldowns(self):
        """Vérifie les cooldowns expirés toutes les 5 minutes."""
        now = datetime.now(timezone.utc)

        try:
            # Récupérer les cooldowns actifs non notifiés
            cooldowns = await self._get_active_cooldowns()

            self.logger.info(f"[Notifications] Vérification de {len(cooldowns)} cooldowns actifs")

            for cooldown in cooldowns:
                try:
                    await self._process_cooldown(cooldown, now)
                except Exception as e:
                    self.logger.error(f"[Notifications] Erreur traitement cooldown {cooldown['id']}: {e}")

        except Exception as e:
            self.logger.error(f"[Notifications] Erreur globale lors de la vérification: {e}")

    @check_cooldowns.before_loop
    async def before_check_cooldowns(self):
        """Attend que le bot soit prêt avant de démarrer."""
        await self.bot.wait_until_ready()
        self.logger.info("[Notifications] Bot prêt, tâche de cooldown en attente de démarrage")

    async def _get_active_cooldowns(self) -> List[Dict]:
        """Récupère les cooldowns actifs depuis la DB."""
        if self.service.db is None:
            return []

        query = """
            SELECT
                ac.id,
                ac.heist_id,
                ac.leader_user_id,
                ac.guild_id,
                ac.finished_at,
                ac.num_players,
                ac.notified_cooldown,
                ac.notified_hardmode,
                u.discord_id as leader_discord_id
            FROM cayo_active_cooldowns ac
            JOIN users u ON ac.leader_user_id = u.id
            WHERE ac.notified_cooldown = false OR ac.notified_hardmode = false
        """

        rows = await self.service.db.fetch(query)
        return [dict(row) for row in rows]

    async def _process_cooldown(self, cooldown: Dict, now: datetime):
        """Traite un cooldown individuel."""

        # Calculer les timestamps
        cooldown_minutes = (self.COOLDOWN_SOLO_MINUTES if cooldown['num_players'] == 1
                          else self.COOLDOWN_MULTI_MINUTES)

        cooldown_end = cooldown['finished_at'] + timedelta(minutes=cooldown_minutes)
        hardmode_deadline = cooldown_end + timedelta(minutes=self.HARD_MODE_WINDOW_MINUTES)

        # Vérifier si l'utilisateur veut être notifié
        notify_prefs = await self._get_user_notification_prefs(
            cooldown['leader_user_id'],
            cooldown['guild_id']
        )

        # Notification cooldown terminé
        if not cooldown['notified_cooldown'] and now >= cooldown_end:
            if notify_prefs.get('notify_cooldown', True):
                await self._send_cooldown_notification(cooldown, cooldown_end, hardmode_deadline)

            # Marquer comme notifié
            await self._mark_cooldown_notified(cooldown['id'])

        # Notification deadline hard mode (10 min avant expiration)
        hardmode_warning = hardmode_deadline - timedelta(minutes=10)
        if not cooldown['notified_hardmode'] and now >= hardmode_warning and now < hardmode_deadline:
            if notify_prefs.get('notify_hardmode', True):
                await self._send_hardmode_notification(cooldown, hardmode_deadline)

            # Marquer comme notifié
            await self._mark_hardmode_notified(cooldown['id'])

    async def _send_cooldown_notification(self, cooldown: Dict, cooldown_end: datetime,
                                         hardmode_deadline: datetime):
        """Envoie une notification de cooldown terminé."""
        try:
            guild = self.bot.get_guild(cooldown['guild_id'])
            if not guild:
                return

            user = guild.get_member(cooldown['leader_discord_id'])
            if not user:
                return

            embed = discord.Embed(
                title="⏰ Cooldown Cayo Perico terminé !",
                description=f"Ton prochain braquage est maintenant disponible !",
                color=discord.Color.green(),
                timestamp=cooldown_end
            )

            embed.add_field(
                name="🔥 Mode Difficile",
                value=f"Active le mode difficile avant <t:{int(hardmode_deadline.timestamp())}:R> pour +10% de gains sur l'objectif primaire",
                inline=False
            )

            embed.add_field(
                name="ℹ️ Rappel",
                value="• Mode difficile : fenêtre de 48 min\n• Bonus : +100K GTA$ pour Elite Challenge",
                inline=False
            )

            embed.set_footer(text="Désactive avec /cayo-notify cooldown off")

            await user.send(embed=embed)
            self.logger.info(f"[Notifications] Cooldown envoyé à {user.display_name}")

        except discord.Forbidden:
            self.logger.warning(f"[Notifications] Impossible d'envoyer DM à {cooldown['leader_discord_id']}")
        except Exception as e:
            self.logger.error(f"[Notifications] Erreur envoi cooldown: {e}")

    async def _send_hardmode_notification(self, cooldown: Dict, hardmode_deadline: datetime):
        """Envoie une notification de deadline hard mode."""
        try:
            guild = self.bot.get_guild(cooldown['guild_id'])
            if not guild:
                return

            user = guild.get_member(cooldown['leader_discord_id'])
            if not user:
                return

            embed = discord.Embed(
                title="⚠️ Mode Difficile - Deadline proche !",
                description=f"Il te reste moins de 10 minutes pour lancer le braquage en mode difficile !",
                color=discord.Color.orange(),
                timestamp=hardmode_deadline
            )

            embed.add_field(
                name="⏱️ Expiration",
                value=f"Mode difficile expire <t:{int(hardmode_deadline.timestamp())}:R>",
                inline=False
            )

            embed.add_field(
                name="💡 Rappel",
                value="• Bonus mode difficile : +10% sur objectif primaire\n• Elite Challenge : +100K GTA$ au lieu de +50K",
                inline=False
            )

            embed.set_footer(text="Désactive avec /cayo-notify hardmode off")

            await user.send(embed=embed)
            self.logger.info(f"[Notifications] Hard mode deadline envoyée à {user.display_name}")

        except discord.Forbidden:
            self.logger.warning(f"[Notifications] Impossible d'envoyer DM à {cooldown['leader_discord_id']}")
        except Exception as e:
            self.logger.error(f"[Notifications] Erreur envoi hardmode: {e}")

    async def _get_user_notification_prefs(self, user_id: int, guild_id: int) -> Dict:
        """Récupère les préférences de notification d'un utilisateur."""
        if self.service.db is None:
            return {"notify_cooldown": True, "notify_hardmode": True}

        query = """
            SELECT notify_cooldown, notify_hardmode
            FROM cayo_user_notifications
            WHERE user_id = %s AND guild_id = %s
        """

        row = await self.service.db.fetchrow(query, user_id, guild_id)

        if row:
            return dict(row)
        else:
            # Par défaut, tout activé
            return {"notify_cooldown": True, "notify_hardmode": True}

    async def _mark_cooldown_notified(self, cooldown_id: int):
        """Marque un cooldown comme notifié."""
        if self.service.db is None:
            return

        query = """
            UPDATE cayo_active_cooldowns
            SET notified_cooldown = true
            WHERE id = %s
        """

        await self.service.db.execute(query, cooldown_id)

    async def _mark_hardmode_notified(self, cooldown_id: int):
        """Marque le hard mode comme notifié."""
        if self.service.db is None:
            return

        query = """
            UPDATE cayo_active_cooldowns
            SET notified_hardmode = true
            WHERE id = %s
        """

        await self.service.db.execute(query, cooldown_id)

    @app_commands.command(name="cayo-notify", description="Configurer les notifications Cayo Perico")
    @app_commands.describe(
        notification_type="Type de notification",
        enabled="Activer ou désactiver"
    )
    @app_commands.choices(notification_type=[
        app_commands.Choice(name="Cooldown terminé", value="cooldown"),
        app_commands.Choice(name="Deadline mode difficile", value="hardmode")
    ])
    async def configure_notifications(
        self,
        interaction: discord.Interaction,
        notification_type: str,
        enabled: bool
    ):
        """
        Configure les préférences de notification.

        Args:
            interaction: Interaction Discord
            notification_type: Type de notification (cooldown ou hardmode)
            enabled: True pour activer, False pour désactiver
        """

        if self.service.db is None:
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

        try:
            # Récupérer ou créer l'user_id
            user_id = await self.service.get_or_create_user_id(interaction.user.id)

            # Update ou insert
            query = """
                INSERT INTO cayo_user_notifications (user_id, guild_id, notify_cooldown, notify_hardmode)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, guild_id)
                DO UPDATE SET
                    notify_cooldown = CASE WHEN %s = 'cooldown' THEN %s ELSE cayo_user_notifications.notify_cooldown END,
                    notify_hardmode = CASE WHEN %s = 'hardmode' THEN %s ELSE cayo_user_notifications.notify_hardmode END,
                    updated_at = NOW()
            """

            await self.service.db.execute(
                query,
                user_id, interaction.guild.id,
                enabled if notification_type == 'cooldown' else True,
                enabled if notification_type == 'hardmode' else True,
                notification_type, enabled,
                notification_type, enabled
            )

            status = "activées" if enabled else "désactivées"
            notif_name = "de cooldown terminé" if notification_type == "cooldown" else "de deadline mode difficile"

            await interaction.response.send_message(
                f"✅ Notifications {notif_name} {status} !",
                ephemeral=True
            )

            self.logger.info(f"[Notifications] {interaction.user.display_name} a {status} les notifications {notif_name}")

        except Exception as e:
            self.logger.error(f"[Notifications] Erreur lors de la configuration: {e}")
            await interaction.response.send_message(
                "❌ Une erreur s'est produite lors de la configuration.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Fonction appelée par discord.ext.commands pour charger le cog."""
    await bot.add_cog(NotificationManager(bot))
    logger.info("Cog NotificationManager chargé")
