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
            value="• Active le **mode difficile** si nécessaire (+25% sur objectif primaire)\n"
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
            value="• Active le **mode difficile** si nécessaire (+25% sur objectif primaire)\n"
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

        # Créer le braquage en DB
        heist_id = await self.service.create_heist(
            guild_id=interaction.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            leader_discord_id=interaction.user.id,
            primary_loot=self.primary_target,
            secondary_loot=self.secondary_loot,
            estimated_loot=total_loot,
        )

        # Sauvegarder le plan optimisé
        await self.service.update_optimized_plan(heist_id, optimized_bags)

        # Ajouter l'organisateur comme participant
        await self.service.add_participant(heist_id, interaction.user.id)

        await interaction.followup.send(
            "✅ Braquage Cayo Perico créé avec succès !",
            ephemeral=True
        )


# ==================== VIEW PRINCIPALE (PERSISTANTE) ====================

class CayoPericoView(discord.ui.View):
    """
    View des boutons Cayo Perico.
    timeout=None -> boutons persistants tant que le bot tourne.
    """

    def __init__(self, service: CayoPericoService):
        super().__init__(timeout=None)
        self.service = service

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

        try:
            await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            logger.error(f"[Cayo] Erreur lors de la mise à jour du message: {e}")

    @discord.ui.button(
        label="Rejoindre le braquage",
        style=discord.ButtonStyle.success,
        custom_id="cayo_join",
    )
    async def join_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        # Répondre immédiatement à l'interaction
        await interaction.response.send_message(
            "Tu as rejoint le braquage.", ephemeral=True
        )

        # Ajouter le participant et recalculer le plan
        await self.service.add_participant(heist["id"], interaction.user.id)
        await self._update_message_embed(interaction, heist)

    @discord.ui.button(
        label="Quitter",
        style=discord.ButtonStyle.danger,
        custom_id="cayo_leave",
    )
    async def leave_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
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
                pass  # Le message n'existe peut-être plus

            return

        # Répondre immédiatement à l'interaction
        await interaction.response.send_message(
            "Tu as quitté le braquage.", ephemeral=True
        )

        # Retirer le participant et recalculer le plan
        await self.service.remove_participant(heist["id"], interaction.user.id)
        await self._update_message_embed(interaction, heist)

    @discord.ui.button(
        label="Braquage prêt",
        style=discord.ButtonStyle.primary,
        custom_id="cayo_ready",
    )
    async def ready_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
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
                    bag_info = optimized_plan[idx]
                    private_msg = format_bag_plan_private(bag_info, idx + 1)
                    await user.send(
                        f"📋 **Ton plan de sac pour le Cayo de <@{heist['leader_id']}>**\n\n{private_msg}"
                    )
            except:
                pass  # L'utilisateur a bloqué les DM

        await interaction.followup.send(
            f"✅ Le Cayo Perico de <@{heist['leader_id']}> est prêt !\n"
            f"📨 Chaque participant a reçu son plan de sac en privé.",
            allowed_mentions=discord.AllowedMentions(users=True),
        )

    @discord.ui.button(
        label="🏁 Terminer",
        style=discord.ButtonStyle.secondary,
        custom_id="cayo_finish",
    )
    async def finish_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
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

        # Ouvrir Modal pour saisir les gains réels
        participants = await self.service.get_participants(heist["id"])
        modal = FinishHeistModal(heist, participants, self.service)
        await interaction.response.send_modal(modal)


class FinishHeistModal(discord.ui.Modal, title="Résultats du braquage"):
    """Modal pour saisir les gains réels de chaque participant."""

    def __init__(self, heist: Dict, participants: List[int], service: CayoPericoService):
        super().__init__()
        self.heist = heist
        self.participants = participants
        self.service = service

        # Créer un TextInput par participant (max 5 à cause limite Discord)
        for idx, participant_id in enumerate(participants[:5]):
            text_input = discord.ui.TextInput(
                label=f"Gain de Joueur {idx + 1}",
                placeholder="Ex: 450000",
                max_length=10,
                required=True
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Parser les gains réels
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
        await self.service.close_heist(self.heist["id"], total_real)

        # Construire les gains prévus depuis le plan
        optimized_plan = self.heist.get("optimized_plan") or []
        predicted_gains = {}
        for idx, participant_id in enumerate(self.participants):
            if idx < len(optimized_plan):
                predicted_gains[participant_id] = optimized_plan[idx].get("total_value", 0)
            else:
                predicted_gains[participant_id] = 0

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

        embed.add_field(
            name="Statut",
            value="🏁 Braquage terminé et archivé",
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
