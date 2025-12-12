# cogs/cayo_perico/cayo_perico.py
"""
Fonctionnalité Cayo Perico V2 - Calculateur optimisé :
- Création de braquage via /cayo-perico (Select + Modal + Boutons)
- Calcul automatique du plan de sac optimisé
- Gestion des participants avec recalcul dynamique
- Boutons persistants (timeout=None) gérés via utils.view_manager
- Saisie des gains réels et statistiques
"""

from typing import Optional, Dict, List
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.logging_config import logger
from utils.view_manager import register_persistent_view
from .services.cayo_perico_service import CayoPericoService
from .services.stats_service import CayoStatsService
from .optimizer import (
    PRIMARY_TARGETS,
    SECONDARY_TARGETS,
    calculate_estimated_loot,
    optimize_bags,
    calculate_default_shares,
    calculate_net_total,
    ELITE_BONUS_NORMAL,
    ELITE_BONUS_HARD,
)
from .formatters import (
    format_secondary_loot,
    format_money,
    format_bag_plan_embed,
    format_bag_plan_private,
    format_results_comparison,
    format_objectives_summary,
)


# ==================== UTILITAIRES ====================

def _parse_int_field(value: str, min_val: int = 0, max_val: int = 9) -> int:
    """Parse et valide un champ numérique."""
    value = value.strip()
    if not value:
        return 0
    try:
        num = int(value)
        return max(min_val, min(num, max_val))
    except ValueError:
        return 0


def _calculate_bag_plan_params(primary_target: str, optimized_bags: List, hard_mode: bool, num_players: int):
    """
    Calcule les paramètres nécessaires pour format_bag_plan_embed().

    Returns:
        Tuple (shares, total_net, elite_bonus)
    """
    from .optimizer import PRIMARY_TARGETS, HARD_MODE_MULTIPLIER, SAFE_VALUE

    primary_value = PRIMARY_TARGETS[primary_target]["value"]
    if hard_mode:
        primary_value = int(primary_value * HARD_MODE_MULTIPLIER)

    secondary_value = sum(bag.get("total_value", 0) for bag in optimized_bags)
    total_net = calculate_net_total(primary_value, secondary_value, SAFE_VALUE)
    shares = calculate_default_shares(num_players)
    elite_bonus = ELITE_BONUS_HARD if hard_mode else ELITE_BONUS_NORMAL

    return shares, total_net, elite_bonus


# ==================== VIEWS ET MODALS ====================

class PrimaryTargetSelect(discord.ui.Select):
    """Select pour choisir l'objectif principal."""

    def __init__(self, service: CayoPericoService):
        self.service = service

        options = [
            discord.SelectOption(
                label=info["name"],
                value=key,
                description=format_money(info["value"]),
                emoji="💎" if "diamond" in key else ("🐆" if "panther" in key else "💰")
            )
            for key, info in PRIMARY_TARGETS.items()
        ]

        super().__init__(
            placeholder="Choisir l'objectif principal du braquage",
            options=options,
            custom_id="cayo_primary_select"
        )

    async def callback(self, interaction: discord.Interaction):
        primary_target = self.values[0]

        # Ouvrir le Modal pour les objectifs secondaires
        modal = SecondaryTargetsModal(primary_target, self.service)
        await interaction.response.send_modal(modal)

        # Supprimer le message du Select
        try:
            await interaction.message.delete()
        except:
            pass  # Ignorer si le message ne peut pas être supprimé


class PrimaryTargetView(discord.ui.View):
    """View contenant le Select pour l'objectif principal."""

    def __init__(self, service: CayoPericoService):
        super().__init__(timeout=180)
        self.add_item(PrimaryTargetSelect(service))


class SecondaryTargetsModal(discord.ui.Modal, title="Objectifs secondaires (Cayo Perico)"):
    """Modal pour saisir les quantités d'objectifs secondaires."""

    gold = discord.ui.TextInput(
        label="Lingots d'or (0-9)",
        placeholder="0",
        max_length=1,
        required=False
    )
    cocaine = discord.ui.TextInput(
        label="Cocaïne (0-9)",
        placeholder="0",
        max_length=1,
        required=False
    )
    paintings = discord.ui.TextInput(
        label="Tableaux (total/bureau, ex: 3/2)",
        placeholder="0/0 ou 3 ou 3/2",
        max_length=5,
        required=False
    )
    weed = discord.ui.TextInput(
        label="Cannabis (0-9)",
        placeholder="0",
        max_length=1,
        required=False
    )
    cash = discord.ui.TextInput(
        label="Argent (0-9)",
        placeholder="0",
        max_length=1,
        required=False
    )

    def __init__(self, primary_target: str, service: CayoPericoService):
        super().__init__()
        self.primary_target = primary_target
        self.service = service

    async def on_submit(self, interaction: discord.Interaction):
        # Parser les tableaux : format "total/bureau" ou juste "total"
        paintings_value = self.paintings.value.strip()
        total_paintings = 0
        office_paintings_count = 0

        if paintings_value:
            if "/" in paintings_value:
                # Format "total/bureau" (ex: "3/2")
                parts = paintings_value.split("/")
                if len(parts) == 2:
                    total_paintings = _parse_int_field(parts[0])
                    office_paintings_count = _parse_int_field(parts[1], min_val=0, max_val=2)
                else:
                    await interaction.response.send_message(
                        "❌ Format invalide pour les tableaux. Utilisez : total/bureau (ex: 3/2) ou juste le total (ex: 3)",
                        ephemeral=True
                    )
                    return
            else:
                # Format simple : juste le total
                total_paintings = _parse_int_field(paintings_value)
                office_paintings_count = 0

        # Valider que les tableaux du bureau <= total tableaux
        if office_paintings_count > total_paintings:
            await interaction.response.send_message(
                f"❌ Les tableaux dans le bureau ({office_paintings_count}) ne peuvent pas être supérieurs au total ({total_paintings}).",
                ephemeral=True
            )
            return

        # Valider que les tableaux du bureau <= 2
        if office_paintings_count > 2:
            await interaction.response.send_message(
                "❌ Maximum 2 tableaux dans le bureau.",
                ephemeral=True
            )
            return

        secondary_loot = {
            "gold": _parse_int_field(self.gold.value),
            "cocaine": _parse_int_field(self.cocaine.value),
            "paintings": total_paintings,
            "weed": _parse_int_field(self.weed.value),
            "cash": _parse_int_field(self.cash.value),
        }

        # Stocker séparément le nombre de tableaux du bureau
        self.office_paintings_count = office_paintings_count

        # Créer un embed de configuration
        hard_mode = False
        # Calculer avec les sacs optimisés (solo par défaut)
        optimized_bags = optimize_bags(secondary_loot, num_players=1, is_solo=True, office_paintings=office_paintings_count)
        total_loot = calculate_estimated_loot(self.primary_target, optimized_bags, hard_mode)

        embed = discord.Embed(
            title="💣 Configuration Cayo Perico",
            description=format_objectives_summary(
                self.primary_target,
                secondary_loot,
                hard_mode,
                total_loot
            ),
            color=discord.Color.gold()
        )

        # Ajouter info sur les tableaux du bureau si présents
        if office_paintings_count > 0:
            embed.add_field(
                name="🖼️ Tableaux du bureau",
                value=f"✅ **{office_paintings_count} tableau{'x' if office_paintings_count > 1 else ''}** dans le bureau (accessible en solo)",
                inline=False
            )

        embed.add_field(
            name="ℹ️ Prochaines étapes",
            value="• Active le **mode difficile** si nécessaire (+10% sur objectif primaire)\n"
                  "• Clique sur **Confirmer** pour créer le braquage",
            inline=False
        )

        # View avec boutons de configuration
        view = ConfigView(self.primary_target, secondary_loot, self.service, office_paintings_count)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ConfigView(discord.ui.View):
    """View pour configurer le mode difficile et confirmer."""

    def __init__(self, primary_target: str, secondary_loot: Dict[str, int], service: CayoPericoService, office_paintings: int = 0):
        super().__init__(timeout=300)
        self.primary_target = primary_target
        self.secondary_loot = secondary_loot
        self.hard_mode = False
        self.service = service
        self.office_paintings = office_paintings

    @discord.ui.button(
        label="Mode difficile : ❌ Non",
        style=discord.ButtonStyle.secondary,
        custom_id="toggle_hard_mode"
    )
    async def toggle_hard_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.hard_mode = not self.hard_mode

        # Mettre à jour le bouton
        button.label = f"Mode difficile : {'✅ Oui' if self.hard_mode else '❌ Non'}"
        button.style = discord.ButtonStyle.success if self.hard_mode else discord.ButtonStyle.secondary

        # Recalculer et mettre à jour l'embed
        optimized_bags = optimize_bags(self.secondary_loot, num_players=1, is_solo=True, office_paintings=self.office_paintings)
        total_loot = calculate_estimated_loot(self.primary_target, optimized_bags, self.hard_mode)

        embed = discord.Embed(
            title="💣 Configuration Cayo Perico",
            description=format_objectives_summary(
                self.primary_target,
                self.secondary_loot,
                self.hard_mode,
                total_loot
            ),
            color=discord.Color.gold()
        )

        # Ajouter info sur les tableaux du bureau si présents
        if self.office_paintings > 0:
            embed.add_field(
                name="🖼️ Tableaux du bureau",
                value=f"✅ **{self.office_paintings} tableau{'x' if self.office_paintings > 1 else ''}** dans le bureau (accessible en solo)",
                inline=False
            )

        embed.add_field(
            name="ℹ️ Prochaines étapes",
            value="• Active le **mode difficile** si nécessaire (+10% sur objectif primaire)\n"
                  "• Clique sur **Confirmer** pour créer le braquage",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="✅ Confirmer et créer",
        style=discord.ButtonStyle.primary,
        custom_id="confirm_heist"
    )
    async def confirm_heist(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "Cette commande ne peut être utilisée qu'en serveur.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Récupérer la moyenne globale du coffre-fort pour l'estimation
        stats_service = CayoStatsService(self.service.db)
        global_avg_safe = await stats_service.get_global_avg_safe_amount()

        # Optimiser les sacs et calculer le butin estimé RÉEL avec la moyenne globale
        optimized_bags = optimize_bags(self.secondary_loot, num_players=1, is_solo=True, office_paintings=self.office_paintings)
        total_loot = calculate_estimated_loot(self.primary_target, optimized_bags, self.hard_mode, safe_amount=global_avg_safe)

        # Créer l'embed final
        embed = discord.Embed(
            title="💣 Préparation Cayo Perico",
            color=discord.Color.gold()
        )

        embed.add_field(name="Organisateur", value=f"<@{interaction.user.id}>", inline=True)
        embed.add_field(name="Statut", value="⏳ En préparation", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name="🎯 Objectifs",
            value=format_objectives_summary(
                self.primary_target,
                self.secondary_loot,
                self.hard_mode,
                total_loot
            ),
            inline=False
        )

        embed.add_field(
            name="👥 Participants (1)",
            value=f"<@{interaction.user.id}>",
            inline=False
        )

        # Calculer les informations pour le plan de sac avec Elite
        shares, total_net, elite_bonus = _calculate_bag_plan_params(
            self.primary_target, optimized_bags, self.hard_mode, 1
        )

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(
                optimized_bags,
                [interaction.user.id],
                shares=shares,
                total_net=total_net,
                hard_mode=self.hard_mode,
                elite_bonus=elite_bonus
            ),
            inline=False
        )

        # View persistante avec les boutons
        view = CayoPericoView(self.service)

        # Envoyer dans le channel
        message = await interaction.channel.send(embed=embed, view=view)

        # Créer le braquage en DB (peut lever ValueError si braquage actif)
        try:
            heist_id = await self.service.create_heist(
                guild_id=interaction.guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                leader_discord_id=interaction.user.id,
                primary_loot=self.primary_target,
                secondary_loot=self.secondary_loot,
                estimated_loot=total_loot,
                office_paintings=self.office_paintings,
                hard_mode=self.hard_mode,
            )
        except ValueError as e:
            # Braquage actif déjà existant - supprimer le message créé
            await message.delete()
            await interaction.followup.send(
                f"❌ {str(e)}",
                ephemeral=True
            )
            return

        # Sauvegarder le plan optimisé
        await self.service.update_optimized_plan(heist_id, optimized_bags)

        # Ajouter l'organisateur comme participant
        await self.service.add_participant(heist_id, interaction.user.id)

        # Supprimer le message de configuration
        try:
            await interaction.message.delete()
        except:
            pass  # Ignorer si impossible (message ephemeral)

        await interaction.followup.send(
            "✅ Braquage Cayo Perico créé avec succès !",
            ephemeral=True
        )


# ==================== BOUTONS INDIVIDUELS ====================

class JoinButton(discord.ui.Button):
    """Bouton pour rejoindre un braquage."""

    def __init__(self, service: CayoPericoService):
        super().__init__(
            label="Rejoindre le braquage",
            style=discord.ButtonStyle.success,
            custom_id="cayo_join"
        )
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        # Récupérer le heist
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        # Vérifier si déjà participant
        participants = await self.service.get_participants(heist["id"])
        if interaction.user.id in participants:
            await interaction.response.send_message(
                "Tu participes déjà à ce braquage.", ephemeral=True
            )
            return

        # Vérifier la limite de 4 joueurs
        if len(participants) >= 4:
            await interaction.response.send_message(
                "Le braquage est complet (4 joueurs maximum).", ephemeral=True
            )
            return

        # Répondre immédiatement à l'interaction
        await interaction.response.send_message(
            "Tu as rejoint le braquage.", ephemeral=True
        )

        # Ajouter le participant et recalculer le plan
        await self.service.add_participant(heist["id"], interaction.user.id)
        await self._update_message_embed(interaction, heist)

    async def _get_heist_for_interaction(self, interaction: discord.Interaction):
        """Récupère le heist lié au message du bouton."""
        if interaction.guild is None or interaction.channel is None or interaction.message is None:
            await interaction.response.send_message(
                "Cette action n'est pas disponible ici.", ephemeral=True
            )
            return None

        heist = await self.service.get_heist_by_message(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=interaction.message.id,
        )

        if heist is None:
            await interaction.response.send_message(
                "Impossible de retrouver ce braquage (peut-être déjà supprimé).",
                ephemeral=True,
            )
            return None

        return heist

    async def _update_message_embed(self, interaction: discord.Interaction, heist: Dict):
        """Met à jour l'embed du message en fonction des données BDD."""
        participants = await self.service.get_participants(heist["id"])
        num_players = len(participants)

        # Recalculer le plan de sac
        optimized_bags = optimize_bags(
            heist["secondary_loot"],
            num_players=num_players,
            is_solo=(num_players == 1),
            office_paintings=heist.get("office_paintings", 0)
        )

        # Sauvegarder le nouveau plan
        await self.service.update_optimized_plan(heist["id"], optimized_bags)

        # Recalculer le butin estimé RÉEL
        total_loot = calculate_estimated_loot(
            heist["primary_loot"],
            optimized_bags,
            heist.get("hard_mode", False)
        )

        # Construire le nouvel embed
        status_label = {
            "pending": "⏳ En préparation",
            "ready": "✅ Prêt",
            "finished": "🏁 Terminé",
            "cancelled": "❌ Annulé",
        }.get(heist.get("status", "pending"), "⏳ En préparation")

        embed = discord.Embed(
            title="💣 Préparation Cayo Perico",
            color=discord.Color.gold()
        )

        embed.add_field(name="Organisateur", value=f"<@{heist['leader_id']}>", inline=True)
        embed.add_field(name="Statut", value=status_label, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name="🎯 Objectifs",
            value=format_objectives_summary(
                heist["primary_loot"],
                heist["secondary_loot"],
                heist.get("hard_mode", False),
                total_loot
            ),
            inline=False
        )

        participants_mentions = ", ".join(f"<@{uid}>" for uid in participants)
        embed.add_field(
            name=f"👥 Participants ({len(participants)})",
            value=participants_mentions,
            inline=False
        )

        # Calculer les informations pour le plan de sac avec Elite
        shares, total_net, elite_bonus = _calculate_bag_plan_params(
            heist["primary_loot"], optimized_bags, heist.get("hard_mode", False), num_players
        )

        # Récupérer les parts personnalisées si définies
        custom_shares = await self.service.get_custom_shares(heist["id"])
        if custom_shares:
            # Convertir en liste dans l'ordre des participants
            shares = [custom_shares.get(pid, 25.0) for pid in participants]

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(
                optimized_bags,
                participants,
                shares=shares,
                total_net=total_net,
                hard_mode=heist.get("hard_mode", False),
                elite_bonus=elite_bonus
            ),
            inline=False
        )

        # Recréer la vue avec le bon statut
        current_status = heist.get("status", "pending")
        new_view = CayoPericoView(self.service, heist_status=current_status, num_participants=num_players)

        try:
            await interaction.message.edit(embed=embed, view=new_view)
        except Exception as e:
            logger.error(f"[Cayo] Erreur lors de la mise à jour du message: {e}")


class LeaveButton(discord.ui.Button):
    """Bouton pour quitter un braquage."""

    def __init__(self, service: CayoPericoService):
        super().__init__(
            label="Quitter",
            style=discord.ButtonStyle.danger,
            custom_id="cayo_leave"
        )
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        # Si l'organisateur quitte, supprimer le braquage
        if interaction.user.id == heist["leader_id"]:
            await interaction.response.send_message(
                "Tu es l'organisateur, le braquage va être supprimé.", ephemeral=True
            )

            # Supprimer le braquage
            await self.service.delete_heist(heist["id"])

            # Supprimer le message
            try:
                await interaction.message.delete()
            except:
                pass

            return

        # Vérifier si l'utilisateur est participant
        participants = await self.service.get_participants(heist["id"])
        if interaction.user.id not in participants:
            await interaction.response.send_message(
                "Tu ne participes pas à ce braquage.", ephemeral=True
            )
            return

        # Répondre immédiatement à l'interaction
        await interaction.response.send_message(
            "Tu as quitté le braquage.", ephemeral=True
        )

        # Retirer le participant et recalculer le plan
        await self.service.remove_participant(heist["id"], interaction.user.id)
        await self._update_message_embed(interaction, heist)

    async def _get_heist_for_interaction(self, interaction: discord.Interaction):
        """Récupère le heist lié au message du bouton."""
        if interaction.guild is None or interaction.channel is None or interaction.message is None:
            await interaction.response.send_message(
                "Cette action n'est pas disponible ici.", ephemeral=True
            )
            return None

        heist = await self.service.get_heist_by_message(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=interaction.message.id,
        )

        if heist is None:
            await interaction.response.send_message(
                "Impossible de retrouver ce braquage (peut-être déjà supprimé).",
                ephemeral=True,
            )
            return None

        return heist

    async def _update_message_embed(self, interaction: discord.Interaction, heist: Dict):
        """Met à jour l'embed du message en fonction des données BDD."""
        participants = await self.service.get_participants(heist["id"])
        num_players = len(participants)

        # Recalculer le plan de sac
        optimized_bags = optimize_bags(
            heist["secondary_loot"],
            num_players=num_players,
            is_solo=(num_players == 1),
            office_paintings=heist.get("office_paintings", 0)
        )

        # Sauvegarder le nouveau plan
        await self.service.update_optimized_plan(heist["id"], optimized_bags)

        # Recalculer le butin estimé RÉEL
        total_loot = calculate_estimated_loot(
            heist["primary_loot"],
            optimized_bags,
            heist.get("hard_mode", False)
        )

        # Construire le nouvel embed
        status_label = {
            "pending": "⏳ En préparation",
            "ready": "✅ Prêt",
            "finished": "🏁 Terminé",
            "cancelled": "❌ Annulé",
        }.get(heist.get("status", "pending"), "⏳ En préparation")

        embed = discord.Embed(
            title="💣 Préparation Cayo Perico",
            color=discord.Color.gold()
        )

        embed.add_field(name="Organisateur", value=f"<@{heist['leader_id']}>", inline=True)
        embed.add_field(name="Statut", value=status_label, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name="🎯 Objectifs",
            value=format_objectives_summary(
                heist["primary_loot"],
                heist["secondary_loot"],
                heist.get("hard_mode", False),
                total_loot
            ),
            inline=False
        )

        participants_mentions = ", ".join(f"<@{uid}>" for uid in participants)
        embed.add_field(
            name=f"👥 Participants ({len(participants)})",
            value=participants_mentions,
            inline=False
        )

        # Calculer les informations pour le plan de sac avec Elite
        shares, total_net, elite_bonus = _calculate_bag_plan_params(
            heist["primary_loot"], optimized_bags, heist.get("hard_mode", False), num_players
        )

        # Récupérer les parts personnalisées si définies
        custom_shares = await self.service.get_custom_shares(heist["id"])
        if custom_shares:
            # Convertir en liste dans l'ordre des participants
            shares = [custom_shares.get(pid, 25.0) for pid in participants]

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(
                optimized_bags,
                participants,
                shares=shares,
                total_net=total_net,
                hard_mode=heist.get("hard_mode", False),
                elite_bonus=elite_bonus
            ),
            inline=False
        )

        # Recréer la vue avec le bon statut
        current_status = heist.get("status", "pending")
        new_view = CayoPericoView(self.service, heist_status=current_status, num_participants=num_players)

        try:
            await interaction.message.edit(embed=embed, view=new_view)
        except Exception as e:
            logger.error(f"[Cayo] Erreur lors de la mise à jour du message: {e}")


class ReadyButton(discord.ui.Button):
    """Bouton pour marquer le braquage comme prêt."""

    def __init__(self, service: CayoPericoService):
        super().__init__(
            label="🏁 Braquage prêt",
            style=discord.ButtonStyle.primary,
            custom_id="cayo_ready"
        )
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        # Seul l'organisateur peut marquer le braquage prêt
        if interaction.user.id != heist["leader_id"]:
            await interaction.response.send_message(
                "Seul l'organisateur peut marquer le braquage comme prêt.",
                ephemeral=True,
            )
            return

        # Vérifier que le braquage n'est pas déjà prêt ou terminé
        if heist.get("status") != "pending":
            status_msg = {
                "ready": "Le braquage est déjà marqué comme prêt.",
                "finished": "Le braquage est déjà terminé.",
                "cancelled": "Le braquage a été annulé.",
            }.get(heist.get("status"), "Le braquage n'est plus en préparation.")

            await interaction.response.send_message(
                status_msg,
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Marquer le braquage comme prêt
        await self.service.mark_ready(heist["id"])

        # Récupérer le heist mis à jour depuis la BDD (avec le nouveau statut "ready")
        heist = await self.service.get_heist_by_id(heist["id"])
        if heist is None:
            await interaction.followup.send("Erreur : impossible de récupérer le braquage.", ephemeral=True)
            return

        # Mettre à jour l'embed avec le heist fraîchement récupéré
        await self._update_message_embed(interaction, heist)

        # Le heist est maintenant à jour, pas besoin de le récupérer à nouveau
        heist_full = heist

        # Envoyer le plan de sac à chaque participant en privé
        participants = await self.service.get_participants(heist["id"])
        optimized_plan = heist_full.get("optimized_plan") or []

        for idx, participant_id in enumerate(participants):
            if idx >= len(optimized_plan):
                continue

            try:
                user = interaction.guild.get_member(participant_id)
                if user:
                    bag_plan = optimized_plan[idx]
                    dm_embed = format_bag_plan_private(bag_plan, idx + 1)
                    await user.send(embed=dm_embed)
            except Exception as e:
                logger.warning(f"[Cayo] Impossible d'envoyer le plan à l'utilisateur {participant_id}: {e}")

        # Calculer le temps de préparation
        from cogs.cayo_perico.optimizer import format_duration
        prep_time = format_duration(heist_full.get("created_at"), heist_full.get("ready_at"))

        await interaction.followup.send(
            f"✅ Braquage marqué comme prêt !\n⏱️ Temps de préparation : **{prep_time}**\n📨 Les plans de sac ont été envoyés en privé aux participants.",
            ephemeral=True
        )

    async def _get_heist_for_interaction(self, interaction: discord.Interaction):
        """Récupère le heist lié au message du bouton."""
        if interaction.guild is None or interaction.channel is None or interaction.message is None:
            await interaction.response.send_message(
                "Cette action n'est pas disponible ici.", ephemeral=True
            )
            return None

        heist = await self.service.get_heist_by_message(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=interaction.message.id,
        )

        if heist is None:
            await interaction.response.send_message(
                "Impossible de retrouver ce braquage (peut-être déjà supprimé).",
                ephemeral=True,
            )
            return None

        return heist

    async def _update_message_embed(self, interaction: discord.Interaction, heist: Dict):
        """Met à jour l'embed du message en fonction des données BDD."""
        participants = await self.service.get_participants(heist["id"])
        num_players = len(participants)

        # Recalculer le plan de sac
        optimized_bags = optimize_bags(
            heist["secondary_loot"],
            num_players=num_players,
            is_solo=(num_players == 1),
            office_paintings=heist.get("office_paintings", 0)
        )

        # Sauvegarder le nouveau plan
        await self.service.update_optimized_plan(heist["id"], optimized_bags)

        # Recalculer le butin estimé RÉEL
        total_loot = calculate_estimated_loot(
            heist["primary_loot"],
            optimized_bags,
            heist.get("hard_mode", False)
        )

        # Construire le nouvel embed
        status_label = {
            "pending": "⏳ En préparation",
            "ready": "✅ Prêt",
            "finished": "🏁 Terminé",
            "cancelled": "❌ Annulé",
        }.get(heist.get("status", "pending"), "⏳ En préparation")

        embed = discord.Embed(
            title="💣 Préparation Cayo Perico",
            color=discord.Color.gold()
        )

        embed.add_field(name="Organisateur", value=f"<@{heist['leader_id']}>", inline=True)
        embed.add_field(name="Statut", value=status_label, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name="🎯 Objectifs",
            value=format_objectives_summary(
                heist["primary_loot"],
                heist["secondary_loot"],
                heist.get("hard_mode", False),
                total_loot
            ),
            inline=False
        )

        participants_mentions = ", ".join(f"<@{uid}>" for uid in participants)
        embed.add_field(
            name=f"👥 Participants ({len(participants)})",
            value=participants_mentions,
            inline=False
        )

        # Calculer les informations pour le plan de sac avec Elite
        shares, total_net, elite_bonus = _calculate_bag_plan_params(
            heist["primary_loot"], optimized_bags, heist.get("hard_mode", False), num_players
        )

        # Récupérer les parts personnalisées si définies
        custom_shares = await self.service.get_custom_shares(heist["id"])
        if custom_shares:
            # Convertir en liste dans l'ordre des participants
            shares = [custom_shares.get(pid, 25.0) for pid in participants]

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(
                optimized_bags,
                participants,
                shares=shares,
                total_net=total_net,
                hard_mode=heist.get("hard_mode", False),
                elite_bonus=elite_bonus
            ),
            inline=False
        )

        # Recréer la vue avec le bon statut
        current_status = heist.get("status", "pending")
        new_view = CayoPericoView(self.service, heist_status=current_status, num_participants=num_players)

        try:
            await interaction.message.edit(embed=embed, view=new_view)
        except Exception as e:
            logger.error(f"[Cayo] Erreur lors de la mise à jour du message: {e}")


class EliteSelectView(discord.ui.View):
    """View pour sélectionner si le Défi Elite a été validé."""

    def __init__(self, heist: Dict, participants: List[int], service: CayoPericoService):
        super().__init__(timeout=120)  # 2 minutes de timeout
        self.heist = heist
        self.participants = participants
        self.service = service
        self.elite_completed = False

    @discord.ui.select(
        placeholder="Le Défi Elite a-t-il été validé ?",
        options=[
            discord.SelectOption(label="Non", value="no", emoji="❌", default=True),
            discord.SelectOption(label="Oui", value="yes", emoji="✅"),
        ]
    )
    async def elite_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.elite_completed = (select.values[0] == "yes")

        # Ouvrir le Modal pour saisir les gains
        modal = FinishHeistModal(self.heist, self.participants, self.service, self.elite_completed, interaction.message)
        await interaction.response.send_modal(modal)

        # Désactiver la vue
        self.stop()


class FinishButton(discord.ui.Button):
    """Bouton pour terminer le braquage."""

    def __init__(self, service: CayoPericoService):
        super().__init__(
            label="🏁 Terminer",
            style=discord.ButtonStyle.primary,
            custom_id="cayo_finish"
        )
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        # Seul l'organisateur peut terminer
        if interaction.user.id != heist["leader_id"]:
            await interaction.response.send_message(
                "Seul l'organisateur peut terminer le braquage.",
                ephemeral=True,
            )
            return

        # Ouvrir la vue de sélection du Défi Elite
        participants = await self.service.get_participants(heist["id"])
        view = EliteSelectView(heist, participants, self.service)
        await interaction.response.send_message(
            "🏆 Le Défi Elite a-t-il été validé pendant le braquage ?",
            view=view,
            ephemeral=True
        )

    async def _get_heist_for_interaction(self, interaction: discord.Interaction):
        """Récupère le heist lié au message du bouton."""
        if interaction.guild is None or interaction.channel is None or interaction.message is None:
            await interaction.response.send_message(
                "Cette action n'est pas disponible ici.", ephemeral=True
            )
            return None

        heist = await self.service.get_heist_by_message(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=interaction.message.id,
        )

        if heist is None:
            await interaction.response.send_message(
                "Impossible de retrouver ce braquage (peut-être déjà supprimé).",
                ephemeral=True,
            )
            return None

        return heist


class SharesButton(discord.ui.Button):
    """Bouton pour répartir les parts."""

    def __init__(self, service: CayoPericoService):
        super().__init__(
            label="⚖️ Répartir les parts",
            style=discord.ButtonStyle.secondary,
            custom_id="cayo_shares"
        )
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        # Seul l'organisateur peut modifier les parts
        if interaction.user.id != heist["leader_id"]:
            await interaction.response.send_message(
                "Seul l'organisateur peut répartir les parts.",
                ephemeral=True,
            )
            return

        participants = await self.service.get_participants(heist["id"])
        if len(participants) < 2:
            await interaction.response.send_message(
                "Il faut au moins 2 joueurs pour répartir les parts.",
                ephemeral=True,
            )
            return

        # Ouvrir le Modal de répartition
        modal = SharesModal(heist, participants, self.service, interaction.message)
        await interaction.response.send_modal(modal)

    async def _get_heist_for_interaction(self, interaction: discord.Interaction):
        """Récupère le heist lié au message du bouton."""
        if interaction.guild is None or interaction.channel is None or interaction.message is None:
            await interaction.response.send_message(
                "Cette action n'est pas disponible ici.", ephemeral=True
            )
            return None

        heist = await self.service.get_heist_by_message(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=interaction.message.id,
        )

        if heist is None:
            await interaction.response.send_message(
                "Impossible de retrouver ce braquage (peut-être déjà supprimé).",
                ephemeral=True,
            )
            return None

        return heist


class DetailsButton(discord.ui.Button):
    """Bouton pour afficher les détails."""

    def __init__(self, service: CayoPericoService):
        super().__init__(
            label="📊 Détails",
            style=discord.ButtonStyle.secondary,
            custom_id="cayo_details"
        )
        self.service = service

    async def callback(self, interaction: discord.Interaction):
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        # Récupérer le heist complet avec optimized_plan
        heist_full = await self.service.get_heist_by_id(heist["id"])
        if heist_full is None:
            await interaction.response.send_message(
                "Erreur : impossible de récupérer les détails du braquage.",
                ephemeral=True
            )
            return

        # Récupérer les participants et les parts personnalisées
        participants = await self.service.get_participants(heist["id"])
        custom_shares = await self.service.get_custom_shares(heist["id"])

        # Générer l'embed détaillé
        from cogs.cayo_perico.formatters import format_detailed_breakdown
        embed = format_detailed_breakdown(heist_full, participants, custom_shares)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _get_heist_for_interaction(self, interaction: discord.Interaction):
        """Récupère le heist lié au message du bouton."""
        if interaction.guild is None or interaction.channel is None or interaction.message is None:
            await interaction.response.send_message(
                "Cette action n'est pas disponible ici.", ephemeral=True
            )
            return None

        heist = await self.service.get_heist_by_message(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=interaction.message.id,
        )

        if heist is None:
            await interaction.response.send_message(
                "Impossible de retrouver ce braquage (peut-être déjà supprimé).",
                ephemeral=True,
            )
            return None

        return heist


# ==================== VIEW PRINCIPALE (PERSISTANTE) ====================

class CayoPericoView(discord.ui.View):
    """
    View des boutons Cayo Perico avec affichage conditionnel selon le statut.
    timeout=None -> boutons persistants tant que le bot tourne.
    """

    def __init__(self, service: CayoPericoService, heist_status: str = "pending", num_participants: int = 1):
        super().__init__(timeout=None)
        self.service = service
        self.heist_status = heist_status
        self.num_participants = num_participants

        # Configurer les boutons selon le statut
        self._setup_buttons()

    def _setup_buttons(self):
        """Configure les boutons selon le statut du braquage."""
        # Toujours visible : bouton Détails
        self.add_item(DetailsButton(self.service))

        if self.heist_status == "pending":
            # Phase de préparation
            self.add_item(JoinButton(self.service))
            self.add_item(LeaveButton(self.service))
            self.add_item(ReadyButton(self.service))

        elif self.heist_status == "ready":
            # Phase prête (braquage lancé)
            self.add_item(LeaveButton(self.service))
            self.add_item(FinishButton(self.service))
            # Répartir les parts uniquement si 2+ joueurs
            if self.num_participants >= 2:
                self.add_item(SharesButton(self.service))

        elif self.heist_status == "finished":
            # Braquage terminé, seul le bouton Détails reste
            pass

    async def _get_heist_for_interaction(
        self, interaction: discord.Interaction
    ) -> Optional[Dict]:
        """Récupère le heist lié au message du bouton."""
        if interaction.guild is None or interaction.channel is None or interaction.message is None:
            await interaction.response.send_message(
                "Cette action n'est pas disponible ici.", ephemeral=True
            )
            return None

        heist = await self.service.get_heist_by_message(
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            message_id=interaction.message.id,
        )

        if heist is None:
            await interaction.response.send_message(
                "Impossible de retrouver ce braquage (peut-être déjà supprimé).",
                ephemeral=True,
            )
            return None

        return heist

    async def _update_message_embed(
        self,
        interaction: discord.Interaction,
        heist: Dict,
    ) -> None:
        """Met à jour l'embed du message en fonction des données BDD."""
        participants = await self.service.get_participants(heist["id"])
        num_players = len(participants)

        # Recalculer le plan de sac
        optimized_bags = optimize_bags(
            heist["secondary_loot"],
            num_players=num_players,
            is_solo=(num_players == 1),
            office_paintings=heist.get("office_paintings", 0)
        )

        # Sauvegarder le nouveau plan
        await self.service.update_optimized_plan(heist["id"], optimized_bags)

        # Recalculer le butin estimé RÉEL (seulement ce qui rentre dans les sacs)
        total_loot = calculate_estimated_loot(
            heist["primary_loot"],
            optimized_bags,
            heist.get("hard_mode", False)
        )

        # Construire le nouvel embed
        status_label = {
            "pending": "⏳ En préparation",
            "ready": "✅ Prêt",
            "finished": "🏁 Terminé",
            "cancelled": "❌ Annulé",
        }.get(heist.get("status", "pending"), "⏳ En préparation")

        embed = discord.Embed(
            title="💣 Préparation Cayo Perico",
            color=discord.Color.gold()
        )

        embed.add_field(name="Organisateur", value=f"<@{heist['leader_id']}>", inline=True)
        embed.add_field(name="Statut", value=status_label, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        embed.add_field(
            name="🎯 Objectifs",
            value=format_objectives_summary(
                heist["primary_loot"],
                heist["secondary_loot"],
                heist.get("hard_mode", False),
                total_loot
            ),
            inline=False
        )

        participants_mentions = ", ".join(f"<@{uid}>" for uid in participants)
        embed.add_field(
            name=f"👥 Participants ({len(participants)})",
            value=participants_mentions,
            inline=False
        )

        # Calculer les informations pour le plan de sac avec Elite
        shares, total_net, elite_bonus = _calculate_bag_plan_params(
            heist["primary_loot"], optimized_bags, heist.get("hard_mode", False), num_players
        )

        # Récupérer les parts personnalisées si définies
        custom_shares = await self.service.get_custom_shares(heist["id"])
        if custom_shares:
            # Convertir en liste dans l'ordre des participants
            shares = [custom_shares.get(pid, 25.0) for pid in participants]

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(
                optimized_bags,
                participants,
                shares=shares,
                total_net=total_net,
                hard_mode=heist.get("hard_mode", False),
                elite_bonus=elite_bonus
            ),
            inline=False
        )

        # Recréer la vue avec le bon statut
        current_status = heist.get("status", "pending")
        new_view = CayoPericoView(self.service, heist_status=current_status, num_participants=num_players)

        try:
            await interaction.message.edit(embed=embed, view=new_view)
        except Exception as e:
            logger.error(f"[Cayo] Erreur lors de la mise à jour du message: {e}")


class SharesModal(discord.ui.Modal, title="Répartition des parts"):
    """Modal pour définir les parts personnalisées (incréments de 5%, minimum 15%)."""

    def __init__(self, heist: Dict, participants: List[int], service: CayoPericoService, original_message: discord.Message):
        super().__init__()
        self.heist = heist
        self.participants = participants
        self.service = service
        self.original_message = original_message

        # Récupérer les parts actuelles ou par défaut
        from cogs.cayo_perico.optimizer import calculate_default_shares

        current_shares = heist.get("custom_shares")
        if current_shares is None:
            default_shares = calculate_default_shares(len(participants))
        else:
            # custom_shares peut déjà être un dict avec les discord_id
            default_shares = [current_shares.get(str(pid), 25.0) for pid in participants]

        # Créer un TextInput par joueur (max 4 selon le plan)
        for idx, participant_id in enumerate(participants[:4]):
            default_value = str(int(default_shares[idx] if idx < len(default_shares) else 25))
            text_input = discord.ui.TextInput(
                label=f"Part Joueur {idx + 1} (%)",
                placeholder="15-85 (incréments de 5)",
                default=default_value,
                max_length=2,
                required=True
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Parser et valider les parts
        shares = []
        for idx, item in enumerate(self.children):
            try:
                value = int(item.value.strip())
                if value < 15:
                    await interaction.response.send_message(
                        f"❌ Part minimum : 15% (Joueur {idx + 1} = {value}%)", ephemeral=True
                    )
                    return
                if value > 85:
                    await interaction.response.send_message(
                        f"❌ Part maximum : 85% (Joueur {idx + 1} = {value}%)", ephemeral=True
                    )
                    return
                if value % 5 != 0:
                    await interaction.response.send_message(
                        f"❌ Parts par incréments de 5% (Joueur {idx + 1} = {value}%)", ephemeral=True
                    )
                    return
                shares.append(value)
            except ValueError:
                await interaction.response.send_message(
                    f"❌ Valeur invalide pour Joueur {idx + 1}", ephemeral=True
                )
                return

        # Vérifier total = 100%
        if sum(shares) != 100:
            await interaction.response.send_message(
                f"❌ Total doit être 100% (actuel : {sum(shares)}%)", ephemeral=True
            )
            return

        # Créer le dictionnaire {discord_id: pourcentage}
        shares_dict = {self.participants[idx]: shares[idx] for idx in range(len(shares))}

        # Sauvegarder
        await self.service.update_custom_shares(self.heist["id"], shares_dict)

        # Mettre à jour l'embed principal
        heist_full = await self.service.get_heist_by_id(self.heist["id"])
        if heist_full:
            participants = await self.service.get_participants(self.heist["id"])
            num_players = len(participants)

            # Recalculer le plan de sac
            optimized_bags = optimize_bags(
                heist_full["secondary_loot"],
                num_players=num_players,
                is_solo=(num_players == 1),
                office_paintings=heist_full.get("office_paintings", 0)
            )

            # Recalculer le butin estimé
            total_loot = calculate_estimated_loot(
                heist_full["primary_loot"],
                optimized_bags,
                heist_full.get("hard_mode", False)
            )

            # Construire le nouvel embed
            status_label = {
                "pending": "⏳ En préparation",
                "ready": "✅ Prêt",
                "finished": "🏁 Terminé",
                "cancelled": "❌ Annulé",
            }.get(heist_full.get("status", "pending"), "⏳ En préparation")

            embed = discord.Embed(
                title="💣 Préparation Cayo Perico",
                color=discord.Color.gold()
            )

            embed.add_field(name="Organisateur", value=f"<@{heist_full['leader_id']}>", inline=True)
            embed.add_field(name="Statut", value=status_label, inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)

            embed.add_field(
                name="🎯 Objectifs",
                value=format_objectives_summary(
                    heist_full["primary_loot"],
                    heist_full["secondary_loot"],
                    heist_full.get("hard_mode", False),
                    total_loot
                ),
                inline=False
            )

            participants_mentions = ", ".join(f"<@{uid}>" for uid in participants)
            embed.add_field(
                name=f"👥 Participants ({len(participants)})",
                value=participants_mentions,
                inline=False
            )

            # Calculer les informations pour le plan de sac avec Elite
            shares_list, total_net, elite_bonus = _calculate_bag_plan_params(
                heist_full["primary_loot"], optimized_bags, heist_full.get("hard_mode", False), num_players
            )

            # Utiliser les parts personnalisées
            shares_list = [shares_dict.get(pid, 25.0) for pid in participants]

            embed.add_field(
                name="🎒 Plan de sac optimisé",
                value=format_bag_plan_embed(
                    optimized_bags,
                    participants,
                    shares=shares_list,
                    total_net=total_net,
                    hard_mode=heist_full.get("hard_mode", False),
                    elite_bonus=elite_bonus
                ),
                inline=False
            )

            # Mettre à jour le message principal
            current_status = heist_full.get("status", "pending")
            new_view = CayoPericoView(self.service, heist_status=current_status, num_participants=num_players)

            try:
                await self.original_message.edit(embed=embed, view=new_view)
            except Exception as e:
                logger.error(f"[Cayo] Erreur lors de la mise à jour du message après répartition des parts: {e}")

        await interaction.response.send_message(
            "✅ Parts personnalisées enregistrées !", ephemeral=True
        )


class FinishHeistModal(discord.ui.Modal, title="Résultats du braquage"):
    """Modal pour saisir les gains réels de chaque participant."""

    def __init__(self, heist: Dict, participants: List[int], service: CayoPericoService, elite_completed: bool, elite_message: Optional[discord.Message] = None):
        super().__init__()
        self.heist = heist
        self.participants = participants
        self.service = service
        self.elite_completed = elite_completed  # Déjà déterminé par le Select
        self.elite_message = elite_message  # Message éphémère à supprimer

        # Ajouter le champ pour le temps de mission
        self.mission_time_input = discord.ui.TextInput(
            label="Temps de mission (mm:ss)",
            placeholder="Ex: 12:34",
            max_length=10,
            required=True
        )
        self.add_item(self.mission_time_input)

        # Ajouter le champ pour la valeur du coffre-fort
        self.safe_value_input = discord.ui.TextInput(
            label="Valeur du coffre-fort (GTA$)",
            placeholder="Ex: 60000",
            max_length=10,
            required=True
        )
        self.add_item(self.safe_value_input)

        # Créer un seul champ pour tous les gains (séparés par des espaces ou virgules)
        gains_placeholder = " ".join([f"J{idx+1}:450000" for idx in range(len(participants))])
        self.gains_input = discord.ui.TextInput(
            label=f"Gains de tous les joueurs ({len(participants)})",
            placeholder=gains_placeholder[:100],  # Limiter la taille du placeholder
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True
        )
        self.add_item(self.gains_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        from cogs.cayo_perico.optimizer import (
            PRIMARY_TARGETS,
            HARD_MODE_MULTIPLIER,
            SAFE_VALUE,
            calculate_default_shares,
            calculate_net_total,
            calculate_player_gains,
            format_next_heist_time,
            format_hard_mode_deadline,
            format_duration,
        )
        from datetime import datetime, timezone

        # Parser le temps de mission (format mm:ss)
        mission_time_str = self.mission_time_input.value.strip()
        try:
            if ":" in mission_time_str:
                minutes, seconds = mission_time_str.split(":")
                mission_time_seconds = int(minutes) * 60 + int(seconds)
            else:
                mission_time_seconds = int(mission_time_str) * 60  # Si juste un nombre, on assume des minutes
        except:
            mission_time_seconds = 0

        # Parser la valeur du coffre-fort
        try:
            safe_value_real = int(self.safe_value_input.value.strip())
        except:
            safe_value_real = SAFE_VALUE  # Valeur par défaut

        # Parser les gains réels (format: "450000 380000" ou "J1:450000 J2:380000" ou "450000, 380000")
        real_gains = {}
        gains_text = self.gains_input.value.strip()

        # Essayer de parser avec différents séparateurs
        import re
        # Extraire seulement les nombres de 5+ chiffres (montants GTA$)
        # Cela ignore automatiquement les "1", "2" dans "J1:", "J2:", etc.
        numbers = re.findall(r'(\d{5,})', gains_text)

        for idx, participant_id in enumerate(self.participants):
            if idx < len(numbers):
                try:
                    real_gains[participant_id] = int(numbers[idx])
                except ValueError:
                    real_gains[participant_id] = 0
            else:
                real_gains[participant_id] = 0

        total_real = sum(real_gains.values())
        finished_at = datetime.now(timezone.utc)
        await self.service.close_heist(self.heist["id"], total_real, self.elite_completed, finished_at)

        # Mettre à jour le temps de mission
        await self._update_mission_time(self.heist["id"], mission_time_seconds)

        # Sauvegarder la vraie valeur du coffre-fort
        await self._update_safe_amount(self.heist["id"], safe_value_real)

        # Enregistrer le cooldown actif pour les notifications
        await self._register_active_cooldown(self.heist, finished_at, len(self.participants))

        # Récupérer le heist complet avec tous les timestamps
        heist_full = await self.service.get_heist_by_id(self.heist["id"])
        if heist_full is None:
            await interaction.followup.send("Erreur : impossible de récupérer le braquage.", ephemeral=True)
            return

        # Calculer les gains prévus avec les nouvelles formules
        # 1. Récupérer les infos du heist
        primary_target = heist_full.get("primary_loot", "tequila")
        hard_mode = heist_full.get("hard_mode", False)
        optimized_plan = heist_full.get("optimized_plan") or []

        # 2. Calculer la valeur primaire (avec bonus hard mode 10% si applicable)
        primary_value = PRIMARY_TARGETS[primary_target]["value"]
        if hard_mode:
            primary_value = int(primary_value * HARD_MODE_MULTIPLIER)

        # 3. Calculer la valeur secondaire (somme des sacs)
        secondary_value = sum(bag.get("total_value", 0) for bag in optimized_plan)

        # 4. Calculer le total net (primaire + secondaires + coffre) × 88%
        # Utiliser la vraie valeur du coffre saisie par l'utilisateur au lieu de la constante
        total_net = calculate_net_total(primary_value, secondary_value, safe_value_real)

        # 5. Récupérer ou calculer les parts
        custom_shares = await self.service.get_custom_shares(self.heist["id"])
        if custom_shares:
            # Convertir en liste dans l'ordre des participants
            shares = [custom_shares.get(pid, 25.0) for pid in self.participants]
        else:
            shares = calculate_default_shares(len(self.participants))

        # 6. Calculer les gains prévus par joueur (avec bonus Elite si validé)
        predicted_gains_list = calculate_player_gains(total_net, shares, self.elite_completed, hard_mode)
        predicted_gains = {self.participants[idx]: predicted_gains_list[idx] for idx in range(len(self.participants))}

        # Sauvegarder les gains réels et prévus en DB (avec bonus Elite inclus)
        await self.service.save_real_gains(self.heist["id"], real_gains, predicted_gains)

        # Refresh les stats matérialisées pour refléter immédiatement le nouveau braquage
        await self.service.refresh_materialized_stats()

        # 7. Calculer le temps de préparation et formater le temps de mission saisi
        prep_time = format_duration(heist_full.get("created_at"), heist_full.get("ready_at"))

        # Formater le temps de mission saisi par l'utilisateur
        minutes_mission = mission_time_seconds // 60
        seconds_mission = mission_time_seconds % 60
        if minutes_mission > 0:
            mission_time = f"{minutes_mission}min {seconds_mission}s"
        else:
            mission_time = f"{seconds_mission}s"

        # 8. Calculer les timers cooldown
        num_players = len(self.participants)
        next_heist = format_next_heist_time(finished_at, num_players)
        hard_mode_deadline = format_hard_mode_deadline(finished_at, num_players)

        # Afficher les résultats
        embed = discord.Embed(
            title="📊 Résultats du braquage Cayo Perico",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Comparaison gains",
            value=format_results_comparison(predicted_gains, real_gains, self.participants),
            inline=False
        )

        # Ajouter les temps
        embed.add_field(
            name="⏱️ Statistiques de temps",
            value=(
                f"• Temps de préparation : **{prep_time}**\n"
                f"• Temps de mission : **{mission_time}**\n"
                f"• Valeur coffre-fort : **{safe_value_real:,} GTA$**".replace(",", " ")
            ),
            inline=False
        )

        # Ajouter les timers cooldown
        embed.add_field(
            name="⏰ Prochain braquage",
            value=f"{next_heist}\n{hard_mode_deadline}",
            inline=False
        )

        embed.add_field(
            name="Statut",
            value=f"🏁 Braquage terminé et archivé\n{'🏆 Défi Elite validé !' if self.elite_completed else ''}",
            inline=False
        )

        # Envoyer l'embed de résultats
        await interaction.followup.send(embed=embed, ephemeral=False)

        # Supprimer le message principal de préparation
        try:
            # Récupérer le message original du braquage
            if interaction.guild and heist_full.get("channel_id") and heist_full.get("message_id"):
                channel = interaction.guild.get_channel(heist_full["channel_id"])
                if channel:
                    try:
                        original_message = await channel.fetch_message(heist_full["message_id"])
                        await original_message.delete()
                        logger.info(f"[Cayo] Message principal du braquage {self.heist['id']} supprimé")
                    except discord.NotFound:
                        logger.warning(f"[Cayo] Message principal du braquage {self.heist['id']} déjà supprimé")
                    except Exception as e:
                        logger.error(f"[Cayo] Erreur lors de la suppression du message principal: {e}")
        except Exception as e:
            logger.error(f"[Cayo] Erreur lors de la récupération du message principal: {e}")

        # Note: Le message Elite est éphémère (ephemeral=True), donc il se supprime automatiquement
        # Pas besoin de le supprimer manuellement

    async def _update_mission_time(self, heist_id: int, mission_time_seconds: int):
        """Met à jour le temps de mission dans la table cayo_heists."""
        if self.service.db is None:
            return

        query = """
            UPDATE cayo_heists
            SET mission_time_seconds = %s
            WHERE id = %s
        """

        await self.service.db.execute(query, mission_time_seconds, heist_id)
        logger.info(f"[Cayo] Temps de mission enregistré: {mission_time_seconds}s pour heist {heist_id}")

    async def _update_safe_amount(self, heist_id: int, safe_amount: int):
        """Met à jour la valeur du coffre-fort dans la table cayo_heists."""
        if self.service.db is None:
            return

        query = """
            UPDATE cayo_heists
            SET safe_amount = %s
            WHERE id = %s
        """

        await self.service.db.execute(query, safe_amount, heist_id)
        logger.info(f"[Cayo] Valeur coffre-fort enregistrée: {safe_amount} GTA$ pour heist {heist_id}")

    async def _register_active_cooldown(self, heist: Dict, finished_at: datetime, num_players: int):
        """Enregistre le cooldown actif pour les notifications."""
        if self.service.db is None:
            return

        try:
            # Récupérer le leader_user_id (ID interne)
            leader_user_id = await self.service.get_or_create_user_id(heist['leader_id'])

            query = """
                INSERT INTO cayo_active_cooldowns
                    (heist_id, leader_user_id, guild_id, finished_at, num_players)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (heist_id) DO NOTHING
            """

            await self.service.db.execute(
                query,
                heist['id'],
                leader_user_id,
                heist['guild_id'],
                finished_at,
                num_players
            )

            logger.info(f"[Cayo] Cooldown actif enregistré pour heist {heist['id']}")

        except Exception as e:
            logger.error(f"[Cayo] Erreur lors de l'enregistrement du cooldown actif: {e}")


# ==================== COG PRINCIPAL ====================

class CayoPerico(commands.Cog):
    """Cog pour la commande /cayo-perico et la gestion des braquages Cayo."""

    def __init__(self, bot: commands.Bot, service: Optional[CayoPericoService] = None):
        self.bot = bot
        self.logger = logger
        self.service = service or CayoPericoService(getattr(bot, "db", None))

    @app_commands.command(
        name="cayo-perico",
        description="Préparer un braquage Cayo Perico avec calculateur optimisé",
    )
    async def cayo_perico(self, interaction: discord.Interaction) -> None:
        """
        Ouvre un Select pour configurer un braquage Cayo Perico.
        """
        if self.service is None or self.service.db is None:
            await interaction.response.send_message(
                "La base de données n'est pas disponible, la fonctionnalité Cayo Perico est désactivée.",
                ephemeral=True,
            )
            return

        # Envoyer un Select pour choisir l'objectif principal
        view = PrimaryTargetView(self.service)
        await interaction.response.send_message(
            "🎯 **Choisir l'objectif principal du braquage Cayo Perico :**",
            view=view,
            ephemeral=True
        )


# ==================== ENREGISTREMENT VIEW PERSISTANTE ====================

def _cayo_view_factory(bot: commands.Bot) -> discord.ui.View:
    """
    Factory utilisée par utils.view_manager pour recréer la View persistante
    au redémarrage du bot.

    Note: On crée une View avec tous les boutons possibles car on ne connaît pas
    le statut spécifique de chaque braquage au redémarrage. Les callbacks
    récupèrent le braquage depuis la DB et vérifient le statut dynamiquement.
    """
    service = CayoPericoService(getattr(bot, "db", None))

    # Créer une View avec tous les boutons (statut "ready" a tous les boutons)
    view = discord.ui.View(timeout=None)
    view.add_item(DetailsButton(service))
    view.add_item(JoinButton(service))
    view.add_item(LeaveButton(service))
    view.add_item(ReadyButton(service))
    view.add_item(FinishButton(service))

    return view


# On enregistre la factory dès l'import du module
register_persistent_view(_cayo_view_factory)


async def setup(bot: commands.Bot):
    """
    Fonction appelée par discord.ext.commands pour charger le cog.
    """
    service = CayoPericoService(getattr(bot, "db", None))
    await bot.add_cog(CayoPerico(bot, service))
    logger.info("Cog CayoPerico V2 chargé")
