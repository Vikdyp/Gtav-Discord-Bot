-- Migration 006: Ajouter avg_safe_amount à la vue matérialisée cayo_user_stats
-- Cette migration ajoute le calcul de la moyenne du coffre-fort pour chaque joueur
-- (uniquement pour les braquages où le joueur est leader)
--
-- STRATÉGIE PROPRE :
-- 1. Drop de la vue existante (pas de perte de données, juste du cache)
-- 2. Recréation avec le nouveau champ avg_safe_amount
-- 3. Les données sources (users, cayo_heists, cayo_results) restent intactes
-- 4. La vue est automatiquement peuplée lors du CREATE MATERIALIZED VIEW

-- Drop la vue matérialisée existante
DROP MATERIALIZED VIEW IF EXISTS cayo_user_stats;

-- Recréer la vue avec le nouveau champ
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
    COUNT(DISTINCT CASE WHEN h.elite_challenge_completed THEN r.heist_id END) as elite_count,
    COALESCE(
        MIN(CASE WHEN h.mission_time_seconds > 0 THEN h.mission_time_seconds END),
        0
    ) as best_mission_time_seconds,
    -- NOUVEAU : Moyenne du coffre-fort (uniquement braquages en tant que leader)
    COALESCE(
        AVG(CASE WHEN h.leader_user_id = u.id THEN h.safe_amount END),
        0
    ) as avg_safe_amount
FROM users u
LEFT JOIN cayo_results r ON u.id = r.user_id
LEFT JOIN cayo_heists h ON r.heist_id = h.id
GROUP BY u.id, u.discord_id;

-- Recréer les index pour la performance (en cohérence avec migration 005)
CREATE UNIQUE INDEX idx_cayo_user_stats_user_id ON cayo_user_stats(user_id);
CREATE INDEX idx_cayo_user_stats_discord_id ON cayo_user_stats(discord_id);
CREATE INDEX idx_cayo_user_stats_total_earned ON cayo_user_stats(total_earned DESC);
CREATE INDEX idx_cayo_user_stats_total_heists ON cayo_user_stats(total_heists DESC);
