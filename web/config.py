"""
Configuration pour le dashboard web
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class WebConfig:
    """Configuration pour l'application web"""
    host: str = os.getenv("WEB_HOST", "0.0.0.0")
    port: int = int(os.getenv("WEB_PORT", "8000"))
    debug: bool = os.getenv("WEB_DEBUG", "False").lower() == "true"

    # Database (réutilise les mêmes variables que le bot)
    db_user: Optional[str] = os.getenv("DB_USER")
    db_password: Optional[str] = os.getenv("DB_PASSWORD")
    db_host: Optional[str] = os.getenv("DB_HOST")
    db_name: Optional[str] = os.getenv("DB_NAME")
    db_port: int = int(os.getenv("DB_PORT", "5432"))

    @property
    def has_database(self) -> bool:
        """Vérifie si la configuration DB est complète"""
        return all([
            self.db_user,
            self.db_password,
            self.db_host,
            self.db_name
        ])


# Instance globale
web_config = WebConfig()
