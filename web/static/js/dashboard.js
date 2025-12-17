// Dashboard JavaScript - Charge et affiche toutes les stats

let activityChart = null;
let gainsChart = null;

// Load dashboard data on page load
document.addEventListener('DOMContentLoaded', async function() {
    console.log('Loading dashboard data...');

    // Load all data
    await Promise.all([
        loadServerStats(),
        loadActivityChart(),
        loadGainsChart(),
        loadTopPlayers(),
        loadRecentHeists()
    ]);

    console.log('Dashboard loaded!');
});

// Load server stats
async function loadServerStats() {
    const data = await apiCall('dashboard');
    if (!data || !data.server_stats) return;

    const stats = data.server_stats;

    // Update stat cards
    document.getElementById('total-heists').textContent = formatNumber(stats.total_heists);
    document.getElementById('total-earned').textContent = formatMoney(stats.total_earned);
    document.getElementById('total-players').textContent = formatNumber(stats.total_players);
    document.getElementById('avg-gain').textContent = formatMoney(stats.avg_gain);
    document.getElementById('elite-completed').textContent = formatNumber(stats.elite_completed);
    document.getElementById('avg-time').textContent = formatTime(stats.avg_mission_time);
}

// Load activity chart
async function loadActivityChart() {
    const data = await apiCall('activity?days=30');
    if (!data || data.length === 0) {
        console.log('No activity data available');
        return;
    }

    // Destroy existing chart if any
    if (activityChart) {
        activityChart.destroy();
    }

    // Create new chart
    activityChart = createActivityChart('activity-chart', data);
}

// Load gains chart
async function loadGainsChart() {
    const data = await apiCall('gains?weeks=12');
    if (!data || data.length === 0) {
        console.log('No gains data available');
        return;
    }

    // Destroy existing chart if any
    if (gainsChart) {
        gainsChart.destroy();
    }

    // Create new chart
    gainsChart = createGainsChart('gains-chart', data);
}

// Load top players
async function loadTopPlayers() {
    const data = await apiCall('dashboard');
    if (!data || !data.leaderboards) return;

    // Top Earned
    const topEarned = data.leaderboards.total_earned.slice(0, 5);
    const topEarnedBody = document.getElementById('top-earned');
    if (topEarnedBody) {
        topEarnedBody.innerHTML = topEarned.map(player => `
            <tr>
                <td>${getRankBadge(player.rank)}</td>
                <td>${formatDiscordUser(player.discord_id, player.username, player.display_name)}</td>
                <td class="money">${formatMoney(player.total_earned)}</td>
            </tr>
        `).join('');
    }

    // Top Elite
    const topElite = data.leaderboards.elite_count.slice(0, 5);
    const topEliteBody = document.getElementById('top-elite');
    if (topEliteBody) {
        topEliteBody.innerHTML = topElite.map(player => `
            <tr>
                <td>${getRankBadge(player.rank)}</td>
                <td>${formatDiscordUser(player.discord_id, player.username, player.display_name)}</td>
                <td><span class="badge badge-elite">${player.elite_count}</span></td>
            </tr>
        `).join('');
    }
}

// Load recent heists
async function loadRecentHeists() {
    const data = await apiCall('dashboard');
    if (!data || !data.recent_heists) return;

    const recentHeists = data.recent_heists;
    const tbody = document.getElementById('recent-heists');

    if (!tbody) return;

    if (recentHeists.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center;">Aucun braquage récent</td></tr>';
        return;
    }

    tbody.innerHTML = recentHeists.map(heist => {
        const elite = heist.elite_challenge_completed ? '<span class="badge badge-elite">✓ Elite</span>' : '';
        const hardMode = heist.hard_mode ? '<span class="badge" style="background: #ff4444;">Hard</span>' : '';

        return `
            <tr>
                <td>${formatDate(heist.finished_at)}</td>
                <td>${formatDiscordUser(heist.leader_discord_id, heist.leader_username, heist.leader_display_name)}</td>
                <td>${getPrimaryLootEmoji(heist.primary_loot)} ${heist.primary_loot} ${hardMode}</td>
                <td>${heist.player_count} joueur${heist.player_count > 1 ? 's' : ''}</td>
                <td class="money">${formatMoney(heist.final_loot)}</td>
                <td>${formatTime(heist.mission_time_seconds)}</td>
                <td>${elite}</td>
            </tr>
        `;
    }).join('');
}
