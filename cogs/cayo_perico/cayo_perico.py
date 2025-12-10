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

import discord
from discord import app_commands
from discord.ext import commands

from utils.logging_config import logger
from utils.view_manager import register_persistent_view
from .services.cayo_perico_service import CayoPericoService
from .optimizer import (
    PRIMARY_TARGETS,
    SECONDARY_TARGETS,
    calculate_estimated_loot,
    optimize_bags,
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
        label="Tableaux (0-9)",
        placeholder="0",
        max_length=1,
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
        # Parser les quantités
        secondary_loot = {
            "gold": _parse_int_field(self.gold.value),
            "cocaine": _parse_int_field(self.cocaine.value),
            "paintings": _parse_int_field(self.paintings.value),
            "weed": _parse_int_field(self.weed.value),
            "cash": _parse_int_field(self.cash.value),
        }

        # Créer un embed de configuration
        hard_mode = False
        # Calculer avec les sacs optimisés (solo par défaut)
        optimized_bags = optimize_bags(secondary_loot, num_players=1, is_solo=True)
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

        embed.add_field(
            name="ℹ️ Prochaines étapes",
            value="• Active le **mode difficile** si nécessaire (+10% sur objectif primaire)\n"
                  "• Clique sur **Confirmer** pour créer le braquage",
            inline=False
        )

        # View avec boutons de configuration
        view = ConfigView(self.primary_target, secondary_loot, self.service)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ConfigView(discord.ui.View):
    """View pour configurer le mode difficile et confirmer."""

    def __init__(self, primary_target: str, secondary_loot: Dict[str, int], service: CayoPericoService):
        super().__init__(timeout=300)
        self.primary_target = primary_target
        self.secondary_loot = secondary_loot
        self.hard_mode = False
        self.service = service

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
        optimized_bags = optimize_bags(self.secondary_loot, num_players=1, is_solo=True)
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

        # Optimiser les sacs et calculer le butin estimé RÉEL
        optimized_bags = optimize_bags(self.secondary_loot, num_players=1, is_solo=True)
        total_loot = calculate_estimated_loot(self.primary_target, optimized_bags, self.hard_mode)

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

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(optimized_bags, [interaction.user.id]),
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
            is_solo=(num_players == 1)
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

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(optimized_bags, participants),
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
            is_solo=(num_players == 1)
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

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(optimized_bags, participants),
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
        await self._update_message_embed(interaction, heist)

        # Récupérer le heist complet avec le plan optimisé depuis la DB
        heist_full = await self.service.get_heist_by_id(heist["id"])
        if heist_full is None:
            await interaction.followup.send("Erreur : impossible de récupérer le braquage.", ephemeral=True)
            return

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
            is_solo=(num_players == 1)
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

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(optimized_bags, participants),
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
        modal = FinishHeistModal(self.heist, self.participants, self.service, self.elite_completed)
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
        modal = SharesModal(heist, participants, self.service)
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
            is_solo=(num_players == 1)
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

        embed.add_field(
            name="🎒 Plan de sac optimisé",
            value=format_bag_plan_embed(optimized_bags, participants),
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

    def __init__(self, heist: Dict, participants: List[int], service: CayoPericoService):
        super().__init__()
        self.heist = heist
        self.participants = participants
        self.service = service

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

        await interaction.response.send_message(
            "✅ Parts personnalisées enregistrées !", ephemeral=True
        )


class FinishHeistModal(discord.ui.Modal, title="Résultats du braquage"):
    """Modal pour saisir les gains réels de chaque participant."""

    def __init__(self, heist: Dict, participants: List[int], service: CayoPericoService, elite_completed: bool):
        super().__init__()
        self.heist = heist
        self.participants = participants
        self.service = service
        self.elite_completed = elite_completed  # Déjà déterminé par le Select

        # Créer un TextInput par participant (max 4 selon limite joueurs)
        for idx, participant_id in enumerate(participants[:4]):
            text_input = discord.ui.TextInput(
                label=f"Gain Joueur {idx + 1}",
                placeholder="Ex: 450000",
                max_length=10,
                required=True
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

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

        # Parser les gains réels (tous les enfants sont maintenant des TextInput de gains)
        real_gains = {}
        for idx, item in enumerate(self.children):
            if idx >= len(self.participants):
                break
            participant_id = self.participants[idx]
            try:
                real_gain = int(item.value.strip())
                real_gains[participant_id] = real_gain
            except ValueError:
                real_gains[participant_id] = 0

        # Sauvegarder en DB
        await self.service.save_real_gains(self.heist["id"], real_gains)

        total_real = sum(real_gains.values())
        finished_at = datetime.now(timezone.utc)
        await self.service.close_heist(self.heist["id"], total_real, self.elite_completed, finished_at)

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
        total_net = calculate_net_total(primary_value, secondary_value, SAFE_VALUE)

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

        # 7. Calculer les temps de préparation et mission
        prep_time = format_duration(heist_full.get("created_at"), heist_full.get("ready_at"))
        mission_time = format_duration(heist_full.get("ready_at"), heist_full.get("finished_at"))

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
                f"• Temps de mission : **{mission_time}**"
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

        await interaction.followup.send(embed=embed)


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
    """
    service = CayoPericoService(getattr(bot, "db", None))
    return CayoPericoView(service)


# On enregistre la factory dès l'import du module
register_persistent_view(_cayo_view_factory)


async def setup(bot: commands.Bot):
    """
    Fonction appelée par discord.ext.commands pour charger le cog.
    """
    service = CayoPericoService(getattr(bot, "db", None))
    await bot.add_cog(CayoPerico(bot, service))
    logger.info("Cog CayoPerico V2 chargé")
