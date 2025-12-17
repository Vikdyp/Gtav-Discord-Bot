# Dashboard Web Lester - Guide de Démarrage

Dashboard web pour visualiser les statistiques des braquages Cayo Perico.

## Installation

Les dépendances web sont déjà installées. Si nécessaire, réinstallez avec :

```bash
pip install -r web/requirements-web.txt
```

## Configuration

Le dashboard utilise les mêmes variables d'environnement que le bot Discord (`.env`). Aucune configuration supplémentaire n'est nécessaire.

Variables optionnelles dans `.env` :
- `WEB_HOST` : Host du serveur (défaut: `0.0.0.0`)
- `WEB_PORT` : Port du serveur (défaut: `8000`)
- `WEB_DEBUG` : Mode debug (défaut: `False`)

## Démarrage

### Option 1 : Lancement rapide
```bash
python web/app.py
```

### Option 2 : Avec Uvicorn (recommandé pour production)
```bash
uvicorn web.app:app --host 0.0.0.0 --port 8000
```

### Option 3 : Mode développement avec reload automatique
```bash
uvicorn web.app:app --reload --port 8000
```

Le dashboard sera accessible sur http://localhost:8000

## Structure du Dashboard

### Pages Disponibles

- **`/`** - Page d'accueil
- **`/dashboard`** - Dashboard principal avec statistiques et graphiques
- **`/leaderboards`** - Classements des joueurs (5 catégories)
- **`/calculator`** - Calculateur de gains Cayo Perico

### API Endpoints (JSON)

- **`/api/dashboard`** - Toutes les données du dashboard
- **`/api/leaderboard/{type}`** - Leaderboard spécifique
- **`/api/user/{discord_id}`** - Profil d'un utilisateur
- **`/api/activity?days=30`** - Données d'activité
- **`/api/gains?weeks=12`** - Gains hebdomadaires
- **`/health`** - Health check

## Fonctionnalités

### Dashboard Principal (`/dashboard`)
- 📊 Statistiques globales du serveur (6 cartes)
- 📈 Graphique d'activité (30 derniers jours)
- 💰 Graphique de gains hebdomadaires (12 semaines)
- 🏆 Top 5 joueurs (Total Gagné + Elite Challenges)
- 🕐 Braquages récents avec détails

### Leaderboards (`/leaderboards`)
- 💰 Total Gagné
- 📊 Total Braquages
- 📈 Gain Moyen (min 3 braquages)
- ⭐ Elite Challenges
- ⚡ Speed Run
- Top 50 joueurs par catégorie

### Calculateur (`/calculator`)
- Configuration complète du braquage
- Calcul en temps réel des gains
- Support du mode difficile
- Elite Challenge bonus
- Répartition par joueur

## Style

Le dashboard utilise un thème dark inspiré de GTA V avec :
- Couleurs style "préparation de braquage"
- Graphiques interactifs (Chart.js)
- Design responsive (mobile-friendly)
- Animations et effets de hover
- Format d'argent GTA$ français

## Image de Lester

⚠️ **Action requise** : Copiez l'image de Lester dans :
```
web/static/images/lester.jpg
```

Si l'image n'est pas présente, créez d'abord le dossier si nécessaire :
```bash
mkdir -p web/static/images
```

## Développement

### Structure des Fichiers

```
web/
├── app.py                  # Application FastAPI principale
├── config.py               # Configuration
├── routes/
│   ├── dashboard.py        # Routes HTML
│   └── api.py              # Routes API JSON
├── services/
│   └── web_stats_service.py # Service layer
├── templates/              # Templates Jinja2
│   ├── base.html
│   ├── index.html
│   ├── dashboard.html
│   ├── leaderboards.html
│   └── calculator.html
└── static/                 # Assets statiques
    ├── css/
    │   └── styles.css      # CSS style GTA
    ├── js/
    │   ├── main.js         # Utilitaires JS
    │   ├── charts.js       # Configuration Chart.js
    │   └── dashboard.js    # Logic dashboard
    └── images/
        └── lester.jpg      # Logo (à ajouter)
```

### Technologies

- **Backend** : FastAPI (Python 3.10+)
- **Frontend** : Jinja2 Templates + Vanilla JavaScript
- **Charts** : Chart.js 4.4.0
- **Database** : PostgreSQL (via utils/database.py)
- **Styling** : CSS Custom (style GTA V)

## Déploiement

### Même Serveur que le Bot

Le dashboard peut tourner sur le même serveur que le bot Discord :
- Ils partagent la même base de données
- Lancez-les dans deux terminaux séparés
- Port par défaut : 8000 (configurable)

### Serveur Séparé

Si vous déployez sur un serveur séparé :
1. Copiez le dossier `web/`
2. Copiez `utils/database.py` et `utils/logging_config.py`
3. Copiez les services `cogs/cayo_perico/services/`
4. Configurez les mêmes variables DB dans `.env`

## Notes

- ✅ Tout le dashboard est public (pas d'authentification)
- ✅ Les données sont en temps réel depuis la base de données
- ✅ Aucune modification du bot Discord nécessaire
- ✅ Les 22 indexes existants garantissent des performances optimales
- ✅ Le dashboard fonctionne même si le bot est éteint
