"""
Commandes pour le dashboard web.
"""
import discord
from discord import app_commands
from discord.ext import commands
from utils.logging_config import logger


class WebCommands(commands.Cog):
    """Cog pour les commandes liées au dashboard web."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("[WebCommands] Cog initialisé")

    @app_commands.command(name="dashboard", description="Obtenir le lien vers le dashboard web")
    async def dashboard_command(self, interaction: discord.Interaction):
        """Envoie le lien vers le dashboard web avec un embed stylisé."""

        # Créer un embed stylé GTA V
        embed = discord.Embed(
            title="🎮 Dashboard Web Cayo Perico",
            description="Consultez toutes vos statistiques de braquages en temps réel !",
            color=0x7CFC00  # Vert néon
        )

        # Ajouter les sections du dashboard
        embed.add_field(
            name="📊 Dashboard Principal",
            value="Statistiques globales, graphiques d'activité et gains",
            inline=False
        )
        embed.add_field(
            name="🏆 Classements",
            value="Top joueurs par gains, elite challenges, speed runs",
            inline=False
        )
        embed.add_field(
            name="🧮 Calculateur",
            value="Calculez vos gains potentiels avant le braquage",
            inline=False
        )

        # Lien vers le dashboard
        embed.add_field(
            name="🔗 Accéder au Dashboard",
            value="[**Cliquez ici pour ouvrir le dashboard**](http://localhost:8000)",
            inline=False
        )

        # Footer
        embed.set_footer(text="💡 Le dashboard se met à jour en temps réel !")

        # Thumbnail (si l'image existe)
        embed.set_thumbnail(url="attachment://lester.jpg")

        # Envoyer l'embed
        try:
            # Essayer d'envoyer avec l'image
            file = discord.File("web/static/images/lester.jpg", filename="lester.jpg")
            await interaction.response.send_message(embed=embed, file=file)
        except FileNotFoundError:
            # Si l'image n'existe pas, envoyer sans
            logger.warning("[WebCommands] Image lester.jpg introuvable, envoi sans image")
            embed.set_thumbnail(url=None)
            await interaction.response.send_message(embed=embed)

        logger.info(f"[WebCommands] Commande /dashboard utilisée par {interaction.user} dans {interaction.guild.name if interaction.guild else 'DM'}")


async def setup(bot: commands.Bot):
    """Charge le cog."""
    await bot.add_cog(WebCommands(bot))
    logger.info("[WebCommands] Cog chargé avec succès")
