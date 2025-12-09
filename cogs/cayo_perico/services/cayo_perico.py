# cogs/gta/cayo_perico.py
"""
Fonctionnalité Cayo Perico :
- Création de braquage via /cayo-perico (Modal)
- Gestion des participants via boutons
- Boutons persistants (timeout=None) gérés via utils.view_manager
"""

from typing import Optional, Dict, List

import discord
from discord import app_commands
from discord.ext import commands

from utils.logging_config import logger
from utils.view_manager import register_persistent_view
from cayo_perico.services.cayo_perico_service import CayoPericoService


# ---------------------- Utilitaires internes ----------------------


def _format_secondary_loot(secondary_loot: Dict[str, int]) -> str:
    """Formate le loot secondaire en texte lisible."""
    labels = {
        "gold": "Or",
        "coke": "Cocaïne",
        "weed": "Weed",
        "paintings": "Tableaux",
        "cash": "Billets",
    }

    parts: List[str] = []
    for key, label in labels.items():
        qty = int(secondary_loot.get(key, 0) or 0)
        if qty > 0:
            parts.append(f"{qty}x {label}")

    if not parts:
        return "Aucun"

    return ", ".join(parts)


def _build_heist_embed(
    heist: Dict,
    participants: List[int],
) -> discord.Embed:
    """Construit l'embed principal d'un braquage Cayo."""
    primary_loot = heist["primary_loot"]
    secondary_loot = heist.get("secondary_loot") or {}
    estimated_loot = heist.get("estimated_loot")
    status = heist.get("status", "pending")
    leader_id = heist["leader_id"]

    participants_mentions = (
        ", ".join(f"<@{uid}>" for uid in participants) if participants else "*aucun pour l'instant*"
    )

    status_label = {
        "pending": "⏳ En préparation",
        "ready": "✅ Prêt",
        "finished": "🏁 Terminé",
        "cancelled": "❌ Annulé",
    }.get(status, status)

    embed = discord.Embed(
        title="💣 Préparation Cayo Perico",
        color=discord.Color.gold(),
    )

    embed.add_field(name="Organisateur", value=f"<@{leader_id}>", inline=True)
    embed.add_field(name="Statut", value=status_label, inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    embed.add_field(name="Objectif principal", value=str(primary_loot), inline=True)
    embed.add_field(
        name="Secondaires",
        value=_format_secondary_loot(secondary_loot),
        inline=True,
    )

    if estimated_loot is not None:
        embed.add_field(
            name="Butin estimé",
            value=f"**{estimated_loot:,}$**".replace(",", " "),
            inline=True,
        )

    embed.add_field(
        name="Participants",
        value=participants_mentions,
        inline=False,
    )

    return embed


# ---------------------- Service / View / Modal ----------------------


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
        new_embed = _build_heist_embed(heist, participants)

        try:
            await interaction.message.edit(embed=new_embed, view=self)
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

        await self.service.add_participant(heist["id"], interaction.user.id)
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        await self._update_message_embed(interaction, heist)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Tu as rejoint le braquage.", ephemeral=True
            )

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

        await self.service.remove_participant(heist["id"], interaction.user.id)
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        await self._update_message_embed(interaction, heist)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                "Tu as quitté le braquage.", ephemeral=True
            )

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

        await self.service.mark_ready(heist["id"])
        heist = await self._get_heist_for_interaction(interaction)
        if heist is None:
            return

        await self._update_message_embed(interaction, heist)

        await interaction.followup.send(
            f"✅ Le Cayo Perico de <@{heist['leader_id']}> est prêt !",
            allowed_mentions=discord.AllowedMentions(users=True),
        )


class CayoPericoSetupModal(discord.ui.Modal, title="Préparation Cayo Perico"):
    """
    Modal pour configurer un braquage Cayo Perico.
    """

    primary_loot = discord.ui.TextInput(
        label="Objectif principal",
        placeholder="Tequila, Diamant rose, Collier, etc.",
        max_length=100,
    )

    gold = discord.ui.TextInput(
        label="Or",
        required=False,
        placeholder="Ex: 3",
        max_length=10,
    )

    coke = discord.ui.TextInput(
        label="Cocaïne",
        required=False,
        placeholder="Ex: 2",
        max_length=10,
    )

    weed = discord.ui.TextInput(
        label="Weed",
        required=False,
        placeholder="Ex: 1",
        max_length=10,
    )

    paintings = discord.ui.TextInput(
        label="Tableaux",
        required=False,
        placeholder="Ex: 2",
        max_length=10,
    )
    cash = discord.ui.TextInput(
        label="Billets",
        required=False,
        placeholder="Ex: 5",
        max_length=10,
    )

    def __init__(self, service: CayoPericoService):
        super().__init__()
        self.service = service

    @staticmethod
    def _parse_int_field(value: str) -> int:
        value = value.strip()
        if not value:
            return 0
        try:
            return max(int(value), 0)
        except ValueError:
            return 0

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message(
                "Cette commande ne peut être utilisée qu'en serveur.",
                ephemeral=True,
            )
            return

        secondary_loot = {
            "gold": self._parse_int_field(self.gold.value),
            "coke": self._parse_int_field(self.coke.value),
            "weed": self._parse_int_field(self.weed.value),
            "paintings": self._parse_int_field(self.paintings.value),
        }

        # TODO: calculer un butin estimé plus intelligent.
        estimated_loot: Optional[int] = None

        # View pour les boutons
        view = CayoPericoView(self.service)

        # Heist provisoire pour l'affichage initial (avant écriture en BDD)
        temp_heist = {
            "id": 0,
            "guild_id": interaction.guild.id,
            "channel_id": interaction.channel.id,
            "message_id": 0,
            "leader_id": interaction.user.id,
            "primary_loot": self.primary_loot.value,
            "secondary_loot": secondary_loot,
            "estimated_loot": estimated_loot,
            "final_loot": None,
            "status": "pending",
        }
        embed = _build_heist_embed(temp_heist, participants=[interaction.user.id])

        await interaction.response.send_message(embed=embed, view=view)
        message = await interaction.original_response()

        # Création réelle du heist en BDD
        heist_id = await self.service.create_heist(
            guild_id=interaction.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
            leader_discord_id=interaction.user.id,
            primary_loot=self.primary_loot.value,
            secondary_loot=secondary_loot,
            estimated_loot=estimated_loot,
        )

        # Enregistrer l'organisateur comme participant
        await self.service.add_participant(heist_id, interaction.user.id)

        # Recharger depuis la BDD pour être cohérent
        heist = await self.service.get_heist_by_message(
            guild_id=interaction.guild.id,
            channel_id=message.channel.id,
            message_id=message.id,
        )
        if heist is not None:
            participants = await self.service.get_participants(heist["id"])
            final_embed = _build_heist_embed(heist, participants)
            try:
                await message.edit(embed=final_embed, view=view)
            except Exception as e:
                logger.error(f"[Cayo] Erreur lors de la mise à jour initiale du message: {e}")


# ---------------------- Cog principal ----------------------


class CayoPerico(commands.Cog):
    """Cog pour la commande /cayo-perico et la gestion des braquages Cayo."""

    def __init__(self, bot: commands.Bot, service: Optional[CayoPericoService] = None):
        self.bot = bot
        self.logger = logger
        self.service = service or CayoPericoService(getattr(bot, "db", None))

    @app_commands.command(
        name="cayo-perico",
        description="Préparer un braquage Cayo Perico avec formulaire et boutons.",
    )
    async def cayo_perico(self, interaction: discord.Interaction) -> None:
        """
        Ouvre un Modal pour configurer un braquage Cayo Perico.
        """
        if self.service is None or self.service.db is None:
            await interaction.response.send_message(
                "La base de données n'est pas disponible, la fonctionnalité Cayo Perico est désactivée.",
                ephemeral=True,
            )
            return

        modal = CayoPericoSetupModal(self.service)
        await interaction.response.send_modal(modal)


# ---------- Enregistrement de la View persistante via view_manager ----------


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
    logger.info("Cog CayoPerico chargé")
