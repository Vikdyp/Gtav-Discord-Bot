-- Migration 003: Ajout de la colonne ready_at pour calculer les temps de préparation et mission
-- Date: 2025-12-10
-- Ajoute la colonne ready_at pour :
--   - Calculer le temps de préparation (ready_at - created_at)
--   - Calculer le temps de mission (finished_at - ready_at)

-- ==================== AJOUT DE LA COLONNE ====================

ALTER TABLE cayo_heists
ADD COLUMN IF NOT EXISTS ready_at TIMESTAMPTZ;

-- ==================== INDEX ====================

-- Index pour rechercher les braquages marqués prêts récemment
CREATE INDEX IF NOT EXISTS idx_cayo_heists_ready
ON cayo_heists (ready_at DESC) WHERE ready_at IS NOT NULL;

-- ==================== COMMENTAIRES ====================

COMMENT ON COLUMN cayo_heists.ready_at IS 'Horodatage quand le braquage a été marqué prêt (pour calculer temps de préparation et mission)';
