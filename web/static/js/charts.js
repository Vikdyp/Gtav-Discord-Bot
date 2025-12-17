// Configuration globale pour Chart.js avec style GTA

// Thème sombre GTA
const chartTheme = {
    backgroundColor: '#2a2a2a',
    gridColor: '#3a3a3a',
    textColor: '#b0b0b0',
    accentGreen: '#7cfc00',
    accentBlue: '#00bfff',
    accentYellow: '#ffd700',
};

// Configuration par défaut pour tous les charts
Chart.defaults.color = chartTheme.textColor;
Chart.defaults.borderColor = chartTheme.gridColor;
Chart.defaults.backgroundColor = chartTheme.backgroundColor;

// Options communes
const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            labels: {
                color: chartTheme.textColor,
                font: {
                    size: 14,
                    weight: 'bold'
                }
            }
        },
        tooltip: {
            backgroundColor: 'rgba(26, 26, 26, 0.9)',
            titleColor: chartTheme.accentGreen,
            bodyColor: chartTheme.textColor,
            borderColor: chartTheme.accentGreen,
            borderWidth: 2,
            padding: 12,
            displayColors: true,
            callbacks: {}
        }
    },
    scales: {
        x: {
            grid: {
                color: chartTheme.gridColor
            },
            ticks: {
                color: chartTheme.textColor
            }
        },
        y: {
            grid: {
                color: chartTheme.gridColor
            },
            ticks: {
                color: chartTheme.textColor
            }
        }
    }
};

// Create activity chart (bar chart)
function createActivityChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const labels = data.map(d => {
        const date = new Date(d.date);
        return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    });

    const values = data.map(d => d.count ?? d.heist_count ?? 0);

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Braquages par jour',
                data: values,
                backgroundColor: chartTheme.accentGreen + '80',
                borderColor: chartTheme.accentGreen,
                borderWidth: 2
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                title: {
                    display: true,
                    text: 'Activité des 30 Derniers Jours',
                    color: chartTheme.accentGreen,
                    font: {
                        size: 18,
                        weight: 'bold'
                    }
                }
            }
        }
    });
}

// Create gains chart (line chart with area)
function createGainsChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const labels = data.map(d => {
        const date = new Date(d.week_start);
        return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
    });

    const values = data.map(d => d.total_gains);

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Gains hebdomadaires (GTA$)',
                data: values,
                backgroundColor: chartTheme.accentBlue + '40',
                borderColor: chartTheme.accentBlue,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: chartTheme.accentBlue,
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                title: {
                    display: true,
                    text: 'Gains des 12 Dernières Semaines',
                    color: chartTheme.accentBlue,
                    font: {
                        size: 18,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    ...commonOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += formatMoney(context.parsed.y) + ' $';
                            return label;
                        }
                    }
                }
            },
            scales: {
                ...commonOptions.scales,
                y: {
                    ...commonOptions.scales.y,
                    ticks: {
                        ...commonOptions.scales.y.ticks,
                        callback: function(value) {
                            return formatMoney(value) + ' $';
                        }
                    }
                }
            }
        }
    });
}

// Create progression chart (for user profile)
function createProgressionChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const labels = data.map((d, index) => `#${index + 1}`);
    const values = data.map(d => d.real_gain);

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Gains par braquage (GTA$)',
                data: values,
                backgroundColor: chartTheme.accentGreen + '40',
                borderColor: chartTheme.accentGreen,
                borderWidth: 3,
                fill: true,
                tension: 0.3,
                pointBackgroundColor: chartTheme.accentGreen,
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            ...commonOptions,
            plugins: {
                ...commonOptions.plugins,
                title: {
                    display: true,
                    text: 'Progression des Gains',
                    color: chartTheme.accentGreen,
                    font: {
                        size: 18,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    ...commonOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            return `Gain: ${formatMoney(context.parsed.y)} $`;
                        }
                    }
                }
            },
            scales: {
                ...commonOptions.scales,
                y: {
                    ...commonOptions.scales.y,
                    ticks: {
                        ...commonOptions.scales.y.ticks,
                        callback: function(value) {
                            return formatMoney(value) + ' $';
                        }
                    }
                }
            }
        }
    });
}

// Create pie chart (for primary targets distribution)
function createPieChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const labels = data.map(d => d.primary_loot);
    const values = data.map(d => d.count);
    const colors = [
        '#7cfc00',
        '#00bfff',
        '#ffd700',
        '#ff00ff',
        '#ff4444'
    ];

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors.map(c => c + '80'),
                borderColor: colors,
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: chartTheme.textColor,
                        font: {
                            size: 14
                        },
                        padding: 15
                    }
                },
                title: {
                    display: true,
                    text: 'Répartition des Cibles Primaires',
                    color: chartTheme.accentYellow,
                    font: {
                        size: 18,
                        weight: 'bold'
                    }
                }
            }
        }
    });
}
