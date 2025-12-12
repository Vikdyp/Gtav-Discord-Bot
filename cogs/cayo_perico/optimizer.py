# cogs/cayo_perico/optimizer.py
"""
Algorithme d'optimisation pour le calculateur Cayo Perico.
Gère les constantes des butins et l'optimisation automatique des sacs.
"""

from typing import Dict, List, TypedDict


# ==================== CONSTANTES ====================

class PrimaryTarget(TypedDict):
    name: str
    value: int


class SecondaryTarget(TypedDict):
    name: str
    value: int
    weight: float    # Poids de l'item (détermine l'espace occupé dans le sac)
    capacity: float  # % du sac que prend 1 pile complète (pour compatibilité)
    clicks: int      # Nombre de clics pour prendre 1 pile complète (pour compatibilité)
    solo: bool       # True = accessible en solo, False = interdit en solo
    pickup_steps: List[float]  # Progression des clics (% de la pile)
    bag_capacity_steps: List[float]  # Capacité utilisée à chaque clic (% du sac)


PRIMARY_TARGETS: Dict[str, PrimaryTarget] = {
    "tequila": {"name": "Tequila", "value": 630000},
    "ruby_necklace": {"name": "Collier de Rubis", "value": 700000},
    "bearer_bonds": {"name": "Documents", "value": 770000},
    "pink_diamond": {"name": "Diamant rose", "value": 1300000},
    "panther_statue": {"name": "Statue de la panthère", "value": 1900000},
}

SECONDARY_TARGETS: Dict[str, SecondaryTarget] = {
    "gold": {
        "name": "Lingots d'or",
        "value": 330833,  # Moyenne 328333-333333
        "weight": 0.6666,
        "capacity": 66.66,
        "clicks": 7,
        "solo": False,
        "pickup_steps": [8.333, 25.0, 33.333, 50.0, 66.666, 83.333, 100.0],
        "bag_capacity_steps": [5.556, 16.667, 22.222, 33.333, 44.444, 55.556, 66.66]
    },
    "cocaine": {
        "name": "Cocaïne",
        "value": 200250,  # Moyenne 198000-202500
        "weight": 0.5,
        "capacity": 50.0,
        "clicks": 10,
        "solo": True,
        "pickup_steps": [11.111, 22.222, 31.111, 37.778, 42.222, 51.111, 64.444, 77.778, 95.556, 100.0],
        "bag_capacity_steps": [5.556, 11.111, 15.556, 18.889, 21.111, 25.556, 32.222, 38.889, 47.778, 50.0]
    },
    "paintings": {
        "name": "Tableaux",
        "value": 168750,  # Moyenne 157500-180000
        "weight": 0.5,
        "capacity": 50.0,
        "clicks": 1,
        "solo": False,
        "pickup_steps": [100.0],
        "bag_capacity_steps": [50.0]
    },
    "weed": {
        "name": "Cannabis",
        "value": 132750,  # Moyenne 130500-135000
        "weight": 0.375,
        "capacity": 37.5,
        "clicks": 10,
        "solo": True,
        "pickup_steps": [11.111, 22.222, 31.111, 37.778, 42.222, 51.111, 64.444, 77.778, 95.556, 100.0],
        "bag_capacity_steps": [4.167, 8.333, 11.667, 14.167, 15.833, 19.167, 24.167, 29.167, 35.833, 37.5]
    },
    "cash": {
        "name": "Argent",
        "value": 81000,  # Moyenne 78750-83250
        "weight": 0.25,
        "capacity": 25.0,
        "clicks": 10,
        "solo": False,
        "pickup_steps": [11.111, 22.222, 31.111, 37.778, 42.222, 51.111, 64.444, 77.778, 95.556, 100.0],
        "bag_capacity_steps": [2.778, 5.556, 7.778, 9.444, 10.556, 12.778, 16.111, 19.444, 23.889, 25.0]
    }
}

SAFE_VALUE = 59500  # Valeur moyenne du coffre-fort (20000-99000)
HARD_MODE_MULTIPLIER = 1.10  # Bonus mode difficile (+10%)

# Frais et déductions
PAVEL_FEE = 0.02  # 2%
CONTACT_FEE = 0.10  # 10%
TOTAL_FEES = PAVEL_FEE + CONTACT_FEE  # 12% total
NET_MULTIPLIER = 1.0 - TOTAL_FEES  # 0.88 (88% des gains)

# Bonus Défi Elite
ELITE_BONUS_NORMAL = 50000  # Bonus en mode normal
ELITE_BONUS_HARD = 100000  # Bonus en mode difficile

# Cooldown et timers
COOLDOWN_SOLO_MINUTES = 144  # 2h24 pour solo
COOLDOWN_MULTI_MINUTES = 48  # 48min pour 2+ joueurs
HARD_MODE_WINDOW_MINUTES = 48  # Fenêtre de 48min pour mode difficile

# Limites joueurs et parts
MAX_PLAYERS = 4
MIN_SHARE_PERCENT = 15
MAX_SHARE_PERCENT = 85
SHARE_INCREMENT = 5


# ==================== TYPES ====================

class BagItem(TypedDict):
    type: str
    name: str
    piles: float
    clicks: float  # Peut être fractionnaire pour le dernier clic
    capacity: float
    value: int


class BagPlan(TypedDict):
    player_index: int
    capacity_remaining: float
    items: List[BagItem]
    total_value: int


# ==================== FONCTIONS DE CALCUL ====================

def calculate_total_loot(
    primary_target: str,
    secondary_quantities: Dict[str, int],
    hard_mode: bool
) -> int:
    """
    Calcule le butin total estimé (OBSOLÈTE - utiliser calculate_estimated_loot à la place).

    ATTENTION : Cette fonction calcule le butin total DISPONIBLE, pas le butin réellement récupérable.
    Pour le butin estimé réel, utilisez calculate_estimated_loot() avec les sacs optimisés.

    Args:
        primary_target: Clé de l'objectif principal (ex: "pink_diamond")
        secondary_quantities: Quantités par type {"gold": 3, "cocaine": 2, ...}
        hard_mode: True si mode difficile activé

    Returns:
        Valeur totale en GTA$
    """
    primary_value = PRIMARY_TARGETS[primary_target]["value"]

    # Le mode difficile s'applique UNIQUEMENT sur l'objectif primaire
    if hard_mode:
        primary_value = int(primary_value * HARD_MODE_MULTIPLIER)

    secondary_value = sum(
        SECONDARY_TARGETS[loot_type]["value"] * qty
        for loot_type, qty in secondary_quantities.items()
        if qty > 0
    )

    total = primary_value + secondary_value + SAFE_VALUE

    return total


def find_closest_value(value: float, array: List[float]) -> int:
    """
    Trouve l'index de la valeur la plus proche dans pickup_steps.
    Retourne l'index + 1 (nombre de clics).

    Traduction exacte de la fonction JavaScript du projet de référence.

    Args:
        value: Valeur à chercher (pourcentage)
        array: Tableau de pickup_steps

    Returns:
        Nombre de clics (index + 1)
    """
    if value == 0:
        return 0

    # Trouver l'index avec la distance minimale
    distances = [abs(value - element) for element in array]
    closest_index = min(range(len(distances)), key=lambda i: distances[i])

    return closest_index + 1


def optimize_bags(
    secondary_loot: Dict[str, int],
    num_players: int,
    is_solo: bool = False,
    office_paintings: int = 0
) -> List[BagPlan]:
    """
    Optimise la répartition du butin secondaire dans les sacs des joueurs.

    Algorithme glouton : trie les ressources par valeur/% de sac décroissant,
    puis remplit les sacs un par un en prenant les meilleures ressources disponibles.

    Args:
        secondary_loot: Quantités disponibles {"gold": 3, "cocaine": 2, ...}
        num_players: Nombre de joueurs
        is_solo: True si un seul joueur (restreint certains loots)
        office_paintings: Nombre de tableaux dans le bureau (0-2, accessibles en solo)

    Returns:
        Liste de plans de sac, un par joueur
    """
    # 1. Préparer les items disponibles
    items = []
    for loot_type, quantity in secondary_loot.items():
        if quantity == 0:
            continue

        info = SECONDARY_TARGETS[loot_type]

        # Cas spécial : tableaux du bureau (accessibles en solo)
        if is_solo and loot_type == "paintings" and office_paintings > 0:
            # Séparer les tableaux en deux catégories :
            # - Ceux du bureau (accessibles en solo)
            # - Les autres (non accessibles en solo)
            office_count = min(office_paintings, quantity)
            other_count = quantity - office_count

            # Ajouter les tableaux du bureau (accessibles en solo)
            if office_count > 0:
                value_per_percent = info["value"] / info["capacity"]
                items.append({
                    "type": loot_type,
                    "name": f"{info['name']} (bureau)",
                    "total_quantity": office_count,
                    "remaining": float(office_count),
                    "value_per_pile": info["value"],
                    "capacity_per_pile": info["capacity"],
                    "clicks_per_pile": info["clicks"],
                    "value_per_percent": value_per_percent,
                })

            # Les autres tableaux ne sont pas accessibles en solo, donc on les ignore
            continue

        # Ignorer les items interdits en solo
        if is_solo and not info["solo"]:
            continue

        value_per_percent = info["value"] / info["capacity"]

        items.append({
            "type": loot_type,
            "name": info["name"],
            "total_quantity": quantity,
            "remaining": float(quantity),  # On peut prendre des fractions
            "value_per_pile": info["value"],
            "capacity_per_pile": info["capacity"],
            "clicks_per_pile": info["clicks"],
            "value_per_percent": value_per_percent,
        })

    # 2. Trier par valeur/% décroissant (meilleur d'abord)
    items.sort(key=lambda x: x["value_per_percent"], reverse=True)

    # 3. Remplir les sacs un par un
    bags: List[BagPlan] = []

    for player_idx in range(num_players):
        bag: BagPlan = {
            "player_index": player_idx,
            "capacity_remaining": 100.0,
            "items": [],
            "total_value": 0,
        }

        for item in items:
            # Si le sac est plein ou plus de stock
            if bag["capacity_remaining"] < 0.01:
                break
            if item["remaining"] <= 0:
                continue

            # === TRADUCTION EXACTE DU CODE JAVASCRIPT ===

            loot_info = SECONDARY_TARGETS[item["type"]]
            weight = loot_info["weight"]
            pickup_steps = loot_info["pickup_steps"]

            # === SPECIAL CASE: PAINTINGS (MUST BE WHOLE UNITS) ===
            if item["type"] == "paintings":
                # Each painting = 50% of bag capacity, must take whole paintings only
                max_paintings_by_space = int(bag["capacity_remaining"] / 50.0)
                max_paintings_by_stock = int(item["remaining"])
                paintings_to_take = min(max_paintings_by_space, max_paintings_by_stock)

                if paintings_to_take == 0:
                    continue

                # Calculate exact values for whole paintings
                capacity_used = paintings_to_take * 50.0
                value_gained = paintings_to_take * item["value_per_pile"]
                total_clicks = paintings_to_take * 4  # 1 click per painting, displayed as 4 cuts

                bag["items"].append({
                    "type": item["type"],
                    "name": item["name"],
                    "piles": float(paintings_to_take),  # Whole number only
                    "clicks": total_clicks,
                    "capacity": capacity_used,
                    "value": int(value_gained),
                })

                bag["capacity_remaining"] -= capacity_used
                bag["capacity_remaining"] = max(0, bag["capacity_remaining"])
                bag["total_value"] += int(value_gained)
                item["remaining"] -= paintings_to_take

                continue  # Skip normal processing for paintings

            # === NORMAL PROCESSING FOR OTHER LOOT TYPES ===

            # Calculer realFill (quantité réelle à prendre)
            # maxFill = combien on peut prendre max avec le stock disponible
            max_fill = item["remaining"] * weight

            # realFill = min(capacité restante, stock disponible)
            real_fill = min(bag["capacity_remaining"] / 100.0, max_fill)

            if real_fill < 0.01:
                continue

            # Calculer les clics (traduction exacte du JavaScript)
            # rest = partie fractionnaire en pourcentage
            piles = real_fill / weight
            full_piles = int(piles)
            rest = round((piles - full_piles) * 100, 3)

            # Clics = (piles complètes × nombre de clics par pile) + clics pour le reste
            total_clicks = full_piles * len(pickup_steps) + find_closest_value(rest, pickup_steps)

            # Correction +1 clic pour cocaine, cash, et weed (si multi-joueur)
            if total_clicks % 10 != 0:
                if item["type"] in ["cocaine", "cash"]:
                    total_clicks += 1
                elif item["type"] == "weed" and num_players > 1:
                    total_clicks += 1

            # Calculer la capacité utilisée
            # Utiliser weight × piles pour obtenir la capacité exacte
            capacity_used = real_fill * 100.0

            # Calculer la valeur
            piles_taken = real_fill / weight
            value_gained = piles_taken * item["value_per_pile"]

            # Filtrer les valeurs négligeables
            if value_gained < 100:
                continue

            # Clicks display (paintings are already handled above)
            clicks_display = total_clicks

            bag["items"].append({
                "type": item["type"],
                "name": item["name"],
                "piles": round(piles_taken, 2),
                "clicks": clicks_display,
                "capacity": round(capacity_used, 2),
                "value": int(value_gained),
            })

            bag["capacity_remaining"] -= capacity_used
            bag["capacity_remaining"] = max(0, bag["capacity_remaining"])
            bag["total_value"] += int(value_gained)
            item["remaining"] -= piles_taken

        bags.append(bag)

    return bags


# ==================== FONCTIONS UTILITAIRES ====================

def get_available_secondary_value(secondary_quantities: Dict[str, int], is_solo: bool = False) -> int:
    """
    Calcule la valeur totale des objectifs secondaires disponibles.

    Args:
        secondary_quantities: Quantités par type
        is_solo: True si solo (certains loots sont exclus)

    Returns:
        Valeur totale en GTA$
    """
    total = 0
    for loot_type, quantity in secondary_quantities.items():
        if quantity == 0:
            continue

        info = SECONDARY_TARGETS[loot_type]

        # Ignorer les items interdits en solo
        if is_solo and not info["solo"]:
            continue

        total += info["value"] * quantity

    return total


def get_recoverable_value(bags: List[BagPlan]) -> int:
    """
    Calcule la valeur totale récupérable dans les sacs optimisés.

    Args:
        bags: Plans de sac générés par optimize_bags()

    Returns:
        Valeur totale en GTA$
    """
    return sum(bag["total_value"] for bag in bags)


def calculate_loss(
    secondary_quantities: Dict[str, int],
    bags: List[BagPlan],
    is_solo: bool = False
) -> tuple[int, float]:
    """
    Calcule le butin perdu (non récupérable).

    Args:
        secondary_quantities: Quantités disponibles
        bags: Plans de sac optimisés
        is_solo: True si solo

    Returns:
        Tuple (perte_en_gta, perte_en_pourcentage)
    """
    available = get_available_secondary_value(secondary_quantities, is_solo)
    recoverable = get_recoverable_value(bags)

    loss = available - recoverable
    loss_percent = (loss / available * 100) if available > 0 else 0

    return loss, loss_percent


def calculate_estimated_loot(
    primary_target: str,
    bags: List[BagPlan],
    hard_mode: bool,
    safe_amount: int = None
) -> int:
    """
    Calcule le butin estimé RÉEL basé sur ce qui rentre dans les sacs optimisés.

    Args:
        primary_target: Clé de l'objectif principal
        bags: Plans de sac optimisés générés par optimize_bags()
        hard_mode: True si mode difficile (bonus +10% UNIQUEMENT sur primaire)
        safe_amount: Valeur du coffre-fort (si None, utilise la moyenne globale ou SAFE_VALUE par défaut)

    Returns:
        Valeur totale estimée en GTA$
    """
    primary_value = PRIMARY_TARGETS[primary_target]["value"]

    # Le mode difficile s'applique UNIQUEMENT sur l'objectif primaire
    if hard_mode:
        primary_value = int(primary_value * HARD_MODE_MULTIPLIER)

    # Somme des valeurs dans les sacs optimisés
    secondary_value = sum(bag["total_value"] for bag in bags)

    # Utiliser la valeur du coffre fournie, sinon la valeur par défaut
    safe_value = safe_amount if safe_amount is not None else SAFE_VALUE

    total = primary_value + secondary_value + safe_value

    return total


# ==================== NOUVELLES FONCTIONS V2 ====================


def calculate_default_shares(num_players: int, leader_index: int = 0) -> List[float]:
    """
    Calcule la répartition par défaut selon le nombre de joueurs.
    Avantage légèrement le leader (index 0) tout en respectant les incréments de 5%.

    Args:
        num_players: Nombre de joueurs (1-4)
        leader_index: Index du leader (par défaut 0)

    Returns:
        Liste de pourcentages [50.0, 50.0] pour 2 joueurs, etc.

    Examples:
        2 joueurs: [50.0, 50.0]
        3 joueurs: [40.0, 30.0, 30.0]
        4 joueurs: [40.0, 20.0, 20.0, 20.0]
    """
    if num_players == 1:
        return [100.0]
    elif num_players == 2:
        return [50.0, 50.0]
    elif num_players == 3:
        return [40.0, 30.0, 30.0]
    elif num_players == 4:
        return [40.0, 20.0, 20.0, 20.0]
    else:
        # Fallback: répartition égale
        equal_share = 100.0 / num_players
        return [equal_share] * num_players


def calculate_net_total(primary_value: int, secondary_value: int, safe_value: int = SAFE_VALUE) -> int:
    """
    Applique les frais Pavel (-2%) et Contact (-10%) sur le TOTAL BRUT.

    Args:
        primary_value: Valeur objectif primaire (avec bonus hard mode si applicable)
        secondary_value: Valeur des objectifs secondaires dans les sacs
        safe_value: Valeur du coffre-fort (60 000 GTA$ par défaut)

    Returns:
        Valeur nette totale après frais (88% du total brut)

    Formula:
        total_brut = primary + secondary + safe
        total_net = total_brut × 0.88
    """
    total_brut = primary_value + secondary_value + safe_value
    total_net = int(total_brut * NET_MULTIPLIER)
    return total_net


def calculate_player_gains(
    total_net: int,
    shares: List[float],
    elite_completed: bool,
    hard_mode: bool
) -> List[int]:
    """
    Calcule les gains individuels par joueur.

    Args:
        total_net: Valeur NETTE totale après frais Pavel/Contact (88% du brut)
        shares: Pourcentages par joueur [50.0, 50.0]
        elite_completed: True si défi Elite validé
        hard_mode: True si mode difficile (pour bonus Elite)

    Returns:
        Liste des gains par joueur en GTA$

    Formula:
        - Gain joueur = (total_net × share / 100) + bonus_elite
        - bonus_elite = 50 000 (normal) ou 100 000 (difficile) si validé
    """
    gains = []
    elite_bonus = ELITE_BONUS_HARD if hard_mode else ELITE_BONUS_NORMAL

    for share in shares:
        # Gain de base selon la part
        base_gain = int(total_net * share / 100.0)

        # Ajouter le bonus Elite si validé
        if elite_completed:
            base_gain += elite_bonus

        gains.append(base_gain)

    return gains


def format_next_heist_time(finished_at, num_players: int) -> str:
    """
    Calcule et formate le temps restant avant le prochain braquage avec timestamp Discord.

    Args:
        finished_at: datetime de fin du braquage (timezone-aware)
        num_players: Nombre de joueurs (1 = solo, 2+ = multi)

    Returns:
        "Disponible <t:timestamp:R>" ou "✅ Disponible maintenant"
    """
    from datetime import datetime, timezone, timedelta

    # Déterminer le cooldown
    cooldown_minutes = COOLDOWN_SOLO_MINUTES if num_players == 1 else COOLDOWN_MULTI_MINUTES

    # Calculer le moment où le prochain braquage sera disponible
    next_available = finished_at + timedelta(minutes=cooldown_minutes)

    # Temps restant
    now = datetime.now(timezone.utc)
    time_remaining = next_available - now

    if time_remaining.total_seconds() <= 0:
        return "✅ Disponible maintenant"

    # Timestamp Unix pour Discord
    timestamp = int(next_available.timestamp())
    return f"⏳ Disponible <t:{timestamp}:R>"


def format_hard_mode_deadline(finished_at, num_players: int) -> str:
    """
    Calcule et formate le temps restant pour le mode difficile avec timestamps Discord.

    Args:
        finished_at: datetime de fin du braquage (timezone-aware)
        num_players: Nombre de joueurs (1 = solo, 2+ = multi)

    Returns:
        "Mode difficile expire <t:timestamp:R>" ou "❌ Mode difficile expiré"
    """
    from datetime import datetime, timezone, timedelta

    # Le mode difficile est disponible pendant 48min APRÈS que le braquage soit à nouveau disponible
    cooldown_minutes = COOLDOWN_SOLO_MINUTES if num_players == 1 else COOLDOWN_MULTI_MINUTES
    next_available = finished_at + timedelta(minutes=cooldown_minutes)
    hard_mode_deadline = next_available + timedelta(minutes=HARD_MODE_WINDOW_MINUTES)

    # Temps restant
    now = datetime.now(timezone.utc)
    time_remaining = hard_mode_deadline - now

    if time_remaining.total_seconds() <= 0:
        return "❌ Mode difficile expiré"

    # Timestamps Unix pour Discord
    timestamp_available = int(next_available.timestamp())
    timestamp_deadline = int(hard_mode_deadline.timestamp())

    # Si le braquage n'est pas encore disponible, le mode difficile n'a pas encore commencé
    if now < next_available:
        return f"🔒 Mode difficile disponible <t:{timestamp_available}:R> (expire <t:{timestamp_deadline}:R>)"

    # Le mode difficile est actuellement disponible
    return f"⚡ Mode difficile expire <t:{timestamp_deadline}:R>"


def format_duration(start_time, end_time) -> str:
    """
    Formate une durée entre deux timestamps.

    Args:
        start_time: datetime de début
        end_time: datetime de fin

    Returns:
        Chaîne formatée "Xmin Ys" ou "XhYYmin"
    """
    if start_time is None or end_time is None:
        return "N/A"

    delta = end_time - start_time
    total_seconds = int(delta.total_seconds())

    if total_seconds < 0:
        return "N/A"

    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}h{minutes:02d}min"
    elif minutes > 0:
        return f"{minutes}min {seconds}s"
    else:
        return f"{seconds}s"
