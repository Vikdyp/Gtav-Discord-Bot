-- Migration pour Cayo Perico V2 - Calculateur optimisé
-- Date: 2025-12-09
-- Crée toutes les tables nécessaires pour le système Cayo Perico

-- ==================== TABLE USERS ====================
-- Table de base pour mapper discord_id -> id interne
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    discord_id  BIGINT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ==================== TABLE CAYO_HEISTS ====================
-- Table principale des braquages Cayo Perico
CREATE TABLE IF NOT EXISTS cayo_heists (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    channel_id      BIGINT NOT NULL,
    message_id      BIGINT NOT NULL,

    leader_user_id  INTEGER NOT NULL REFERENCES users(id),

    primary_loot    TEXT NOT NULL,
    secondary_loot  JSONB NOT NULL,

    estimated_loot  INTEGER,
    final_loot      INTEGER,
    status          TEXT NOT NULL DEFAULT 'pending',

    -- Colonnes V2
    hard_mode       BOOLEAN DEFAULT FALSE,
    safe_amount     INTEGER DEFAULT 60000,
    optimized_plan  JSONB,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ajouter les colonnes V2 si la table existe déjà (migration depuis V1)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'cayo_heists') THEN
        ALTER TABLE cayo_heists
        ADD COLUMN IF NOT EXISTS hard_mode BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS safe_amount INTEGER DEFAULT 60000,
        ADD COLUMN IF NOT EXISTS optimized_plan JSONB;
    END IF;
END$$;

-- Index pour les braquages
CREATE INDEX IF NOT EXISTS idx_cayo_heists_guild_status
ON cayo_heists (guild_id, status);

CREATE INDEX IF NOT EXISTS idx_cayo_heists_message
ON cayo_heists (guild_id, channel_id, message_id);

-- ==================== TABLE CAYO_PARTICIPANTS ====================
-- Table des participants aux braquages
CREATE TABLE IF NOT EXISTS cayo_participants (
    id          SERIAL PRIMARY KEY,
    heist_id    INTEGER NOT NULL REFERENCES cayo_heists(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    role        TEXT,
    bag_plan    JSONB,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (heist_id, user_id)
);

-- Index pour les participants
CREATE INDEX IF NOT EXISTS idx_cayo_participants_heist
ON cayo_participants (heist_id);

CREATE INDEX IF NOT EXISTS idx_cayo_participants_user
ON cayo_participants (user_id);

-- ==================== TABLE CAYO_RESULTS ====================
-- Table des résultats des braquages (pour statistiques)
CREATE TABLE IF NOT EXISTS cayo_results (
    id SERIAL PRIMARY KEY,
    heist_id INTEGER NOT NULL REFERENCES cayo_heists(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id),
    predicted_gain INTEGER NOT NULL,
    real_gain INTEGER NOT NULL,
    difference INTEGER GENERATED ALWAYS AS (real_gain - predicted_gain) STORED,
    accuracy_percent FLOAT GENERATED ALWAYS AS (
        CASE WHEN predicted_gain > 0
        THEN (real_gain::float / predicted_gain * 100)
        ELSE 0 END
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index pour les résultats
CREATE INDEX IF NOT EXISTS idx_cayo_results_user ON cayo_results(user_id);
CREATE INDEX IF NOT EXISTS idx_cayo_results_heist ON cayo_results(heist_id);
CREATE INDEX IF NOT EXISTS idx_cayo_results_created ON cayo_results(created_at DESC);

-- ==================== VUE MATÉRIALISÉE STATISTIQUES ====================
-- Vue matérialisée pour les statistiques utilisateur (optionnel mais performant)
CREATE MATERIALIZED VIEW IF NOT EXISTS cayo_user_stats AS
SELECT
    u.id as user_id,
    u.discord_id,
    COUNT(DISTINCT r.heist_id) as total_heists,
    COALESCE(AVG(r.real_gain), 0) as avg_gain,
    COALESCE(AVG(r.accuracy_percent), 0) as avg_accuracy,
    COALESCE(SUM(r.real_gain), 0) as total_earned,
    MIN(r.created_at) as first_heist,
    MAX(r.created_at) as last_heist
FROM users u
LEFT JOIN cayo_results r ON u.id = r.user_id
GROUP BY u.id, u.discord_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_cayo_user_stats_user ON cayo_user_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_cayo_user_stats_discord ON cayo_user_stats(discord_id);

-- ==================== TRIGGERS ====================
-- Fonction pour rafraîchir la vue matérialisée
CREATE OR REPLACE FUNCTION refresh_cayo_user_stats()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY cayo_user_stats;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour rafraîchir automatiquement les stats
DROP TRIGGER IF EXISTS trigger_refresh_cayo_stats ON cayo_results;
CREATE TRIGGER trigger_refresh_cayo_stats
AFTER INSERT OR UPDATE OR DELETE ON cayo_results
FOR EACH STATEMENT
EXECUTE FUNCTION refresh_cayo_user_stats();
