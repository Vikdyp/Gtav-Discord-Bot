# cogs/general/admin_commands.py
"""
Commande slash /admin regroupée (ping, update-usernames, db-check).
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.logging_config import logger
from .services.admin_commands_service import AdminCommandsService


class GeneralCommands(commands.Cog):
    """Commande d'administration regroupée."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logger
        self.service = AdminCommandsService(getattr(bot, "db", None))

    @app_commands.command(
        name="admin",
        description="[Admin] Outils : ping, update-usernames, db-check"
    )
    @app_commands.describe(
        action="Action à exécuter",
        db_action="Sous-action DB (count, list_heists, clean_heists, clean_all)"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="ping", value="ping"),
            app_commands.Choice(name="update-usernames", value="update_usernames"),
            app_commands.Choice(name="db-check", value="db_check"),
        ],
        db_action=[
            app_commands.Choice(name="count", value="count"),
            app_commands.Choice(name="list_heists", value="list_heists"),
            app_commands.Choice(name="clean_heists", value="clean_heists"),
            app_commands.Choice(name="clean_all", value="clean_all"),
        ],
    )
    @app_commands.default_permissions(administrator=True)
    async def admin(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        db_action: Optional[app_commands.Choice[str]] = None
    ):
        if action.value == "ping":
            await self._handle_ping(interaction)
        elif action.value == "update_usernames":
            await self._handle_update_usernames(interaction)
        else:
            await self._handle_db_check(interaction, db_action.value if db_action else None)

    async def _handle_ping(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        latency_ms = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latence: **{latency_ms}ms**",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        self.logger.info(f"Commande admin ping utilisée par {interaction.user} (latence: {latency_ms}ms)")

    async def _handle_update_usernames(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("⚠️ Cette commande doit être utilisée dans un serveur.", ephemeral=True)
            return

        db = getattr(self.bot, "db", None)
        if db is None:
            await interaction.followup.send("⚠️ Base de données non disponible.", ephemeral=True)
            return

        try:
            query = """
                SELECT DISTINCT u.id, u.discord_id
                FROM users u
                INNER JOIN cayo_heists h ON h.leader_user_id = u.id
                WHERE h.guild_id = %s
                UNION
                SELECT DISTINCT u.id, u.discord_id
                FROM users u
                INNER JOIN cayo_participants cp ON cp.user_id = u.id
                INNER JOIN cayo_heists h ON h.id = cp.heist_id
                WHERE h.guild_id = %s
            """
            rows = await db.fetch(query, interaction.guild.id, interaction.guild.id)

            updated = 0
            not_found = 0

            for row in rows:
                discord_id = row["discord_id"]
                try:
                    member = await interaction.guild.fetch_member(discord_id)
                    update_query = """
                        UPDATE users
                        SET username = %s,
                            display_name = %s,
                            updated_at = NOW()
                        WHERE discord_id = %s
                    """
                    await db.execute(update_query, member.name, member.display_name, discord_id)
                    updated += 1
                except discord.NotFound:
                    not_found += 1
                    self.logger.warning(f"Membre Discord {discord_id} introuvable dans le serveur")
                except Exception as e:
                    self.logger.error(f"Erreur lors de la mise à jour de {discord_id}: {e}")

            embed = discord.Embed(
                title="✅ Pseudos mis à jour",
                description=(
                    f"**{updated}** utilisateurs mis à jour\n"
                    f"**{not_found}** utilisateurs introuvables (ont quitté le serveur)"
                ),
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.logger.info(f"[Update Usernames] {updated} pseudos mis à jour, {not_found} introuvables")

        except Exception as e:
            embed = discord.Embed(
                title="⚠️ Erreur",
                description=f"```\n{e}\n```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.logger.error(f"[Update Usernames] Erreur : {e}")

    async def _handle_db_check(self, interaction: discord.Interaction, db_action: Optional[str]):
        await interaction.response.defer(ephemeral=True)

        db = getattr(self.bot, "db", None)
        if db is None:
            await interaction.followup.send("⚠️ Base de données non disponible.", ephemeral=True)
            return

        if db_action == "count":
            counts = {}
            tables = ["users", "cayo_heists", "cayo_participants", "cayo_results"]
            for table_name in tables:
                query = f"SELECT COUNT(*) AS count FROM {table_name};"
                try:
                    row = await db.fetchrow(query)
                    counts[table_name] = row.get("count", 0) if row else 0
                except Exception as e:
                    counts[table_name] = f"Erreur: {str(e)}"

            embed = discord.Embed(
                title="📊 Nombre de lignes par table",
                color=discord.Color.blue()
            )
            for table_name, count in counts.items():
                embed.add_field(
                    name=f"🗂️ {table_name}",
                    value=f"`{count}` ligne(s)",
                    inline=True
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if db_action == "list_heists":
            query = """
            SELECT
                h.id,
                h.status,
                h.primary_loot,
                h.hard_mode,
                u.discord_id AS leader_id,
                h.created_at,
                (SELECT COUNT(*) FROM cayo_participants WHERE heist_id = h.id) AS num_participants
            FROM cayo_heists h
            JOIN users u ON h.leader_user_id = u.id
            ORDER BY h.created_at DESC
            LIMIT 20;
            """
            rows = await db.fetch(query)

            if not rows:
                await interaction.followup.send("✅ Aucun braquage dans la base de données", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"🗂️ Braquages Cayo Perico ({len(rows)} trouvés)",
                color=discord.Color.gold()
            )
            for row in rows[:10]:
                heist_id = row.get("id")
                status = row.get("status")
                primary = row.get("primary_loot")
                hard_mode = row.get("hard_mode")
                leader_id = row.get("leader_id")
                created = row.get("created_at")
                num_part = row.get("num_participants")

                status_emoji = {
                    "pending": "⏳",
                    "ready": "✅",
                    "finished": "🏁"
                }.get(status, "❔")

                embed.add_field(
                    name=f"{status_emoji} Heist #{heist_id} - {status}",
                    value=(
                        f"👤 Organisateur: <@{leader_id}>\n"
                        f"🎯 Objectif: {primary}\n"
                        f"💪 Hard mode: {'✅' if hard_mode else '❌'}\n"
                        f"👥 Participants: {num_part}\n"
                        f"🕒 Créé: {created.strftime('%Y-%m-%d %H:%M') if created else 'N/A'}"
                    ),
                    inline=False
                )

            if len(rows) > 10:
                embed.set_footer(text=f"... et {len(rows) - 10} autre(s) braquage(s)")

            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if db_action == "clean_heists":
            row = await db.fetchrow("SELECT COUNT(*) AS count FROM cayo_heists;")
            count = row.get("count", 0) if row else 0
            if count == 0:
                await interaction.followup.send("✅ Aucun braquage à nettoyer", ephemeral=True)
                return

            await db.execute("DELETE FROM cayo_heists;")
            embed = discord.Embed(
                title="🧹 Nettoyage effectué",
                description=f"✅ {count} braquage(s) supprimé(s) (+ participants associés)",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"[DB] {count} braquages nettoyés par {interaction.user}")
            return

        if db_action == "clean_all":
            tables_queries = {
                "cayo_heists": "SELECT COUNT(*) AS count FROM cayo_heists;",
                "cayo_participants": "SELECT COUNT(*) AS count FROM cayo_participants;",
                "cayo_results": "SELECT COUNT(*) AS count FROM cayo_results;",
                "users": "SELECT COUNT(*) AS count FROM users;"
            }

            counts_before = {}
            for table, query in tables_queries.items():
                try:
                    row = await db.fetchrow(query)
                    counts_before[table] = row.get("count", 0) if row else 0
                except Exception:
                    counts_before[table] = 0

            await db.execute("DELETE FROM cayo_results;")
            await db.execute("DELETE FROM cayo_heists;")
            await db.execute("DELETE FROM users;")

            embed = discord.Embed(
                title="🧹 Nettoyage complet effectué",
                description="⚠️ **TOUTES les données Cayo Perico ont été supprimées**",
                color=discord.Color.red()
            )
            embed.add_field(
                name="📊 Lignes supprimées",
                value=(
                    f"👤 `users`: {counts_before['users']}\n"
                    f"🎯 `cayo_heists`: {counts_before['cayo_heists']}\n"
                    f"👥 `cayo_participants`: {counts_before['cayo_participants']}\n"
                    f"🏁 `cayo_results`: {counts_before['cayo_results']}"
                ),
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.warning(f"[DB] Nettoyage complet Cayo Perico par {interaction.user}")
            return

        await interaction.followup.send("⚠️ db_action requis pour db-check.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCommands(bot))
    logger.info("Cog GeneralCommands chargé")
