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


async def setup(bot: commands.Bot):
    """
    Fonction appelée par discord.py pour charger le cog.

    Args:
        bot: Instance du bot
    """
    await bot.add_cog(GeneralCommands(bot))
    logger.info("Cog GeneralCommands chargé")
