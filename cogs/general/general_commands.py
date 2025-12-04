# cogs/general/general_commands.py
"""
Commandes générales et utilitaires du bot.
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.logging_config import logger


class GeneralCommands(commands.Cog):
    """Cog contenant les commandes générales du bot"""

    def __init__(self, bot: commands.Bot):
        """
        Initialise le cog.

        Args:
            bot: Instance du bot
        """
        self.bot = bot
        self.logger = logger

    @app_commands.command(
        name="ping",
        description="Vérifie la latence du bot"
    )
    async def ping(self, interaction: discord.Interaction):
        """
        Commande /ping - Affiche la latence du bot.

        Args:
            interaction: L'interaction Discord
        """
        # Calculer la latence
        latency_ms = round(self.bot.latency * 1000)

        # Créer un embed pour la réponse
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latence: **{latency_ms}ms**",
            color=discord.Color.green()
        )

        # Répondre à l'interaction
        await interaction.response.send_message(embed=embed)

        self.logger.info(
            f"Commande /ping utilisée par {interaction.user} "
            f"(latence: {latency_ms}ms)"
        )
    
    @app_commands.command(
        name="dbtest",
        description="Teste la connexion à la base PostgreSQL"
    )
    async def dbtest(self, interaction: discord.Interaction):
        """Teste la connexion PostgreSQL via VLAN"""

        # Paramètres fournis par toi
        host = "postgresql"  # HOSTNAME VLAN
        user = "postgres"
        password = "postgres1234"
        dbname = "lesterbot"

        conn_string = (
            f"postgresql://{user}:{password}@{host}:5432/{dbname}"
        )

        try:
            # Tentative de connexion
            with psycopg.connect(conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    result = cur.fetchone()

            # Réponse Discord
            embed = discord.Embed(
                title="📡 Connexion PostgreSQL",
                description=f"Connexion réussie : **{result[0]}**",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

            self.logger.info("Connexion PostgreSQL OK")

        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur PostgreSQL",
                description=f"```\n{e}\n```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            self.logger.error(f"Erreur PostgreSQL : {e}")

async def setup(bot: commands.Bot):
    """
    Fonction appelée par discord.py pour charger le cog.

    Args:
        bot: Instance du bot
    """
    await bot.add_cog(GeneralCommands(bot))
    logger.info("Cog GeneralCommands chargé")
