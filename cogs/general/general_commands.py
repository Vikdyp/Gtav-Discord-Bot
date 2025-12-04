# cogs/general/general_commands.py
"""
Commandes générales et utilitaires du bot.
"""

import discord
import psycopg
from discord import app_commands
from discord.ext import commands

from utils.logging_config import logger


class GeneralCommands(commands.Cog):
    """Cog contenant les commandes générales du bot"""

    def __init__(self, bot: commands.Bot):
        """
        Initialise le cog.

        Args:
            bot: Instance du bot
        """
        self.bot = bot
        self.logger = logger

        # ⚙️ Config DB (adapter si tu changes les identifiants)
        host = "postgresql"
        user = "postgres"
        password = "postgres1234"
        dbname = "lesterdb"

        self.db_conn_string = (
            f"postgresql://{user}:{password}@{host}:5432/{dbname}"
        )

    # -------------------- UTILITAIRE INTERNE DB --------------------

    def _ensure_table(self):
        """
        Crée la table de test si elle n'existe pas.
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS test_entries (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        with psycopg.connect(self.db_conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(create_table_sql)
            conn.commit()

    # -------------------- COMMANDES --------------------

    @app_commands.command(
        name="ping",
        description="Vérifie la latence du bot"
    )
    async def ping(self, interaction: discord.Interaction):
        """
        Commande /ping - Affiche la latence du bot.
        """
        latency_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latence: **{latency_ms}ms**",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

        self.logger.info(
            f"Commande /ping utilisée par {interaction.user} "
            f"(latence: {latency_ms}ms)"
        )

    @app_commands.command(
        name="dbtest",
        description="Teste la connexion à la base PostgreSQL"
    )
    async def dbtest(self, interaction: discord.Interaction):
        """
        Test simple: SELECT 1
        """
        self.logger.info(
            f"Tentative de connexion PostgreSQL avec : {self.db_conn_string}"
        )

        try:
            with psycopg.connect(self.db_conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    result = cur.fetchone()

            embed = discord.Embed(
                title="📡 Connexion PostgreSQL",
                description=f"Connexion réussie : **{result[0]}**",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            self.logger.info("Connexion PostgreSQL OK")

        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur PostgreSQL",
                description=f"```\n{e}\n```",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            self.logger.error(f"Erreur PostgreSQL : {e}")

    # -------------------- TEST ÉCRITURE --------------------

    @app_commands.command(
        name="dbsave",
        description="Enregistre un message de test dans la base"
    )
    @app_commands.describe(message="Le message à enregistrer")
    async def dbsave(self, interaction: discord.Interaction, message: str):
        """
        Insère une ligne dans test_entries.
        """
        await interaction.response.defer(thinking=True)

        try:
            # S'assure que la table existe
            self._ensure_table()

            user = interaction.user
            insert_sql = """
            INSERT INTO test_entries (user_id, username, content)
            VALUES (%s, %s, %s)
            RETURNING id, created_at;
            """

            with psycopg.connect(self.db_conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        insert_sql,
                        (user.id, str(user), message)
                    )
                    row = cur.fetchone()
                conn.commit()

            entry_id, created_at = row

            embed = discord.Embed(
                title="✅ Donnée enregistrée",
                description=(
                    f"ID: **{entry_id}**\n"
                    f"Utilisateur: **{user}**\n"
                    f"Message: `{message}`\n"
                    f"Date: `{created_at}`"
                ),
                color=discord.Color.green()
            )

            await interaction.followup.send(embed=embed)
            self.logger.info(
                f"Entrée DB ajoutée id={entry_id} user={user} content={message}"
            )

        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur lors de l'insertion",
                description=f"```\n{e}\n```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            self.logger.error(f"Erreur insertion PostgreSQL : {e}")

    # -------------------- TEST LECTURE --------------------

    @app_commands.command(
        name="dbshow",
        description="Affiche les 5 dernières entrées enregistrées"
    )
    async def dbshow(self, interaction: discord.Interaction):
        """
        Lit les dernières lignes de test_entries.
        """
        await interaction.response.defer(thinking=True)

        try:
            self._ensure_table()

            select_sql = """
            SELECT id, username, content, created_at
            FROM test_entries
            ORDER BY created_at DESC
            LIMIT 5;
            """

            with psycopg.connect(self.db_conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute(select_sql)
                    rows = cur.fetchall()

            if not rows:
                description = "Aucune entrée trouvée dans `test_entries`."
            else:
                lines = []
                for r in rows:
                    _id, username, content, created_at = r
                    lines.append(
                        f"**#{_id}** - {username} - `{content}` "
                        f"(_{created_at}_)"
                    )
                description = "\n".join(lines)

            embed = discord.Embed(
                title="📄 Dernières entrées test_entries",
                description=description,
                color=discord.Color.blurple()
            )

            await interaction.followup.send(embed=embed)
            self.logger.info("Lecture des dernières entrées test_entries")

        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur lors de la lecture",
                description=f"```\n{e}\n```",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            self.logger.error(f"Erreur lecture PostgreSQL : {e}")


async def setup(bot: commands.Bot):
    """
    Fonction appelée par discord.py pour charger le cog.
    """
    await bot.add_cog(GeneralCommands(bot))
    logger.info("Cog GeneralCommands chargé")
