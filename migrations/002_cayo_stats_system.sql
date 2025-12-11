-- Migration 002: Système de stats et leaderboards Cayo Perico
-- Auteur: Claude Code
-- Date: 2025-12-11
-- Description: Ajoute les tables pour leaderboards auto-update, notifications et stats étendues

-- ============================================
-- Table: Messages de leaderboard
-- ============================================
-- Stocker les messages de leaderboard pour auto-update
CREATE TABLE IF NOT EXISTS cayo_leaderboard_messages (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    forum_channel_id BIGINT NOT NULL,
    thread_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    leaderboard_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(guild_id, leaderboard_type)
);

-- Index pour recherche rapide par guild
CREATE INDEX IF NOT EXISTS idx_leaderboard_messages_guild
ON cayo_leaderboard_messages(guild_id);

-- ============================================
-- Table: Préférences de notification utilisateur
-- ============================================
-- Stocker les préférences de notification par utilisateur
CREATE TABLE IF NOT EXISTS cayo_user_notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    guild_id BIGINT NOT NULL,
    notify_cooldown BOOLEAN DEFAULT true,
    notify_hardmode BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, guild_id)
);

-- Index pour recherche rapide
CREATE INDEX IF NOT EXISTS idx_user_notifications_user_guild
ON cayo_user_notifications(user_id, guild_id);

-- ============================================
-- Table: Cooldowns actifs pour notifications
-- ============================================
-- Stocker les cooldowns actifs pour notifications
CREATE TABLE IF NOT EXISTS cayo_active_cooldowns (
    id SERIAL PRIMARY KEY,
    heist_id INTEGER REFERENCES cayo_heists(id) ON DELETE CASCADE,
    leader_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    guild_id BIGINT NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    num_players INTEGER NOT NULL,
    notified_cooldown BOOLEAN DEFAULT false,
    notified_hardmode BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(heist_id)
);

-- Index pour recherche des cooldowns expirés à notifier
CREATE INDEX IF NOT EXISTS idx_active_cooldowns_finished
ON cayo_active_cooldowns(finished_at)
WHERE notified_cooldown = false OR notified_hardmode = false;

-- Index pour recherche par guild
CREATE INDEX IF NOT EXISTS idx_active_cooldowns_guild
ON cayo_active_cooldowns(guild_id);

-- ============================================
-- Extension table cayo_heists
-- ============================================
-- Ajouter colonne pour stocker le temps de mission en secondes
ALTER TABLE cayo_heists
ADD COLUMN IF NOT EXISTS mission_time_seconds INTEGER DEFAULT 0;

-- ============================================
-- Extension vue matérialisée cayo_user_stats
-- ============================================
-- Drop et recréer la vue avec colonnes supplémentaires

-- Drop triggers d'abord
DROP TRIGGER IF EXISTS trigger_refresh_cayo_stats_heists ON cayo_heists;
DROP TRIGGER IF EXISTS trigger_refresh_cayo_stats ON cayo_results;

-- Drop la fonction de refresh
DROP FUNCTION IF EXISTS refresh_cayo_user_stats();

-- Drop la vue
DROP MATERIALIZED VIEW IF EXISTS cayo_user_stats CASCADE;

-- Recréer la vue avec colonnes supplémentaires
CREATE MATERIALIZED VIEW cayo_user_stats AS
SELECT
    u.id as user_id,
    u.discord_id,
    COUNT(DISTINCT r.heist_id) as total_heists,
    COALESCE(AVG(r.real_gain), 0) as avg_gain,
    COALESCE(AVG(r.accuracy_percent), 0) as avg_accuracy,
    COALESCE(SUM(r.real_gain), 0) as total_earned,
    COALESCE(MAX(r.real_gain), 0) as best_gain,
    MIN(r.created_at) as first_heist,
    MAX(r.created_at) as last_heist,
    -- Nouveau: Compter les Elite Challenge réussis
    COUNT(DISTINCT CASE WHEN h.elite_challenge_completed THEN r.heist_id END) as elite_count,
    -- Nouveau: Temps de mission le plus rapide (en secondes)
    -- Note: mission_time_seconds = 0 signifie pas de données
    COALESCE(
        MIN(CASE WHEN h.mission_time_seconds > 0 THEN h.mission_time_seconds END),
        0
    ) as best_mission_time_seconds
FROM users u
LEFT JOIN cayo_results r ON u.id = r.user_id
LEFT JOIN cayo_heists h ON r.heist_id = h.id
GROUP BY u.id, u.discord_id;

-- Recréer les index
CREATE UNIQUE INDEX idx_cayo_user_stats_user_id ON cayo_user_stats(user_id);
CREATE INDEX idx_cayo_user_stats_discord_id ON cayo_user_stats(discord_id);
CREATE INDEX idx_cayo_user_stats_total_earned ON cayo_user_stats(total_earned DESC);
CREATE INDEX idx_cayo_user_stats_total_heists ON cayo_user_stats(total_heists DESC);
CREATE INDEX idx_cayo_user_stats_avg_gain ON cayo_user_stats(avg_gain DESC);
CREATE INDEX idx_cayo_user_stats_elite_count ON cayo_user_stats(elite_count DESC);

-- Recréer la fonction de refresh
CREATE OR REPLACE FUNCTION refresh_cayo_user_stats()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY cayo_user_stats;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Recréer les triggers
-- Trigger sur cayo_results (pour gains, accuracy)
CREATE TRIGGER trigger_refresh_cayo_stats
AFTER INSERT OR UPDATE OR DELETE ON cayo_results
FOR EACH STATEMENT
EXECUTE FUNCTION refresh_cayo_user_stats();

-- Trigger sur cayo_heists (pour elite_challenge et mission_time)
CREATE TRIGGER trigger_refresh_cayo_stats_heists
AFTER UPDATE ON cayo_heists
FOR EACH STATEMENT
EXECUTE FUNCTION refresh_cayo_user_stats();

-- ============================================
-- Commentaires pour documentation
-- ============================================

COMMENT ON TABLE cayo_leaderboard_messages IS
'Stocke les références aux messages de leaderboard dans les forums Discord pour mise à jour automatique';

COMMENT ON TABLE cayo_user_notifications IS
'Préférences de notification par utilisateur et par serveur';

COMMENT ON TABLE cayo_active_cooldowns IS
'Cooldowns actifs pour envoyer des notifications de disponibilité de braquage';

COMMENT ON COLUMN cayo_heists.mission_time_seconds IS
'Durée de la mission en secondes (0 = pas de données)';

COMMENT ON COLUMN cayo_user_stats.elite_count IS
'Nombre de braquages avec Défi Elite validé';

COMMENT ON COLUMN cayo_user_stats.best_mission_time_seconds IS
'Temps de mission le plus rapide en secondes (0 = pas de données)';

-- ============================================
-- Initialisation: Refresh de la vue
-- ============================================

-- Refresh initial de la vue matérialisée
REFRESH MATERIALIZED VIEW CONCURRENTLY cayo_user_stats;
