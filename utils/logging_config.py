# utils/logging_config.py
"""
Configuration centralisée du système de logging.
"""

import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Formatter personnalisé avec couleurs pour la console"""

    # Codes couleurs ANSI
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Vert
        'WARNING': '\033[33m',    # Jaune
        'ERROR': '\033[31m',      # Rouge
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """Formate le message de log avec des couleurs"""
        # Ajouter la couleur au niveau de log
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Formater le message
        result = super().format(record)

        return result


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Configure le système de logging pour le bot.

    Args:
        level: Niveau de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logger configuré
    """
    # Créer le logger principal
    logger = logging.getLogger("lester")
    logger.setLevel(getattr(logging, level.upper()))

    # Éviter la duplication des handlers si déjà configuré
    if logger.handlers:
        return logger

    # Handler pour la console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    # Format: [2025-01-15 14:30:45] [INFO] [module] Message
    formatter = ColoredFormatter(
        fmt='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    # Ajouter le handler au logger
    logger.addHandler(console_handler)

    # Configurer aussi le logger de discord.py
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(logging.INFO)
    discord_logger.addHandler(console_handler)

    return logger


# Logger global pour le bot
logger = setup_logging()
