# config.py
"""
Configuration centralisée et typée du bot.
Utilise des dataclasses pour une meilleure validation et typage.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
import discord

# Charger les variables d'environnement
load_dotenv()


@dataclass
class DatabaseConfig:
    """Configuration de la base de données PostgreSQL"""

    user: str
    password: str
    host: str
    database: str
    port: int = 5432

    @classmethod
    def from_env(cls) -> "DatabaseConfig | None":
        """Crée la configuration de la base de données depuis les variables d'environnement"""
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        host = os.getenv("DB_HOST")
        database = os.getenv("DB_NAME")
        port_str = os.getenv("DB_PORT")

        # Si les variables essentielles ne sont pas définies, retourner None
        if not all([user, password, host, database]):
            return None

        port = int(port_str) if port_str else 5432

        return cls(
            user=user,
            password=password,
            host=host,
            database=database,
            port=port
        )


@dataclass
class BotConfig:
    """Configuration principale du bot Discord"""

    token: str
    intents: discord.Intents
    database: Optional[DatabaseConfig]

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
            intents=intents,
            database=DatabaseConfig.from_env()
        )


# Instance globale de configuration
config = BotConfig.from_env()
