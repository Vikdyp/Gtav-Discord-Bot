# cogs\general\admin_commands.py
import discord
from discord import app_commands
from discord.ext import commands
from cogs.general.services.admin_commands_service import TestEntryService
from utils.logging_config import logger
from typing import Optional

class GeneralCommands(commands.Cog):
    """Cog contenant les commandes générales du bot"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger
        self.db_service = TestEntryService(bot.db)

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
            f"Commande /ping utilisée par {interaction.user} (latence: {latency_ms}ms)"
        )

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
        await interaction.response.defer(thinking=True)

        if action.value == "test":
            try:
                row = await self.bot.db.fetchrow("SELECT 1;")
                await interaction.followup.send(embed=discord.Embed(
                    title="📡 Connexion PostgreSQL",
                    description=f"Connexion réussie : **{row[0]}**",
                    color=discord.Color.green()
                ))
                self.logger.info("[DB] Connexion PostgreSQL OK")
            except Exception as e:
                self.logger.error(f"[DB] Erreur PostgreSQL : {e}")
                await interaction.followup.send(embed=discord.Embed(
                    title="❌ Erreur PostgreSQL",
                    description=f"```\n{e}\n```",
                    color=discord.Color.red()
                ))
            return

        if action.value == "save":
            if not message:
                await interaction.followup.send(embed=discord.Embed(
                    title="⚠️ Paramètre manquant",
                    description="Tu dois fournir `message` pour l'action **save**.",
                    color=discord.Color.orange()
                ))
                return

            await self.db_service.ensure_table()
            user = interaction.user
            try:
                row = await self.db_service.insert_entry(user.id, str(user), message)
                entry_id, created_at = row["id"], row["created_at"]
                await interaction.followup.send(embed=discord.Embed(
                    title="✅ Donnée enregistrée",
                    description=(f"ID: **{entry_id}**\n"
                                 f"Utilisateur: **{user}**\n"
                                 f"Message: `{message}`\n"
                                 f"Date: `{created_at}`"),
                    color=discord.Color.green()
                ))
                self.logger.info(f"[DB] Entrée ajoutée id={entry_id} user={user} content={message}")
            except Exception as e:
                self.logger.error(f"[DB] Erreur insertion PostgreSQL : {e}")
                await interaction.followup.send(embed=discord.Embed(
                    title="❌ Erreur lors de l'insertion",
                    description=f"```\n{e}\n```",
                    color=discord.Color.red()
                ))
            return

        if action.value == "show":
            await self.db_service.ensure_table()
            try:
                rows = await self.db_service.get_recent_entries(limit=5)
                if not rows:
                    description = "Aucune entrée trouvée dans `test_entries`."
                else:
                    description = "\n".join(
                        f"**#{r['id']}** - {r['username']} - `{r['content']}` (_{r['created_at']}_)"
                        for r in rows
                    )
                await interaction.followup.send(embed=discord.Embed(
                    title="📄 Dernières entrées test_entries",
                    description=description,
                    color=discord.Color.blurple()
                ))
                self.logger.info("[DB] Lecture des dernières entrées test_entries")
            except Exception as e:
                self.logger.error(f"[DB] Erreur lecture PostgreSQL : {e}")
                await interaction.followup.send(embed=discord.Embed(
                    title="❌ Erreur lors de la lecture",
                    description=f"```\n{e}\n```",
                    color=discord.Color.red()
                ))
            return

async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCommands(bot))
    logger.info("Cog GeneralCommands chargé")
