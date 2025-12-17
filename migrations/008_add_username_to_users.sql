-- ============================================
-- MIGRATION 008: AJOUT DU USERNAME DISCORD
-- ============================================
-- Date: 2025-12-16
-- Description: Ajoute une colonne username à la table users
--              pour afficher les pseudos Discord au lieu des IDs
-- ============================================

-- Ajouter la colonne username
ALTER TABLE users
ADD COLUMN IF NOT EXISTS username TEXT;

-- Ajouter la colonne display_name (nom d'affichage avec discriminator si présent)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS display_name TEXT;

-- Index pour recherche par username
CREATE INDEX IF NOT EXISTS idx_users_username
    ON users (username);

-- Commentaires
COMMENT ON COLUMN users.username IS 'Nom d''utilisateur Discord (sans discriminator)';
COMMENT ON COLUMN users.display_name IS 'Nom d''affichage Discord complet';

-- Note: Les valeurs seront mises à jour automatiquement par le bot
-- lors des prochaines interactions des utilisateurs
SELECT 'Migration 008: Colonnes username et display_name ajoutées à la table users' as status;
