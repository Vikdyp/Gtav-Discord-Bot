# core/bot_manager.py
"""
Gestionnaire central du bot.
Gère le cycle de vie, le chargement des cogs et la synchronisation.
"""

from pathlib import Path
from typing import Optional
import os

import discord
from discord.ext import commands

from utils.logging_config import logger
from utils.database import Database
from config import DatabaseConfig
from utils.view_manager import init_persistent_views


class BotManager(commands.Bot):
    """
    Gestionnaire principal du bot Discord.
    Hérite de commands.Bot et ajoute des fonctionnalités de gestion avancées.
    """

    def __init__(self, intents: discord.Intents, db_config: Optional[DatabaseConfig]):
        """
        Initialise le gestionnaire du bot.

        Args:
            intents: Les intents Discord à utiliser
            db_config: Configuration de la base de données (optionnelle)
        """
        super().__init__(
            command_prefix="!",  # Prefix de fallback (on utilise surtout les slash commands)
            intents=intents,
            help_command=None  # Désactive le help command par défaut
        )

        self.logger = logger

        # Initialiser la base de données si la config est fournie
        if db_config:
            self.db = Database(
                user=db_config.user,
                password=db_config.password,
                host=db_config.host,
                database=db_config.database,
                port=db_config.port
            )
        else:
            self.db = None
            self.logger.warning("Configuration de base de données non fournie - Le bot fonctionnera sans DB")

    async def setup_hook(self):
        """
        Hook appelé pendant le setup du bot.
        Charge les cogs, initialise les vues persistantes et synchronise les commandes slash.
        """
        self.logger.info("Démarrage du setup du bot...")

        # -----------------------------
        # 1) Connexion DB
        # -----------------------------
        if self.db:
            self.logger.info("Connexion à la base de données PostgreSQL...")
            try:
                await self.db.connect()
                self.logger.info("Connexion à la base de données réussie")
            except Exception as e:
                self.logger.error(f"Erreur lors de la connexion à la base de données: {e}")
                self.logger.warning("Le bot va continuer sans connexion à la base de données")
                self.db = None
        else:
            self.logger.info("Aucune base de données configurée - Le bot démarre sans DB")

        # -----------------------------
        # 2) Charger tous les cogs
        # -----------------------------
        await self.load_all_cogs()

        # -----------------------------
        # 3) Initialiser les vues persistantes
        # -----------------------------
        # (Toutes les Views enregistrées via register_persistent_view()
        # seront recréées automatiquement ici)
        try:
            init_persistent_views(self)
            self.logger.info("Views persistantes initialisées")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation des views persistantes: {e}")

        # -----------------------------
        # 4) Synchronisation intelligente des slash commands
        # -----------------------------
        force_sync = os.getenv("FORCE_COMMAND_SYNC", "false").lower() == "true"
        disable_sync = os.getenv("DISABLE_COMMAND_SYNC", "false").lower() == "true"

        if disable_sync and not force_sync:
            self.logger.info("Sync des commandes d??sactiv?? (DISABLE_COMMAND_SYNC=true)")
            self.logger.info("Les commandes Discord d??j?? enregistr??es seront utilis??es")
            self.logger.info("Pour forcer le sync: d??finir FORCE_COMMAND_SYNC=true dans .env")
        else:
            if force_sync:
                self.logger.info("Synchronisation forc??e des commandes slash (FORCE_COMMAND_SYNC=true)...")
            else:
                self.logger.info("Synchronisation des commandes slash au d??marrage...")
            try:
                synced = await self.tree.sync()
                self.logger.info(f"{len(synced)} commande(s) slash synchronis??e(s)")
            except discord.HTTPException as e:
                if e.status == 429:
                    self.logger.warning("?s???? Rate limit?? lors du sync des commandes - commandes non synchronis??es")
                    self.logger.warning("Les commandes existantes seront utilis??es. R??essayez plus tard si n??cessaire.")
                else:
                    self.logger.error(f"Erreur HTTP lors de la synchronisation: {e}")
                    raise
            except Exception as e:
                self.logger.error(f"Erreur lors de la synchronisation des commandes: {e}")
                raise


    async def on_error(self, event: str, *args, **kwargs) -> None:
        """
        Gestionnaire global d'erreurs pour tous les events Discord.
        Empêche le crash du bot et log les erreurs détaillées.
        """
        import sys
        import traceback

        self.logger.error(f"❌ Erreur dans l'event {event}")
        self.logger.error("".join(traceback.format_exception(*sys.exc_info())))


    async def load_all_cogs(self):
        """
        Charge automatiquement tous les cogs depuis le dossier cogs/
        """
        cogs_dir = Path("cogs")

        if not cogs_dir.exists():
            self.logger.warning("Le dossier 'cogs' n'existe pas")
            return

        # Parcourir tous les sous-dossiers de cogs/
        for folder in cogs_dir.iterdir():
            if folder.is_dir() and not folder.name.startswith("__"):
                # Chercher les fichiers Python dans ce dossier
                for file in folder.iterdir():
                    if file.suffix == ".py" and not file.name.startswith("__"):
                        # Construire le chemin du module: cogs.folder.file
                        module_path = f"cogs.{folder.name}.{file.stem}"

                        try:
                            # Vérifier si le module a une fonction setup()
                            module = __import__(module_path, fromlist=['setup'])
                            if not hasattr(module, 'setup'):
                                # Ignorer les modules utilitaires (sans fonction setup)
                                continue

                            # Charger uniquement si setup() existe
                            await self.load_extension(module_path)
                            self.logger.info(
                                f"[OK] Cog chargé: {module_path}"
                            )
                        except Exception as e:
                            self.logger.error(
                                f"[ERREUR] Chargement de {module_path}: {e}"
                            )

    async def on_ready(self):
        """
        Event appelé quand le bot est prêt et connecté.
        """
        self.logger.info("=" * 50)
        self.logger.info(f"Bot connecté en tant que: {self.user.name} (ID: {self.user.id})")
        self.logger.info(f"Connecté à {len(self.guilds)} serveur(s)")
        self.logger.info("=" * 50)

        # Afficher les serveurs
        for guild in self.guilds:
            self.logger.info(f"  - {guild.name} (ID: {guild.id})")



    async def close(self):
        """
        Ferme proprement le bot et ses ressources.
        """
        self.logger.info("Fermeture du bot...")

        # Fermer la connexion à la base de données
        if self.db:
            self.logger.info("Fermeture de la connexion à la base de données...")
            await self.db.close()

        await super().close()
