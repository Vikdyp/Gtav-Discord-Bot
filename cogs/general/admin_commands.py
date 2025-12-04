# cogs/general/admin_commands.py
"""
Commandes générales et utilitaires du bot.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.logging_config import logger
from .services.admin_commands_service import AdminCommandsService


class GeneralCommands(commands.Cog):
    """Cog contenant les commandes générales du bot"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger

        # Service qui gère toute la logique DB
        # ⬇️ ICI : on réutilise la même instance Database que celle créée dans BotManager
        self.service = AdminCommandsService(getattr(bot, "db", None))

    # -------------------- COMMANDES --------------------

    @app_commands.command(
        name="ping",
        description="Vérifie la latence du bot"
    )
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latence: **{latency_ms}ms**",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

        self.logger.info(
            f"Commande /ping utilisée par {interaction.user} "
            f"(latence: {latency_ms}ms)"
        )

    # -------------------- COMMANDE DB UNIQUE --------------------

    @app_commands.command(
        name="db",
        description="Actions de test sur la base PostgreSQL"
    )
    @app_commands.describe(
        action="Que veux-tu faire ?",
        message="Message à enregistrer (pour l'action 'save')"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Tester la connexion", value="test"),
            app_commands.Choice(name="Enregistrer un message", value="save"),
            app_commands.Choice(name="Afficher les dernières entrées", value="show"),
        ]
    )
    async def db(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        message: Optional[str] = None,
    ):
        """
        Commande unique pour tester / écrire / lire dans la DB.
        La logique DB est déléguée à AdminCommandsService.
        """
        action_value = action.value

        # On évite de flood le temps de la requête
        await interaction.response.defer(thinking=True)

        # ---- ACTION: TEST ----
        if action_value == "test":
            try:
                result = await self.service.test_connection()

                embed = discord.Embed(
                    title="📡 Connexion PostgreSQL",
                    description=f"Connexion réussie : **{result}**",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Erreur PostgreSQL",
                    description=f"```\n{e}\n```",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                self.logger.error(f"[DB] Erreur PostgreSQL : {e}")
            return

        # ---- ACTION: SAVE ----
        if action_value == "save":
            if not message:
                embed = discord.Embed(
                    title="⚠️ Paramètre manquant",
                    description="Tu dois fournir `message` pour l'action **save**.",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
                return

            try:
                user = interaction.user
                entry_id, created_at = await self.service.save_message(
                    user_id=user.id,
                    username=str(user),
                    content=message,
                )

                embed = discord.Embed(
                    title="✅ Donnée enregistrée",
                    description=(
                        f"ID: **{entry_id}**\n"
                        f"Utilisateur: **{user}**\n"
                        f"Message: `{message}`\n"
                        f"Date: `{created_at}`"
                    ),
                    color=discord.Color.green()
                )

                await interaction.followup.send(embed=embed)

            except Exception as e:
                embed = discord.Embed(
                    title="❌ Erreur lors de l'insertion",
                    description=f"```\n{e}\n```",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                self.logger.error(f"[DB] Erreur insertion PostgreSQL : {e}")
            return

        # ---- ACTION: SHOW ----
        if action_value == "show":
            try:
                rows = await self.service.get_last_entries(limit=5)

                if not rows:
                    description = "Aucune entrée trouvée dans `test_entries`."
                else:
                    lines = []
                    for _id, username, content, created_at in rows:
                        lines.append(
                            f"**#{_id}** - {username} - `{content}` "
                            f"(_{created_at}_)"
                        )
                    description = "\n".join(lines)

                embed = discord.Embed(
                    title="📄 Dernières entrées test_entries",
                    description=description,
                    color=discord.Color.blurple()
                )

                await interaction.followup.send(embed=embed)

            except Exception as e:
                embed = discord.Embed(
                    title="❌ Erreur lors de la lecture",
                    description=f"```\n{e}\n```",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)
                self.logger.error(f"[DB] Erreur lecture PostgreSQL : {e}")
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCommands(bot))
    logger.info("Cog GeneralCommands chargé")
