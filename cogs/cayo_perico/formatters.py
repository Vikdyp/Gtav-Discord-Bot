# cogs/cayo_perico/formatters.py
"""
Fonctions de formatage pour les messages et embeds du Cayo Perico.
"""

from typing import Dict, List
from .optimizer import PRIMARY_TARGETS, SECONDARY_TARGETS, BagPlan


def format_secondary_loot(secondary_loot: Dict[str, int]) -> str:
    """
    Formate les objectifs secondaires pour l'affichage.

    Args:
        secondary_loot: {"gold": 3, "cocaine": 2, ...}

    Returns:
        Chaîne formatée ex: "3x Or, 2x Cocaïne"
    """
    parts = []
    for loot_type, quantity in secondary_loot.items():
        if quantity > 0:
            name = SECONDARY_TARGETS[loot_type]["name"]
            parts.append(f"{quantity}x {name}")

    return ", ".join(parts) if parts else "Aucun"


def format_money(amount: int) -> str:
    """
    Formate un montant d'argent avec séparateurs.

    Args:
        amount: Montant en GTA$

    Returns:
        Chaîne formatée ex: "1 300 000 GTA$"
    """
    return f"{amount:,} GTA$".replace(",", " ")


def format_bag_plan_embed(bags: List[BagPlan], participants: List[int]) -> str:
    """
    Formate le plan de sac optimisé pour l'embed Discord.

    Args:
        bags: Plans de sac générés par optimize_bags()
        participants: Liste des discord_id des participants

    Returns:
        Texte formaté pour l'embed
    """
    if not bags:
        return "*Aucun objectif secondaire à répartir*"

    lines = []

    for bag in bags:
        player_idx = bag["player_index"]

        # Éviter l'index out of range
        if player_idx >= len(participants):
            mention = f"Joueur {player_idx + 1}"
        else:
            mention = f"<@{participants[player_idx]}>"

        lines.append(f"**{mention}**")

        if not bag["items"]:
            lines.append("  → Rien à prendre (pas de place ou plus de stock)")
        else:
            for item in bag["items"]:
                piles_str = f"{item['piles']}x" if item['piles'] != 1.0 else "1x"
                lines.append(
                    f"  • {piles_str} {item['name']} "
                    f"({item['clicks']} clics, {item['capacity']:.1f}%) "
                    f"= {format_money(item['value'])}"
                )

        lines.append(f"  💰 **Total : {format_money(bag['total_value'])}**")
        lines.append("")  # Ligne vide entre joueurs

    return "\n".join(lines)


def format_bag_plan_private(bag: BagPlan, player_number: int) -> str:
    """
    Formate le plan de sac pour un message privé envoyé à un joueur.

    Args:
        bag: Plan de sac du joueur
        player_number: Numéro du joueur (1, 2, 3...)

    Returns:
        Texte formaté pour DM
    """
    lines = [
        f"🎒 **Ton plan de sac (Joueur {player_number})**",
        "",
    ]

    if not bag["items"]:
        lines.append("Tu n'as rien à prendre dans les objectifs secondaires.")
        lines.append("(Pas assez de place ou plus de stock disponible)")
    else:
        lines.append("**À prendre dans ton sac :**")
        lines.append("")

        for item in bag["items"]:
            piles_str = f"{item['piles']}x" if item['piles'] != 1.0 else "1 pile"
            lines.append(f"• **{item['name']}** : {piles_str}")
            lines.append(f"  → {item['clicks']} clics")
            lines.append(f"  → {item['capacity']:.1f}% du sac")
            lines.append(f"  → Valeur : {format_money(item['value'])}")
            lines.append("")

        lines.append(f"💰 **Total estimé pour toi : {format_money(bag['total_value'])}**")

    return "\n".join(lines)


def format_results_comparison(
    predicted_gains: Dict[int, int],
    real_gains: Dict[int, int],
    participants: List[int]
) -> str:
    """
    Formate la comparaison gains prévus vs réels pour l'embed de résultats.

    Args:
        predicted_gains: {discord_id: montant_prévu}
        real_gains: {discord_id: montant_réel}
        participants: Liste des discord_id

    Returns:
        Texte formaté pour l'embed
    """
    lines = []

    total_predicted = 0
    total_real = 0

    for discord_id in participants:
        predicted = predicted_gains.get(discord_id, 0)
        real = real_gains.get(discord_id, 0)

        total_predicted += predicted
        total_real += real

        diff = real - predicted
        diff_percent = (diff / predicted * 100) if predicted > 0 else 0

        # Icône selon la précision
        if abs(diff_percent) < 5:
            icon = "✅"
        elif diff > 0:
            icon = "📈"
        else:
            icon = "📉"

        diff_str = f"+{diff:,}".replace(",", " ") if diff >= 0 else f"{diff:,}".replace(",", " ")
        diff_percent_str = f"+{diff_percent:.1f}%" if diff >= 0 else f"{diff_percent:.1f}%"

        lines.append(
            f"{icon} <@{discord_id}> : {format_money(real)} "
            f"(prévu : {format_money(predicted)}, "
            f"diff : {diff_str} GTA$ / {diff_percent_str})"
        )

    lines.append("")
    lines.append("**Total :**")

    total_diff = total_real - total_predicted
    total_diff_percent = (total_diff / total_predicted * 100) if total_predicted > 0 else 0

    total_icon = "✅" if abs(total_diff_percent) < 5 else ("📈" if total_diff > 0 else "📉")

    total_diff_str = f"+{total_diff:,}".replace(",", " ") if total_diff >= 0 else f"{total_diff:,}".replace(",", " ")
    total_diff_percent_str = f"+{total_diff_percent:.1f}%" if total_diff >= 0 else f"{total_diff_percent:.1f}%"

    lines.append(
        f"{total_icon} {format_money(total_real)} "
        f"(prévu : {format_money(total_predicted)}, "
        f"diff : {total_diff_str} GTA$ / {total_diff_percent_str})"
    )

    return "\n".join(lines)


def format_objectives_summary(
    primary_target: str,
    secondary_loot: Dict[str, int],
    hard_mode: bool,
    total_loot: int
) -> str:
    """
    Formate le résumé des objectifs pour l'embed.

    Args:
        primary_target: Clé de l'objectif principal
        secondary_loot: Quantités secondaires
        hard_mode: True si mode difficile
        total_loot: Butin total calculé

    Returns:
        Texte formaté
    """
    primary_info = PRIMARY_TARGETS[primary_target]

    lines = [
        f"**Principal :** {primary_info['name']} ({format_money(primary_info['value'])})",
        f"**Secondaires :** {format_secondary_loot(secondary_loot)}",
        f"**Mode difficile :** {'✅ Oui (+25%)' if hard_mode else '❌ Non'}",
        f"**Coffre-fort :** ~60 000 GTA$",
        "",
        f"💰 **Butin total estimé : {format_money(total_loot)}**"
    ]

    return "\n".join(lines)
