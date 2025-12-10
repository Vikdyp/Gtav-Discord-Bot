-- Migration 004: Ajout de la colonne office_paintings pour gérer les tableaux du bureau
-- Date: 2025-12-10
-- Ajoute la colonne office_paintings pour indiquer combien de tableaux sont dans le bureau
-- (ces tableaux peuvent être pris en solo contrairement aux autres emplacements)

-- ==================== AJOUT DE LA COLONNE ====================

ALTER TABLE cayo_heists
ADD COLUMN IF NOT EXISTS office_paintings INTEGER DEFAULT 0 NOT NULL;

-- ==================== COMMENTAIRES ====================

COMMENT ON COLUMN cayo_heists.office_paintings IS 'Nombre de tableaux dans le bureau (0-2, accessibles en solo)';
