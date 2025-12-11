# cogs/cayo_perico/charts.py
"""
Génération de graphiques pour les statistiques Cayo Perico.
"""

import matplotlib
matplotlib.use('Agg')  # Backend non-interactif pour serveur

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
from typing import List, Dict, Optional
from datetime import datetime


def generate_progression_chart(history: List[Dict], username: str) -> Optional[BytesIO]:
    """
    Génère un graphique de progression des gains.

    Args:
        history: Liste de dicts avec {finished_at, real_gain}
        username: Nom du joueur (pour le titre)

    Returns:
        BytesIO contenant l'image PNG, ou None si pas de données
    """
    if not history:
        return None

    # Trier par date
    history = sorted(history, key=lambda x: x['finished_at'])

    dates = [h['finished_at'] for h in history]
    gains = [h['real_gain'] for h in history]

    # Créer le graphique
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor('#2B2D31')  # Fond Discord
    ax.set_facecolor('#2B2D31')

    # Tracer la ligne de progression
    ax.plot(dates, gains, marker='o', linestyle='-', linewidth=2.5,
            markersize=7, color='#5865F2', markerfacecolor='#5865F2',
            markeredgecolor='white', markeredgewidth=1.5)

    # Titre et labels
    ax.set_title(f"Progression des Gains - {username}",
                 fontsize=16, fontweight='bold', color='white', pad=20)
    ax.set_xlabel("Date", fontsize=12, color='white')
    ax.set_ylabel("Gains (GTA$)", fontsize=12, color='white')

    # Formater l'axe Y avec séparateurs de milliers
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'.replace(',', ' ')))

    # Formater l'axe X avec dates
    if len(dates) > 10:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %Hh'))

    plt.xticks(rotation=45, ha='right', color='white')
    plt.yticks(color='white')

    # Grille
    ax.grid(True, alpha=0.2, color='white', linestyle='--', linewidth=0.5)

    # Ajuster le layout
    fig.tight_layout()

    # Sauvegarder dans BytesIO
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    buffer.seek(0)
    plt.close(fig)

    return buffer


def generate_activity_chart(activity_data: List[Dict]) -> Optional[BytesIO]:
    """
    Génère un graphique d'activité du serveur (braquages par jour).

    Args:
        activity_data: Liste de dicts avec {date, count}

    Returns:
        BytesIO contenant l'image PNG, ou None si pas de données
    """
    if not activity_data:
        return None

    dates = [d['date'] for d in activity_data]
    counts = [d['count'] for d in activity_data]

    # Créer le graphique
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('#2B2D31')  # Fond Discord
    ax.set_facecolor('#2B2D31')

    # Barres avec couleur Discord
    bars = ax.bar(dates, counts, color='#5865F2', alpha=0.9, edgecolor='white', linewidth=1.2)

    # Ajouter les valeurs au-dessus des barres
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=9, color='white', fontweight='bold')

    # Titre et labels
    ax.set_title("Activité du Serveur - Braquages par Jour",
                 fontsize=16, fontweight='bold', color='white', pad=20)
    ax.set_xlabel("Date", fontsize=12, color='white')
    ax.set_ylabel("Nombre de Braquages", fontsize=12, color='white')

    # Formater l'axe X avec dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))

    if len(dates) > 20:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 20)))

    plt.xticks(rotation=45, ha='right', color='white')
    plt.yticks(color='white')

    # Grille horizontale uniquement
    ax.grid(True, axis='y', alpha=0.2, color='white', linestyle='--', linewidth=0.5)

    # Ajuster le layout
    fig.tight_layout()

    # Sauvegarder dans BytesIO
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    buffer.seek(0)
    plt.close(fig)

    return buffer


def generate_gains_by_week_chart(gains_data: List[Dict]) -> Optional[BytesIO]:
    """
    Génère un graphique des gains totaux par semaine.

    Args:
        gains_data: Liste de dicts avec {week_start, total_gains, total_heists}

    Returns:
        BytesIO contenant l'image PNG, ou None si pas de données
    """
    if not gains_data:
        return None

    weeks = [d['week_start'] for d in gains_data]
    gains = [d['total_gains'] for d in gains_data]

    # Créer le graphique
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor('#2B2D31')
    ax.set_facecolor('#2B2D31')

    # Line chart avec aire sous la courbe
    ax.plot(weeks, gains, marker='o', linestyle='-', linewidth=2.5,
            markersize=8, color='#57F287', markerfacecolor='#57F287',
            markeredgecolor='white', markeredgewidth=1.5, label='Gains hebdomadaires')

    ax.fill_between(weeks, gains, alpha=0.3, color='#57F287')

    # Titre et labels
    ax.set_title("Gains Totaux par Semaine",
                 fontsize=16, fontweight='bold', color='white', pad=20)
    ax.set_xlabel("Semaine", fontsize=12, color='white')
    ax.set_ylabel("Gains Totaux (GTA$)", fontsize=12, color='white')

    # Formater l'axe Y avec séparateurs de milliers
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'.replace(',', ' ')))

    # Formater l'axe X avec dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=max(1, len(weeks) // 12)))

    plt.xticks(rotation=45, ha='right', color='white')
    plt.yticks(color='white')

    # Grille
    ax.grid(True, alpha=0.2, color='white', linestyle='--', linewidth=0.5)

    # Légende
    ax.legend(loc='upper left', facecolor='#2B2D31', edgecolor='white', labelcolor='white')

    # Ajuster le layout
    fig.tight_layout()

    # Sauvegarder dans BytesIO
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight',
                facecolor=fig.get_facecolor(), edgecolor='none')
    buffer.seek(0)
    plt.close(fig)

    return buffer
