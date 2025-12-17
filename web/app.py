"""
Application web FastAPI pour le dashboard Cayo Perico
"""
import sys
from pathlib import Path

# Ajouter le dossier parent au path pour pouvoir importer utils et config
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import logging

from utils.database import Database
from utils.logging_config import logger
from web.config import web_config

# Application FastAPI
app = FastAPI(
    title="Lester - Dashboard Cayo Perico",
    description="Dashboard web pour les statistiques de braquages Cayo Perico",
    version="1.0.0"
)

# Configuration des templates et static files
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.on_event("startup")
async def startup_event():
    """Initialisation au démarrage de l'application"""
    logger.info("Demarrage du dashboard web Lester...")

    # Connexion à la base de données
    if web_config.has_database:
        try:
            db = Database(
                user=web_config.db_user,
                password=web_config.db_password,
                host=web_config.db_host,
                database=web_config.db_name,
                port=web_config.db_port
            )
            await db.connect()
            app.state.db = db
            logger.info("Connexion a la base de donnees reussie")
        except Exception as e:
            logger.error(f"Erreur de connexion a la base de donnees: {e}")
            logger.warning("Le dashboard fonctionnera sans acces a la base de donnees")
            app.state.db = None
    else:
        logger.warning("Configuration de base de donnees manquante")
        app.state.db = None


@app.on_event("shutdown")
async def shutdown_event():
    """Nettoyage à l'arrêt de l'application"""
    logger.info("Arret du dashboard web...")

    if hasattr(app.state, "db") and app.state.db:
        try:
            await app.state.db.close()
            logger.info("Connexion a la base de donnees fermee")
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la DB: {e}")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Page d'accueil"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Lester - Dashboard Cayo Perico"
    })


@app.get("/health")
async def health_check():
    """Endpoint de santé pour vérifier que l'API fonctionne"""
    db_status = "disconnected"
    if hasattr(app.state, "db") and app.state.db and app.state.db._connected:
        db_status = "connected"

    return {
        "status": "healthy",
        "database": db_status,
        "version": "1.0.0"
    }


# Import des routes
from web.routes import dashboard, api

app.include_router(dashboard.router)
app.include_router(api.router)


if __name__ == "__main__":
    import uvicorn
    import asyncio
    import sys

    # Fix Windows event loop for psycopg (comme dans bot.py)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logger.info(f"Lancement du serveur sur http://{web_config.host}:{web_config.port}")
    uvicorn.run(
        "app:app",
        host=web_config.host,
        port=web_config.port,
        reload=web_config.debug
    )
