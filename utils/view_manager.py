# utils/view_manager.py
"""
Gestion centralisée des Views persistantes (boutons qui survivent aux redémarrages).
"""

from typing import Callable, List

import discord
from discord.ext import commands

from utils.logging_config import logger

# Factory = fonction qui reçoit le bot et renvoie une instance de View
PersistentViewFactory = Callable[[commands.Bot], discord.ui.View]

_persistent_view_factories: List[PersistentViewFactory] = []


def register_persistent_view(factory: PersistentViewFactory) -> None:
    """
    Enregistre une factory de View persistante.
    À appeler côté Cog, au moment de la définition de la View.
    """
    _persistent_view_factories.append(factory)


def init_persistent_views(bot: commands.Bot) -> None:
    """
    À appeler UNE FOIS au démarrage du bot (après chargement des cogs et init DB).
    Crée et enregistre toutes les Views persistantes connues.
    """
    for factory in _persistent_view_factories:
        try:
            view = factory(bot)
            bot.add_view(view)
            logger.info(f"[Views] View persistante enregistrée: {view.__class__.__name__}")
        except Exception as e:
            logger.exception(f"[Views] Erreur lors de l'initialisation d'une view persistante: {e}")
