# utils/migrator.py
"""
Gestionnaire de migrations SQL pour la base de données.
"""

from pathlib import Path
from typing import Optional, List
from utils.database import Database
from utils.logging_config import logger


class Migrator:
    """Gestionnaire de migrations SQL."""

    def __init__(self, db: Database):
        self.db = db

    async def _table_exists(self, table_name: str) -> bool:
        """Vérifie si une table existe."""
        query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        );
        """
        row = await self.db.fetchrow(query, table_name)
        return row[0] if row else False

    async def _column_exists(self, table_name: str, column_name: str) -> bool:
        """Vérifie si une colonne existe dans une table."""
        query = """
        SELECT EXISTS (
            SELECT FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = %s
            AND column_name = %s
        );
        """
        row = await self.db.fetchrow(query, table_name, column_name)
        return row[0] if row else False

    async def check_cayo_v2_migration(self) -> bool:
        """
        Vérifie si la migration Cayo Perico V2 a déjà été appliquée.

        Returns:
            True si la migration est déjà appliquée, False sinon
        """
        # Vérifier si les nouvelles colonnes existent
        hard_mode_exists = await self._column_exists("cayo_heists", "hard_mode")
        safe_amount_exists = await self._column_exists("cayo_heists", "safe_amount")
        optimized_plan_exists = await self._column_exists("cayo_heists", "optimized_plan")

        # Vérifier si la nouvelle table existe
        results_table_exists = await self._table_exists("cayo_results")

        # La migration est complète si tout existe
        return (
            hard_mode_exists
            and safe_amount_exists
            and optimized_plan_exists
            and results_table_exists
        )

    async def apply_cayo_v2_migration(self) -> tuple[bool, str]:
        """
        Applique la migration Cayo Perico V2.

        Returns:
            Tuple (success, message)
        """
        try:
            # Vérifier si déjà appliquée
            if await self.check_cayo_v2_migration():
                return True, "✅ Migration déjà appliquée (rien à faire)"

            # Lire le fichier de migration
            migration_file = Path("migrations/001_cayo_perico_v2.sql")
            if not migration_file.exists():
                return False, f"❌ Fichier de migration introuvable : {migration_file}"

            with open(migration_file, "r", encoding="utf-8") as f:
                sql = f.read()

            # Exécuter la migration
            await self.db.execute(sql)

            logger.info("[Migrator] Migration Cayo Perico V2 appliquée avec succès")
            return True, "✅ Migration Cayo Perico V2 appliquée avec succès !"

        except Exception as e:
            logger.error(f"[Migrator] Erreur lors de la migration : {e}")
            return False, f"❌ Erreur lors de la migration : {str(e)}"

    async def check_cayo_v2_additions(self) -> bool:
        """
        Vérifie si la migration Cayo Perico V2 Additions (002) a déjà été appliquée.

        Returns:
            True si la migration est déjà appliquée, False sinon
        """
        # Vérifier si les nouvelles colonnes existent
        finished_at_exists = await self._column_exists("cayo_heists", "finished_at")
        custom_shares_exists = await self._column_exists("cayo_heists", "custom_shares")
        elite_exists = await self._column_exists("cayo_heists", "elite_challenge_completed")

        # La migration est complète si tout existe
        return finished_at_exists and custom_shares_exists and elite_exists

    async def apply_cayo_v2_additions(self) -> tuple[bool, str]:
        """
        Applique la migration Cayo Perico V2 Additions (002).

        Returns:
            Tuple (success, message)
        """
        try:
            # Vérifier si déjà appliquée
            if await self.check_cayo_v2_additions():
                return True, "✅ Migration déjà appliquée (rien à faire)"

            # Vérifier que la migration 001 est appliquée
            if not await self.check_cayo_v2_migration():
                return False, "❌ La migration 001 (Cayo Perico V2) doit être appliquée en premier"

            # Lire le fichier de migration
            migration_file = Path("migrations/002_cayo_perico_additions.sql")
            if not migration_file.exists():
                return False, f"❌ Fichier de migration introuvable : {migration_file}"

            with open(migration_file, "r", encoding="utf-8") as f:
                sql = f.read()

            # Exécuter la migration
            await self.db.execute(sql)

            logger.info("[Migrator] Migration Cayo Perico V2 Additions appliquée avec succès")
            return True, "✅ Migration Cayo Perico V2 Additions appliquée avec succès !"

        except Exception as e:
            logger.error(f"[Migrator] Erreur lors de la migration : {e}")
            return False, f"❌ Erreur lors de la migration : {str(e)}"

    async def check_ready_at_column(self) -> bool:
        """
        Vérifie si la migration 003 (colonne ready_at) a été appliquée.

        Returns:
            True si la migration est appliquée, False sinon
        """
        return await self._column_exists("cayo_heists", "ready_at")

    async def apply_ready_at_migration(self) -> tuple[bool, str]:
        """
        Applique la migration 003 (ajout de ready_at).

        Returns:
            Tuple (success, message)
        """
        try:
            if await self.check_ready_at_column():
                return True, "✅ Migration déjà appliquée (rien à faire)"

            # Lire le fichier
            migration_file = Path("migrations/003_add_ready_at.sql")
            if not migration_file.exists():
                return False, f"❌ Fichier de migration introuvable : {migration_file}"

            with open(migration_file, "r", encoding="utf-8") as f:
                sql = f.read()

            # Exécuter
            await self.db.execute(sql)

            logger.info("[Migrator] Migration 003 (ready_at) appliquée avec succès")
            return True, "✅ Migration 003 (ready_at) appliquée avec succès !"

        except Exception as e:
            logger.error(f"[Migrator] Erreur lors de la migration 003 : {e}")
            return False, f"❌ Erreur lors de la migration : {str(e)}"

    async def check_office_paintings_column(self) -> bool:
        """
        Vérifie si la migration 004 (colonne office_paintings) a été appliquée.

        Returns:
            True si la migration est appliquée, False sinon
        """
        return await self._column_exists("cayo_heists", "office_paintings")

    async def apply_office_paintings_migration(self) -> tuple[bool, str]:
        """
        Applique la migration 004 (ajout de office_paintings).

        Returns:
            Tuple (success, message)
        """
        try:
            if await self.check_office_paintings_column():
                return True, "✅ Migration déjà appliquée (rien à faire)"

            # Lire le fichier
            migration_file = Path("migrations/004_add_office_paintings.sql")
            if not migration_file.exists():
                return False, f"❌ Fichier de migration introuvable : {migration_file}"

            with open(migration_file, "r", encoding="utf-8") as f:
                sql = f.read()

            # Exécuter
            await self.db.execute(sql)

            logger.info("[Migrator] Migration 004 (office_paintings) appliquée avec succès")
            return True, "✅ Migration 004 (office_paintings) appliquée avec succès !"

        except Exception as e:
            logger.error(f"[Migrator] Erreur lors de la migration 004 : {e}")
            return False, f"❌ Erreur lors de la migration : {str(e)}"

    async def get_migration_status(self) -> str:
        """
        Récupère le statut de toutes les migrations.

        Returns:
            Message formaté avec le statut
        """
        lines = ["📋 **Statut des migrations**\n"]

        # Cayo Perico V2
        cayo_v2_applied = await self.check_cayo_v2_migration()
        status = "✅ Appliquée" if cayo_v2_applied else "⏳ En attente"
        lines.append(f"• **Cayo Perico V2** (001): {status}")

        # Cayo Perico V2 Additions
        cayo_v2_add_applied = await self.check_cayo_v2_additions()
        status_add = "✅ Appliquée" if cayo_v2_add_applied else "⏳ En attente"
        lines.append(f"• **Cayo Perico V2 Additions** (002): {status_add}")

        # Ready At Column
        ready_at_applied = await self.check_ready_at_column()
        status_ready = "✅ Appliquée" if ready_at_applied else "⏳ En attente"
        lines.append(f"• **Ready At Column** (003): {status_ready}")

        # Office Paintings Column
        office_paintings_applied = await self.check_office_paintings_column()
        status_office = "✅ Appliquée" if office_paintings_applied else "⏳ En attente"
        lines.append(f"• **Office Paintings Column** (004): {status_office}")

        # Vérifier les tables de base
        users_exists = await self._table_exists("users")
        heists_exists = await self._table_exists("cayo_heists")
        participants_exists = await self._table_exists("cayo_participants")

        lines.append("\n📊 **Tables de base**")
        lines.append(f"• `users`: {'✅' if users_exists else '❌'}")
        lines.append(f"• `cayo_heists`: {'✅' if heists_exists else '❌'}")
        lines.append(f"• `cayo_participants`: {'✅' if participants_exists else '❌'}")

        if cayo_v2_applied:
            results_exists = await self._table_exists("cayo_results")
            lines.append(f"• `cayo_results`: {'✅' if results_exists else '❌'}")

        # Stats and Notifications (005)
        stats_applied = await self.check_stats_and_notifications()
        status_stats = "✅ Appliquée" if stats_applied else "⏳ En attente"
        lines.append(f"• **Stats & Notifications** (005): {status_stats}")

        # Migration 006 : Moyenne du coffre-fort
        avg_safe_applied = await self.check_avg_safe_amount()
        status_avg_safe = "✅ Appliquée" if avg_safe_applied else "⏳ En attente"
        lines.append(f"• **Moyenne Coffre-fort** (006): {status_avg_safe}")

        return "\n".join(lines)

    async def check_stats_and_notifications(self) -> bool:
        """
        Vérifie si la migration 005 (stats et notifications) a été appliquée.

        Returns:
            True si la migration est appliquée, False sinon
        """
        # Vérifier les nouvelles tables
        leaderboards_exists = await self._table_exists("cayo_leaderboard_messages")
        notifications_exists = await self._table_exists("cayo_user_notifications")
        cooldowns_exists = await self._table_exists("cayo_active_cooldowns")

        # Vérifier la colonne mission_time_seconds
        mission_time_exists = await self._column_exists("cayo_heists", "mission_time_seconds")

        return (
            leaderboards_exists
            and notifications_exists
            and cooldowns_exists
            and mission_time_exists
        )

    async def apply_stats_and_notifications(self) -> tuple[bool, str]:
        """
        Applique la migration 005 (stats et notifications).

        Returns:
            Tuple (success, message)
        """
        try:
            if await self.check_stats_and_notifications():
                return True, "✅ Migration déjà appliquée (rien à faire)"

            # Lire le fichier
            migration_file = Path("migrations/005_cayo_stats_and_notifications.sql")
            if not migration_file.exists():
                return False, f"❌ Fichier de migration introuvable : {migration_file}"

            with open(migration_file, "r", encoding="utf-8") as f:
                sql = f.read()

            # Exécuter
            await self.db.execute(sql)

            logger.info("[Migrator] Migration 005 (stats et notifications) appliquée avec succès")
            return True, "✅ Migration 005 (Stats & Notifications) appliquée avec succès !"

        except Exception as e:
            logger.error(f"[Migrator] Erreur lors de la migration 005 : {e}")
            return False, f"❌ Erreur lors de la migration : {str(e)}"

    async def check_avg_safe_amount(self) -> bool:
        """
        Vérifie si la migration 006 (avg_safe_amount) a été appliquée.

        Returns:
            True si la migration est appliquée, False sinon
        """
        # Vérifier si la colonne avg_safe_amount existe dans la vue matérialisée
        query = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'cayo_user_stats'
              AND column_name = 'avg_safe_amount'
        """
        row = await self.db.fetchrow(query)
        return row is not None

    async def apply_avg_safe_amount(self) -> tuple[bool, str]:
        """
        Applique la migration 006 (avg_safe_amount).

        Cette migration ajoute le champ avg_safe_amount à la vue matérialisée cayo_user_stats.

        Returns:
            Tuple (success, message)
        """
        try:
            if await self.check_avg_safe_amount():
                return True, "✅ Migration déjà appliquée (rien à faire)"

            # Lire le fichier
            migration_file = Path("migrations/006_add_avg_safe_amount.sql")
            if not migration_file.exists():
                return False, f"❌ Fichier de migration introuvable : {migration_file}"

            with open(migration_file, "r", encoding="utf-8") as f:
                sql = f.read()

            # Exécuter
            await self.db.execute(sql)

            logger.info("[Migrator] Migration 006 (avg_safe_amount) appliquée avec succès")
            return True, "✅ Migration 006 (Moyenne Coffre-fort) appliquée avec succès !"

        except Exception as e:
            logger.error(f"[Migrator] Erreur lors de la migration 006 : {e}")
            return False, f"❌ Erreur lors de la migration : {str(e)}"
