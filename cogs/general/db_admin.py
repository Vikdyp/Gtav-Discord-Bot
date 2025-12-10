# cogs/general/db_admin.py
"""
Commandes d'administration de la base de données.
ATTENTION : Ces commandes sont temporaires et doivent être utilisées avec précaution.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

from utils.logging_config import logger


class DBAdmin(commands.Cog):
    """Commandes temporaires d'administration de la BDD."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = getattr(bot, "db", None)

    @app_commands.command(name="db-check", description="🔍 Inspecter les tables Cayo Perico")
    @app_commands.describe(
        action="Action à effectuer",
        table="Table à inspecter (optionnel)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📋 Compter les lignes", value="count"),
        app_commands.Choice(name="📊 Voir les braquages actifs", value="list_heists"),
        app_commands.Choice(name="🗑️ Nettoyer tous les braquages", value="clean_heists"),
        app_commands.Choice(name="🧹 Nettoyer TOUTES les données Cayo", value="clean_all"),
    ])
    async def db_check(
        self,
        interaction: discord.Interaction,
        action: str,
        table: Optional[str] = None
    ):
        """Commande d'inspection et nettoyage de la BDD."""
        await interaction.response.defer(ephemeral=True)

        if self.db is None:
            await interaction.followup.send("❌ Base de données non disponible", ephemeral=True)
            return

        try:
            # ---- COMPTER LES LIGNES ----
            if action == "count":
                counts = {}
                tables = ["users", "cayo_heists", "cayo_participants", "cayo_results"]

                for table_name in tables:
                    query = f"SELECT COUNT(*) FROM {table_name};"
                    try:
                        row = await self.db.fetchrow(query)
                        counts[table_name] = row[0] if row else 0
                    except Exception as e:
                        counts[table_name] = f"Erreur: {str(e)}"

                embed = discord.Embed(
                    title="📊 Nombre de lignes par table",
                    color=discord.Color.blue()
                )

                for table_name, count in counts.items():
                    embed.add_field(
                        name=f"📋 {table_name}",
                        value=f"`{count}` ligne(s)",
                        inline=True
                    )

                await interaction.followup.send(embed=embed, ephemeral=True)

            # ---- LISTER LES BRAQUAGES ----
            elif action == "list_heists":
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

                rows = await self.db.fetch(query)

                if not rows:
                    await interaction.followup.send("✅ Aucun braquage dans la base de données", ephemeral=True)
                    return

                embed = discord.Embed(
                    title=f"📋 Braquages Cayo Perico ({len(rows)} trouvé(s))",
                    color=discord.Color.gold()
                )

                for row in rows[:10]:  # Limiter à 10 pour éviter les embeds trop longs
                    heist_id = row[0]
                    status = row[1]
                    primary = row[2]
                    hard_mode = row[3]
                    leader_id = row[4]
                    created = row[5]
                    num_part = row[6]

                    status_emoji = {
                        "pending": "⏳",
                        "ready": "✅",
                        "finished": "🏁"
                    }.get(status, "❓")

                    embed.add_field(
                        name=f"{status_emoji} Heist #{heist_id} - {status}",
                        value=(
                            f"• Organisateur: <@{leader_id}>\n"
                            f"• Objectif: {primary}\n"
                            f"• Hard mode: {'✅' if hard_mode else '❌'}\n"
                            f"• Participants: {num_part}\n"
                            f"• Créé: {created.strftime('%Y-%m-%d %H:%M')}"
                        ),
                        inline=False
                    )

                if len(rows) > 10:
                    embed.set_footer(text=f"... et {len(rows) - 10} autre(s) braquage(s)")

                await interaction.followup.send(embed=embed, ephemeral=True)

            # ---- NETTOYER LES BRAQUAGES ----
            elif action == "clean_heists":
                # Demander confirmation
                query_count = "SELECT COUNT(*) FROM cayo_heists;"
                row = await self.db.fetchrow(query_count)
                count = row[0] if row else 0

                if count == 0:
                    await interaction.followup.send("✅ Aucun braquage à nettoyer", ephemeral=True)
                    return

                # Supprimer tous les braquages (CASCADE supprime aussi les participants)
                query_delete = "DELETE FROM cayo_heists;"
                await self.db.execute(query_delete)

                embed = discord.Embed(
                    title="🗑️ Nettoyage effectué",
                    description=f"✅ {count} braquage(s) supprimé(s) (+ participants associés)",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.info(f"[DB] {count} braquages nettoyés par {interaction.user}")

            # ---- NETTOYER TOUTES LES DONNÉES CAYO ----
            elif action == "clean_all":
                # Compter avant
                tables_queries = {
                    "cayo_heists": "SELECT COUNT(*) FROM cayo_heists;",
                    "cayo_participants": "SELECT COUNT(*) FROM cayo_participants;",
                    "cayo_results": "SELECT COUNT(*) FROM cayo_results;",
                    "users": "SELECT COUNT(*) FROM users;"
                }

                counts_before = {}
                for table, query in tables_queries.items():
                    try:
                        row = await self.db.fetchrow(query)
                        counts_before[table] = row[0] if row else 0
                    except:
                        counts_before[table] = 0

                # Supprimer TOUT
                await self.db.execute("DELETE FROM cayo_results;")
                await self.db.execute("DELETE FROM cayo_heists;")  # CASCADE sur participants
                await self.db.execute("DELETE FROM users;")  # ATTENTION : supprime TOUS les users

                embed = discord.Embed(
                    title="🧹 Nettoyage complet effectué",
                    description="⚠️ **TOUTES les données Cayo Perico ont été supprimées**",
                    color=discord.Color.red()
                )

                embed.add_field(
                    name="📊 Lignes supprimées",
                    value=(
                        f"• `users`: {counts_before['users']}\n"
                        f"• `cayo_heists`: {counts_before['cayo_heists']}\n"
                        f"• `cayo_participants`: {counts_before['cayo_participants']}\n"
                        f"• `cayo_results`: {counts_before['cayo_results']}"
                    ),
                    inline=False
                )

                await interaction.followup.send(embed=embed, ephemeral=True)
                logger.warning(f"[DB] Nettoyage complet Cayo Perico par {interaction.user}")

        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur",
                description=f"```\n{str(e)}\n```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.error(f"[DB] Erreur db-check: {e}")


async def setup(bot: commands.Bot):
    """Charge le cog."""
    await bot.add_cog(DBAdmin(bot))
    logger.info("Cog DBAdmin chargé")
