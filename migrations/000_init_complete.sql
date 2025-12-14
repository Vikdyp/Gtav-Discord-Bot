-- ============================================
-- MIGRATION COMPLÈTE - LESTER BOT DATABASE
-- ============================================
-- Consolidation de toutes les migrations (001-006)
-- Date: 2025-12-14
-- Description: Création complète du schéma de base de données pour le bot Lester
--              Système de gestion des braquages Cayo Perico avec statistiques,
--              leaderboards et notifications
-- ============================================

-- ============================================
-- TABLE 1: USERS
-- ============================================
-- Mappage Discord ID → ID interne
-- Table de base pour tous les utilisateurs du bot

CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    discord_id  BIGINT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE users IS 'Utilisateurs Discord - Mapping discord_id vers id interne';
COMMENT ON COLUMN users.discord_id IS 'ID Discord unique de l''utilisateur';

-- ============================================
-- TABLE 2: CAYO_HEISTS
-- ============================================
-- Table principale des braquages Cayo Perico
-- Contient toutes les informations d'un braquage

CREATE TABLE IF NOT EXISTS cayo_heists (
    -- Identifiants
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    channel_id      BIGINT NOT NULL,
    message_id      BIGINT NOT NULL,

    -- Relations
    leader_user_id  INTEGER NOT NULL REFERENCES users(id),

    -- Configuration du braquage
    primary_loot    TEXT NOT NULL,                  -- Butin principal (ex: "Tequila", "Pink Diamond")
    secondary_loot  JSONB NOT NULL,                 -- Butin secondaire disponible {type: quantité}
    hard_mode       BOOLEAN DEFAULT FALSE,          -- Mode difficile activé
    safe_amount     INTEGER DEFAULT 60000,          -- Montant du coffre-fort (60k-99k)
    office_paintings INTEGER DEFAULT 0 NOT NULL,    -- Nombre de tableaux au bureau (0-2)

    -- Résultats
    estimated_loot  INTEGER,                        -- Estimation calculée du gain
    final_loot      INTEGER,                        -- Gain réel final
    optimized_plan  JSONB,                          -- Plan d'optimisation {joueur: sac}
    custom_shares   JSONB,                          -- Parts personnalisées {discord_id: %} ou NULL

    -- Statut et Elite
    status          TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'ready', 'finished'
    elite_challenge_completed BOOLEAN DEFAULT FALSE, -- Défi Elite validé (+bonus)

    -- Horodatages
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- Création du braquage
    ready_at        TIMESTAMPTZ,                        -- Marqué prêt à démarrer
    finished_at     TIMESTAMPTZ,                        -- Braquage terminé
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Statistiques de temps
    mission_time_seconds INTEGER DEFAULT 0          -- Durée mission en secondes (0 = pas de données)
);

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_cayo_heists_guild_status
    ON cayo_heists (guild_id, status);

CREATE INDEX IF NOT EXISTS idx_cayo_heists_message
    ON cayo_heists (guild_id, channel_id, message_id);

CREATE INDEX IF NOT EXISTS idx_cayo_heists_finished
    ON cayo_heists (finished_at DESC)
    WHERE finished_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cayo_heists_ready
    ON cayo_heists (ready_at DESC)
    WHERE ready_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cayo_heists_custom_shares
    ON cayo_heists USING GIN (custom_shares)
    WHERE custom_shares IS NOT NULL;

-- Commentaires
COMMENT ON TABLE cayo_heists IS 'Braquages Cayo Perico - Configuration et résultats';
COMMENT ON COLUMN cayo_heists.status IS 'Statut: pending (en préparation), ready (prêt), finished (terminé)';
COMMENT ON COLUMN cayo_heists.hard_mode IS 'Mode difficile activé (cooldown 48min au lieu de 144min)';
COMMENT ON COLUMN cayo_heists.safe_amount IS 'Montant du coffre-fort (60000-99000)';
COMMENT ON COLUMN cayo_heists.office_paintings IS 'Tableaux au bureau (0-2, accessibles solo)';
COMMENT ON COLUMN cayo_heists.custom_shares IS 'Parts personnalisées ou NULL pour parts par défaut';
COMMENT ON COLUMN cayo_heists.elite_challenge_completed IS 'Défi Elite validé (+50k ou +100k/joueur)';
COMMENT ON COLUMN cayo_heists.created_at IS 'Date de création du braquage';
COMMENT ON COLUMN cayo_heists.ready_at IS 'Date où le braquage a été marqué prêt';
COMMENT ON COLUMN cayo_heists.finished_at IS 'Date de fin du braquage (pour calcul cooldowns)';
COMMENT ON COLUMN cayo_heists.mission_time_seconds IS 'Durée de la mission en secondes (0 = pas de données)';

-- ============================================
-- TABLE 3: CAYO_PARTICIPANTS
-- ============================================
-- Participants aux braquages

CREATE TABLE IF NOT EXISTS cayo_participants (
    id          SERIAL PRIMARY KEY,
    heist_id    INTEGER NOT NULL REFERENCES cayo_heists(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    role        TEXT,                               -- Rôle dans le braquage (optionnel)
    bag_plan    JSONB,                              -- Plan de sac assigné
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (heist_id, user_id)                      -- Un joueur ne peut rejoindre qu'une fois
);

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_cayo_participants_heist
    ON cayo_participants (heist_id);

CREATE INDEX IF NOT EXISTS idx_cayo_participants_user
    ON cayo_participants (user_id);

COMMENT ON TABLE cayo_participants IS 'Participants aux braquages Cayo Perico';
COMMENT ON COLUMN cayo_participants.bag_plan IS 'Plan de sac assigné au joueur {type: quantité}';

-- ============================================
-- TABLE 4: CAYO_RESULTS
-- ============================================
-- Résultats des braquages (pour statistiques)

CREATE TABLE IF NOT EXISTS cayo_results (
    id                  SERIAL PRIMARY KEY,
    heist_id            INTEGER NOT NULL REFERENCES cayo_heists(id) ON DELETE CASCADE,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    predicted_gain      INTEGER NOT NULL,           -- Gain prédit par le calculateur
    real_gain           INTEGER NOT NULL,           -- Gain réel obtenu
    -- Colonnes calculées automatiquement
    difference          INTEGER GENERATED ALWAYS AS (real_gain - predicted_gain) STORED,
    accuracy_percent    FLOAT GENERATED ALWAYS AS (
        CASE
            WHEN predicted_gain > 0 THEN (real_gain::float / predicted_gain * 100)
            ELSE 0
        END
    ) STORED,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_cayo_results_user
    ON cayo_results (user_id);

CREATE INDEX IF NOT EXISTS idx_cayo_results_heist
    ON cayo_results (heist_id);

CREATE INDEX IF NOT EXISTS idx_cayo_results_created
    ON cayo_results (created_at DESC);

COMMENT ON TABLE cayo_results IS 'Résultats individuels des braquages pour statistiques';
COMMENT ON COLUMN cayo_results.predicted_gain IS 'Gain prédit par le calculateur';
COMMENT ON COLUMN cayo_results.real_gain IS 'Gain réel obtenu par le joueur';
COMMENT ON COLUMN cayo_results.difference IS 'Différence réel - prédit (généré automatiquement)';
COMMENT ON COLUMN cayo_results.accuracy_percent IS 'Précision en % (généré automatiquement)';

-- ============================================
-- TABLE 5: CAYO_LEADERBOARD_MESSAGES
-- ============================================
-- Messages de leaderboard pour auto-update

CREATE TABLE IF NOT EXISTS cayo_leaderboard_messages (
    id                  SERIAL PRIMARY KEY,
    guild_id            BIGINT NOT NULL,
    forum_channel_id    BIGINT NOT NULL,
    thread_id           BIGINT NOT NULL,
    message_id          BIGINT NOT NULL,
    leaderboard_type    VARCHAR(50) NOT NULL,       -- Type de leaderboard (ex: "total_earned", "avg_gain")
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(guild_id, leaderboard_type)              -- Un seul message par type et serveur
);

CREATE INDEX IF NOT EXISTS idx_leaderboard_messages_guild
    ON cayo_leaderboard_messages (guild_id);

COMMENT ON TABLE cayo_leaderboard_messages IS 'Messages de leaderboard dans les forums Discord pour mise à jour automatique';
COMMENT ON COLUMN cayo_leaderboard_messages.leaderboard_type IS 'Type de classement (total_earned, avg_gain, etc.)';

-- ============================================
-- TABLE 6: CAYO_USER_NOTIFICATIONS
-- ============================================
-- Préférences de notification par utilisateur

CREATE TABLE IF NOT EXISTS cayo_user_notifications (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER REFERENCES users(id) ON DELETE CASCADE,
    guild_id            BIGINT NOT NULL,
    notify_cooldown     BOOLEAN DEFAULT true,       -- Notifier fin de cooldown
    notify_hardmode     BOOLEAN DEFAULT true,       -- Notifier disponibilité hard mode
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, guild_id)                       -- Préférences uniques par utilisateur et serveur
);

CREATE INDEX IF NOT EXISTS idx_user_notifications_user_guild
    ON cayo_user_notifications (user_id, guild_id);

COMMENT ON TABLE cayo_user_notifications IS 'Préférences de notification par utilisateur et serveur';
COMMENT ON COLUMN cayo_user_notifications.notify_cooldown IS 'Notifier quand le cooldown est terminé';
COMMENT ON COLUMN cayo_user_notifications.notify_hardmode IS 'Notifier quand le mode difficile est disponible';

-- ============================================
-- TABLE 7: CAYO_ACTIVE_COOLDOWNS
-- ============================================
-- Cooldowns actifs pour notifications

CREATE TABLE IF NOT EXISTS cayo_active_cooldowns (
    id                      SERIAL PRIMARY KEY,
    heist_id                INTEGER REFERENCES cayo_heists(id) ON DELETE CASCADE,
    leader_user_id          INTEGER REFERENCES users(id) ON DELETE CASCADE,
    guild_id                BIGINT NOT NULL,
    finished_at             TIMESTAMPTZ NOT NULL,
    num_players             INTEGER NOT NULL,       -- Nombre de joueurs (détermine cooldown)
    notified_cooldown       BOOLEAN DEFAULT false,  -- Notification cooldown envoyée
    notified_hardmode       BOOLEAN DEFAULT false,  -- Notification hardmode envoyée
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(heist_id)                                -- Un seul cooldown par braquage
);

-- Index pour performance (recherche cooldowns expirés)
CREATE INDEX IF NOT EXISTS idx_active_cooldowns_finished
    ON cayo_active_cooldowns (finished_at)
    WHERE notified_cooldown = false OR notified_hardmode = false;

CREATE INDEX IF NOT EXISTS idx_active_cooldowns_guild
    ON cayo_active_cooldowns (guild_id);

COMMENT ON TABLE cayo_active_cooldowns IS 'Cooldowns actifs pour notifications de disponibilité';
COMMENT ON COLUMN cayo_active_cooldowns.num_players IS 'Nombre de joueurs (1: 144min, 2-4: 48min cooldown)';
COMMENT ON COLUMN cayo_active_cooldowns.notified_cooldown IS 'Notification de cooldown normal envoyée';
COMMENT ON COLUMN cayo_active_cooldowns.notified_hardmode IS 'Notification de hard mode envoyée';

-- ============================================
-- VUE MATÉRIALISÉE: CAYO_USER_STATS
-- ============================================
-- Statistiques agrégées par utilisateur
-- Vue matérialisée pour performance

CREATE MATERIALIZED VIEW IF NOT EXISTS cayo_user_stats AS
SELECT
    u.id as user_id,
    u.discord_id,

    -- Statistiques générales
    COUNT(DISTINCT r.heist_id) as total_heists,
    COALESCE(AVG(r.real_gain), 0) as avg_gain,
    COALESCE(AVG(r.accuracy_percent), 0) as avg_accuracy,
    COALESCE(SUM(r.real_gain), 0) as total_earned,
    COALESCE(MAX(r.real_gain), 0) as best_gain,

    -- Horodatages
    MIN(r.created_at) as first_heist,
    MAX(r.created_at) as last_heist,

    -- Statistiques avancées
    COUNT(DISTINCT CASE WHEN h.elite_challenge_completed THEN r.heist_id END) as elite_count,

    -- Temps de mission le plus rapide (0 = pas de données)
    COALESCE(
        MIN(CASE WHEN h.mission_time_seconds > 0 THEN h.mission_time_seconds END),
        0
    ) as best_mission_time_seconds,

    -- Moyenne du coffre-fort (uniquement braquages en tant que leader)
    COALESCE(
        AVG(CASE WHEN h.leader_user_id = u.id THEN h.safe_amount END),
        0
    ) as avg_safe_amount

FROM users u
LEFT JOIN cayo_results r ON u.id = r.user_id
LEFT JOIN cayo_heists h ON r.heist_id = h.id
GROUP BY u.id, u.discord_id;

-- Index sur la vue matérialisée
CREATE UNIQUE INDEX IF NOT EXISTS idx_cayo_user_stats_user_id
    ON cayo_user_stats (user_id);

CREATE INDEX IF NOT EXISTS idx_cayo_user_stats_discord_id
    ON cayo_user_stats (discord_id);

CREATE INDEX IF NOT EXISTS idx_cayo_user_stats_total_earned
    ON cayo_user_stats (total_earned DESC);

CREATE INDEX IF NOT EXISTS idx_cayo_user_stats_total_heists
    ON cayo_user_stats (total_heists DESC);

CREATE INDEX IF NOT EXISTS idx_cayo_user_stats_avg_gain
    ON cayo_user_stats (avg_gain DESC);

CREATE INDEX IF NOT EXISTS idx_cayo_user_stats_elite_count
    ON cayo_user_stats (elite_count DESC);

COMMENT ON MATERIALIZED VIEW cayo_user_stats IS 'Statistiques agrégées par utilisateur (vue matérialisée pour performance)';
COMMENT ON COLUMN cayo_user_stats.elite_count IS 'Nombre de braquages avec Défi Elite validé';
COMMENT ON COLUMN cayo_user_stats.best_mission_time_seconds IS 'Temps de mission le plus rapide en secondes (0 = pas de données)';
COMMENT ON COLUMN cayo_user_stats.avg_safe_amount IS 'Moyenne du montant du coffre-fort en tant que leader';

-- ============================================
-- FONCTION: REFRESH AUTOMATIQUE DES STATS
-- ============================================
-- Rafraîchit la vue matérialisée après modifications

CREATE OR REPLACE FUNCTION refresh_cayo_user_stats()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY cayo_user_stats;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_cayo_user_stats() IS 'Rafraîchit la vue matérialisée cayo_user_stats en mode concurrent';

-- ============================================
-- TRIGGERS: AUTO-REFRESH DE LA VUE
-- ============================================

-- Trigger sur cayo_results (gains, accuracy)
DROP TRIGGER IF EXISTS trigger_refresh_cayo_stats ON cayo_results;
CREATE TRIGGER trigger_refresh_cayo_stats
AFTER INSERT OR UPDATE OR DELETE ON cayo_results
FOR EACH STATEMENT
EXECUTE FUNCTION refresh_cayo_user_stats();

-- Trigger sur cayo_heists (elite_challenge, mission_time)
DROP TRIGGER IF EXISTS trigger_refresh_cayo_stats_heists ON cayo_heists;
CREATE TRIGGER trigger_refresh_cayo_stats_heists
AFTER UPDATE ON cayo_heists
FOR EACH STATEMENT
EXECUTE FUNCTION refresh_cayo_user_stats();

-- ============================================
-- INITIALISATION
-- ============================================
-- Refresh initial de la vue matérialisée

REFRESH MATERIALIZED VIEW CONCURRENTLY cayo_user_stats;

-- ============================================
-- RÉSUMÉ DE LA STRUCTURE
-- ============================================
-- Tables créées: 7
--   1. users                       - Utilisateurs Discord
--   2. cayo_heists                 - Braquages Cayo Perico
--   3. cayo_participants           - Participants aux braquages
--   4. cayo_results                - Résultats individuels
--   5. cayo_leaderboard_messages   - Messages de leaderboard
--   6. cayo_user_notifications     - Préférences de notification
--   7. cayo_active_cooldowns       - Cooldowns actifs
--
-- Vues matérialisées: 1
--   - cayo_user_stats              - Statistiques agrégées
--
-- Fonctions: 1
--   - refresh_cayo_user_stats()    - Rafraîchissement automatique
--
-- Triggers: 2
--   - trigger_refresh_cayo_stats           (sur cayo_results)
--   - trigger_refresh_cayo_stats_heists    (sur cayo_heists)
--
-- Index: 22 (optimisation des requêtes fréquentes)
-- ============================================
