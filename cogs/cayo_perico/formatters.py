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
        f"**Mode difficile :** {'✅ Oui (+10%)' if hard_mode else '❌ Non'}",
        f"**Coffre-fort :** ~60 000 GTA$",
        "",
        f"💰 **Butin total estimé : {format_money(total_loot)}**"
    ]

    return "\n".join(lines)


def format_detailed_breakdown(
    heist: Dict,
    participants: List[int],
    custom_shares: Optional[Dict[int, float]] = None
) -> "discord.Embed":
    """
    Génère un embed détaillé avec tous les calculs (frais, parts, bonus Elite).

    Args:
        heist: Données complètes du braquage (avec optimized_plan)
        participants: Liste des discord_id
        custom_shares: Parts personnalisées {discord_id: pourcentage} ou None

    Returns:
        Embed Discord avec détails complets
    """
    import discord
    from cogs.cayo_perico.optimizer import (
        PRIMARY_TARGETS,
        HARD_MODE_MULTIPLIER,
        SAFE_VALUE,
        PAVEL_FEE,
        CONTACT_FEE,
        NET_MULTIPLIER,
        ELITE_BONUS_NORMAL,
        ELITE_BONUS_HARD,
        calculate_default_shares,
        calculate_net_total,
        calculate_player_gains,
    )

    # 1. Récupérer les infos du heist
    primary_target = heist.get("primary_loot", "tequila")
    hard_mode = heist.get("hard_mode", False)
    elite_completed = heist.get("elite_challenge_completed", False)
    optimized_plan = heist.get("optimized_plan") or []

    # 2. Calculer la valeur primaire (avec bonus hard mode 10% si applicable)
    primary_value = PRIMARY_TARGETS[primary_target]["value"]
    primary_value_with_bonus = primary_value
    if hard_mode:
        primary_value_with_bonus = int(primary_value * HARD_MODE_MULTIPLIER)

    # 3. Calculer la valeur secondaire (somme des sacs)
    secondary_value = sum(bag.get("total_value", 0) for bag in optimized_plan)

    # 4. Calculer le total brut
    total_brut = primary_value_with_bonus + secondary_value + SAFE_VALUE

    # 5. Déductions
    pavel_deduction = int(total_brut * PAVEL_FEE)
    contact_deduction = int(total_brut * CONTACT_FEE)
    total_deductions = pavel_deduction + contact_deduction

    # 6. Total net (88% du brut)
    total_net = calculate_net_total(primary_value_with_bonus, secondary_value, SAFE_VALUE)

    # 7. Récupérer ou calculer les parts
    if custom_shares:
        shares = [custom_shares.get(pid, 25.0) for pid in participants]
        shares_note = "**Parts personnalisées**"
    else:
        shares = calculate_default_shares(len(participants))
        shares_note = "**Parts par défaut**"

    # 8. Calculer les gains par joueur (avec bonus Elite si validé)
    predicted_gains_list = calculate_player_gains(total_net, shares, elite_completed, hard_mode)

    # Construire l'embed
    embed = discord.Embed(
        title="📊 Détails du braquage Cayo Perico",
        color=discord.Color.blue()
    )

    # Section 1: Objectifs
    objectives_lines = [
        f"🎯 **Objectif principal** : {PRIMARY_TARGETS[primary_target]['name']}",
        f"   • Valeur de base : {format_money(primary_value)}",
    ]
    if hard_mode:
        objectives_lines.append(f"   • Bonus mode difficile (+10%) : {format_money(primary_value_with_bonus - primary_value)}")
        objectives_lines.append(f"   • **Total primaire : {format_money(primary_value_with_bonus)}**")
    else:
        objectives_lines.append(f"   • **Total primaire : {format_money(primary_value)}**")

    objectives_lines.append(f"\n🎒 **Objectifs secondaires** (dans les sacs) : {format_money(secondary_value)}")
    objectives_lines.append(f"🔐 **Coffre-fort** : {format_money(SAFE_VALUE)}")

    embed.add_field(
        name="💎 Objectifs et butin",
        value="\n".join(objectives_lines),
        inline=False
    )

    # Section 2: Calcul des frais
    fees_lines = [
        f"💰 **Total brut** : {format_money(total_brut)}",
        f"",
        f"📉 **Déductions** :",
        f"   • Pavel (-2%) : -{format_money(pavel_deduction)}",
        f"   • Frais contact (-10%) : -{format_money(contact_deduction)}",
        f"   • **Total déductions** : -{format_money(total_deductions)}",
        f"",
        f"✅ **Total net (88%)** : {format_money(total_net)}"
    ]

    embed.add_field(
        name="🧮 Calcul des frais",
        value="\n".join(fees_lines),
        inline=False
    )

    # Section 3: Répartition
    elite_bonus = ELITE_BONUS_HARD if hard_mode else ELITE_BONUS_NORMAL
    shares_lines = [shares_note, ""]

    for idx, participant_id in enumerate(participants):
        if idx >= len(predicted_gains_list):
            break
        share = shares[idx]
        base_gain = int(total_net * share / 100.0)
        elite_part = elite_bonus if elite_completed else 0
        total_gain = predicted_gains_list[idx]

        if elite_completed:
            shares_lines.append(
                f"👤 Joueur {idx + 1} ({int(share)}%) : "
                f"{format_money(base_gain)} + {format_money(elite_part)} (Elite) = **{format_money(total_gain)}**"
            )
        else:
            shares_lines.append(
                f"👤 Joueur {idx + 1} ({int(share)}%) : **{format_money(total_gain)}**"
            )

    if elite_completed:
        shares_lines.append(f"\n🏆 **Défi Elite validé** : +{format_money(elite_bonus)} par joueur")

    embed.add_field(
        name="⚖️ Répartition des gains",
        value="\n".join(shares_lines),
        inline=False
    )

    embed.set_footer(text="💡 Les frais Pavel + Contact (12%) sont appliqués sur le TOTAL BRUT (primaire + secondaires + coffre) avant répartition.")

    return embed
