"""
Routes pour les pages HTML du dashboard.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(tags=["pages"])

# Templates
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Page du dashboard principal avec toutes les stats."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "Dashboard - Lester"
    })


@router.get("/leaderboards", response_class=HTMLResponse)
async def leaderboards_page(request: Request):
    """Page des leaderboards."""
    return templates.TemplateResponse("leaderboards.html", {
        "request": request,
        "title": "Leaderboards - Lester"
    })


@router.get("/calculator", response_class=HTMLResponse)
async def calculator_page(request: Request):
    """Page du calculateur de gains Cayo Perico."""
    return templates.TemplateResponse("calculator.html", {
        "request": request,
        "title": "Calculateur - Lester"
    })


@router.get("/profile/{discord_id}", response_class=HTMLResponse)
async def profile_page(request: Request, discord_id: int):
    """Page du profil d'un joueur."""
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "title": f"Profil - Lester",
        "discord_id": discord_id
    })
