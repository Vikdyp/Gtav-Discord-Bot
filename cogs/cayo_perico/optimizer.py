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
    capacity: float  # % du sac que prend 1 pile complète
    clicks: int      # Nombre de clics pour prendre 1 pile complète
    solo: bool       # True = accessible en solo, False = interdit en solo


PRIMARY_TARGETS: Dict[str, PrimaryTarget] = {
    "tequila": {"name": "Tequila", "value": 630000},
    "ruby_necklace": {"name": "Collier de Rubis", "value": 700000},
    "bearer_bonds": {"name": "Documents", "value": 770000},
    "pink_diamond": {"name": "Diamant rose", "value": 1300000},
    "panther_statue": {"name": "Statue de la panthère", "value": 1900000},
}

SECONDARY_TARGETS: Dict[str, SecondaryTarget] = {
    "cash": {"name": "Argent", "value": 78750, "capacity": 25.0, "clicks": 10, "solo": False},
    "weed": {"name": "Cannabis", "value": 130500, "capacity": 37.5, "clicks": 10, "solo": True},
    "paintings": {"name": "Tableaux", "value": 157500, "capacity": 50.0, "clicks": 1, "solo": False},
    "cocaine": {"name": "Cocaïne", "value": 198000, "capacity": 50.0, "clicks": 10, "solo": True},
    "gold": {"name": "Lingots d'or", "value": 328333, "capacity": 66.65, "clicks": 7, "solo": False},
}

SAFE_VALUE = 60000  # Valeur fixe du coffre-fort
HARD_MODE_MULTIPLIER = 1.25  # Bonus mode difficile


# ==================== TYPES ====================

class BagItem(TypedDict):
    type: str
    name: str
    piles: float
    clicks: int
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


def optimize_bags(
    secondary_loot: Dict[str, int],
    num_players: int,
    is_solo: bool = False
) -> List[BagPlan]:
    """
    Optimise la répartition du butin secondaire dans les sacs des joueurs.

    Algorithme glouton : trie les ressources par valeur/% de sac décroissant,
    puis remplit les sacs un par un en prenant les meilleures ressources disponibles.

    Args:
        secondary_loot: Quantités disponibles {"gold": 3, "cocaine": 2, ...}
        num_players: Nombre de joueurs
        is_solo: True si un seul joueur (restreint certains loots)

    Returns:
        Liste de plans de sac, un par joueur
    """
    # 1. Préparer les items disponibles
    items = []
    for loot_type, quantity in secondary_loot.items():
        if quantity == 0:
            continue

        info = SECONDARY_TARGETS[loot_type]

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
            # Si le sac est plein ou plus de stock, passer
            if bag["capacity_remaining"] < 0.01:
                break
            if item["remaining"] <= 0:
                continue

            # Calculer combien de piles on peut prendre
            piles_possible_capacity = bag["capacity_remaining"] / item["capacity_per_pile"]
            piles_possible_stock = item["remaining"]
            piles_to_take = min(piles_possible_capacity, piles_possible_stock)

            if piles_to_take < 0.01:
                continue

            # Prendre les piles
            capacity_used = piles_to_take * item["capacity_per_pile"]
            value_gained = piles_to_take * item["value_per_pile"]
            clicks_needed = int(piles_to_take * item["clicks_per_pile"])

            bag["items"].append({
                "type": item["type"],
                "name": item["name"],
                "piles": round(piles_to_take, 2),
                "clicks": clicks_needed,
                "capacity": round(capacity_used, 2),
                "value": int(value_gained),
            })

            bag["capacity_remaining"] -= capacity_used
            bag["capacity_remaining"] = max(0, bag["capacity_remaining"])  # Éviter les négatifs
            bag["total_value"] += int(value_gained)
            item["remaining"] -= piles_to_take

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
    hard_mode: bool
) -> int:
    """
    Calcule le butin estimé RÉEL basé sur ce qui rentre dans les sacs optimisés.

    Args:
        primary_target: Clé de l'objectif principal
        bags: Plans de sac optimisés générés par optimize_bags()
        hard_mode: True si mode difficile (bonus +25% UNIQUEMENT sur primaire)

    Returns:
        Valeur totale estimée en GTA$
    """
    primary_value = PRIMARY_TARGETS[primary_target]["value"]

    # Le mode difficile s'applique UNIQUEMENT sur l'objectif primaire
    if hard_mode:
        primary_value = int(primary_value * HARD_MODE_MULTIPLIER)

    # Somme des valeurs dans les sacs optimisés
    secondary_value = sum(bag["total_value"] for bag in bags)

    total = primary_value + secondary_value + SAFE_VALUE

    return total
