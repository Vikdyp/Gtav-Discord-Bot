-- Migration 002: Ajout de colonnes pour les nouvelles fonctionnalités Cayo Perico V2
-- Date: 2025-12-10
-- Ajoute les colonnes pour :
--   - Défi Elite (elite_challenge_completed)
--   - Parts personnalisées (custom_shares)
--   - Horodatage de fin pour cooldown (finished_at)

-- ==================== AJOUT DES COLONNES ====================

ALTER TABLE cayo_heists
ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS custom_shares JSONB,
ADD COLUMN IF NOT EXISTS elite_challenge_completed BOOLEAN DEFAULT FALSE;

-- ==================== INDEX ====================

-- Index pour rechercher les braquages terminés récemment
CREATE INDEX IF NOT EXISTS idx_cayo_heists_finished
ON cayo_heists (finished_at DESC) WHERE finished_at IS NOT NULL;

-- Index pour filtrer les braquages avec parts personnalisées
CREATE INDEX IF NOT EXISTS idx_cayo_heists_custom_shares
ON cayo_heists USING GIN (custom_shares) WHERE custom_shares IS NOT NULL;

-- ==================== COMMENTAIRES ====================

COMMENT ON COLUMN cayo_heists.finished_at IS 'Horodatage de fin du braquage (pour calculer les cooldowns)';
COMMENT ON COLUMN cayo_heists.custom_shares IS 'Parts personnalisées {"discord_id": pourcentage} ou NULL pour parts par défaut';
COMMENT ON COLUMN cayo_heists.elite_challenge_completed IS 'True si le défi Elite a été validé (+50k ou +100k par joueur)';
