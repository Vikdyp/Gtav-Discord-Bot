// Utilitaires JavaScript pour le dashboard

// Format number with spaces (French style)
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

// Format money (GTA$)
function formatMoney(amount) {
    return formatNumber(Math.round(amount));
}

// Format time (seconds to mm:ss)
function formatTime(seconds) {
    if (!seconds) return '--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Get rank badge HTML
function getRankBadge(rank) {
    if (rank === 1) return '<span class="badge badge-gold">🥇 #1</span>';
    if (rank === 2) return '<span class="badge badge-silver">🥈 #2</span>';
    if (rank === 3) return '<span class="badge badge-bronze">🥉 #3</span>';
    return `<span class="badge">#${rank}</span>`;
}

// Get primary loot emoji
function getPrimaryLootEmoji(loot) {
    const emojis = {
        'Tequila': '🍾',
        'Ruby Necklace': '💎',
        'Bearer Bonds': '📄',
        'Pink Diamond': '💎',
        'Panther Statue': '🐆'
    };
    return emojis[loot] || '❓';
}

// API call helper
async function apiCall(endpoint) {
    try {
        const response = await fetch(`/api/${endpoint}`);
        const data = await response.json();

        if (data.success) {
            return data.data;
        } else {
            console.error('API Error:', data);
            return null;
        }
    } catch (error) {
        console.error('Network Error:', error);
        return null;
    }
}

// Show loading spinner
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<div class="loading"></div>';
    }
}

// Format Discord user (username or ID)
function formatDiscordUser(discordId, username = null, displayName = null) {
    // Priorité: display_name > username > discord_id
    const name = displayName || username || discordId;
    return `<span style="color: var(--accent-blue);">@${name}</span>`;
}
