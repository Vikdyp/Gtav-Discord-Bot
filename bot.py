# bot.py
"""
Point d'entrée principal du bot Discord.
Ce fichier gère uniquement le setup et le démarrage.
La logique métier est déléguée aux cogs et services.
"""

import asyncio
import sys
import platform
import warnings

from config import config
from core.bot_manager import BotManager
from utils.logging_config import logger

# Fix pour Windows: psycopg async nécessite SelectorEventLoop au lieu de ProactorEventLoop
if platform.system() == 'Windows':
    # Ignorer l'avertissement de dépréciation (fonctionnel jusqu'à Python 3.16)
    warnings.filterwarnings('ignore', category=DeprecationWarning, module='asyncio')
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    """
    Fonction principale pour démarrer le bot.
    """
    logger.info("Démarrage du bot Lester...")

    # Créer l'instance du bot
    bot = BotManager(intents=config.intents, db_config=config.database)

    try:
        # Démarrer le bot
        async with bot:
            await bot.start(config.token)
    except KeyboardInterrupt:
        logger.info("Arrêt du bot demandé par l'utilisateur (Ctrl+C)")
    except Exception as e:
        logger.exception(f"Erreur fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot arrêté")
