# config.py
"""
Configuration centralisée et typée du bot.
Utilise des dataclasses pour une meilleure validation et typage.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv
import discord

# Charger les variables d'environnement
load_dotenv()


@dataclass
class BotConfig:
    """Configuration principale du bot Discord"""

    token: str
    intents: discord.Intents

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Crée la configuration depuis les variables d'environnement"""
        token = os.getenv("BOT_TOKEN")

        if not token:
            raise ValueError("BOT_TOKEN n'est pas défini dans le fichier .env")

        # Configuration des intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True

        return cls(
            token=token,
            intents=intents
        )


# Instance globale de configuration
config = BotConfig.from_env()
