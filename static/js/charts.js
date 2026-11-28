/* FINORA - Charts & Visualizations (Chart.js)
   Theme: Obsidian Dark + Electric Emerald Palette */

const activeChartInstances = {};

function safeDestroyChart(id) {
    if (activeChartInstances[id]) {
        try { activeChartInstances[id].destroy(); } catch (e) {}
        delete activeChartInstances[id];
    }
}

window.initAllCharts = function() {
    if (!window.Chart) return;

    // Set Chart.js global theme defaults
    Chart.defaults.font.family = "'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif";
    Chart.defaults.color = '#94A3B8';
    Chart.defaults.plugins.tooltip.backgroundColor = '#0E1724';
    Chart.defaults.plugins.tooltip.titleColor = '#FFFFFF';
    Chart.defaults.plugins.tooltip.bodyColor = '#CBD5E1';
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.cornerRadius = 10;
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.borderColor = '#1B2B3E';

    const gridColor = 'rgba(255, 255, 255, 0.06)';
    const cardBgColor = '#111C2B';

    // 1. Dashboard Overview Bar Chart (Income vs Expense)
    const overviewCanvas = document.getElementById('overviewBarChart');
    if (overviewCanvas) {
        function loadOverviewChart(view = 'monthly') {
            fetch(`/api/chart-data?view=${view}`)
                .then(r => r.json())
                .then(data => {
                    const ctx = overviewCanvas.getContext('2d');
                    safeDestroyChart('overviewBarChart');

                    activeChartInstances['overviewBarChart'] = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: data.overview.labels,
                            datasets: [
                                {
                                    label: 'Income (₹)',
                                    data: data.overview.income,
                                    backgroundColor: '#00E599',
                                    borderRadius: 6,
                                    barPercentage: 0.6,
                                    categoryPercentage: 0.7
                                },
                                {
                                    label: 'Expenses (₹)',
                                    data: data.overview.expense,
                                    backgroundColor: '#FF536E',
                                    borderRadius: 6,
                                    barPercentage: 0.6,
                                    categoryPercentage: 0.7
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    position: 'top',
                                    align: 'end',
                                    labels: {
                                        boxWidth: 12,
                                        boxHeight: 12,
                                        useBorderRadius: true,
                                        borderRadius: 3,
                                        color: '#CBD5E1',
                                        font: { size: 12, weight: '600' }
                                    }
                                }
                            },
                            scales: {
                                x: {
                                    grid: { display: false },
                                    ticks: { color: '#94A3B8', font: { size: 11 } }
                                },
                                y: {
                                    grid: { color: gridColor },
                                    ticks: {
                                        color: '#94A3B8',
                                        font: { size: 11 },
                                        callback: function(value) {
                                            if (value >= 1000) return '₹' + (value / 1000) + 'k';
                                            return '₹' + value;
                                        }
                                    }
                                }
                            }
                        }
                    });
                });
        }

        loadOverviewChart('monthly');

        const monthlyToggle = document.getElementById('chartViewMonthly');
        const yearlyToggle = document.getElementById('chartViewYearly');

        if (monthlyToggle && yearlyToggle) {
            monthlyToggle.onclick = () => {
                monthlyToggle.classList.add('active');
                yearlyToggle.classList.remove('active');
                loadOverviewChart('monthly');
            };
            yearlyToggle.onclick = () => {
                yearlyToggle.classList.add('active');
                monthlyToggle.classList.remove('active');
                loadOverviewChart('yearly');
            };
        }
    }

    // 2. Expense Breakdown Doughnut Chart (Dashboard)
    const doughnutCanvas = document.getElementById('expenseDoughnutChart');
    if (doughnutCanvas) {
        fetch('/api/chart-data')
            .then(r => r.json())
            .then(data => {
                const ctx = doughnutCanvas.getContext('2d');
                const labels = data.categories.labels;
                const values = data.categories.data;

                const palette = [
                    '#00E599', '#38BDF8', '#FBBF24', '#FF536E', '#A855F7',
                    '#EC4899', '#06B6D4', '#818CF8', '#10B981', '#F43F5E'
                ];

                if (labels.length === 0 || values.every(v => v === 0)) {
                    doughnutCanvas.parentElement.innerHTML = `
                        <div class="empty-state" style="padding: 30px;">
                            <div class="empty-state-desc" style="color: #94A3B8;">No expense records found for this period.</div>
                        </div>
                    `;
                    return;
                }

                safeDestroyChart('expenseDoughnutChart');
                activeChartInstances['expenseDoughnutChart'] = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: palette.slice(0, labels.length),
                            borderWidth: 2,
                            borderColor: cardBgColor,
                            hoverOffset: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '72%',
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: {
                                    boxWidth: 10,
                                    boxHeight: 10,
                                    useBorderRadius: true,
                                    borderRadius: 3,
                                    color: '#CBD5E1',
                                    font: { size: 11, weight: '500' }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        return ` ${label}: ₹${value.toLocaleString()}`;
                                    }
                                }
                            }
                        }
                    }
                });
            });
    }

    // 3. Income Page - Monthly Inflow Trends Bar Chart
    const incomeTrendCanvas = document.getElementById('incomeTrendsBarChart');
    if (incomeTrendCanvas && window.finoraIncomeTrends) {
        const ctx = incomeTrendCanvas.getContext('2d');
        const labels = window.finoraIncomeTrends.map(d => d.label);
        const amounts = window.finoraIncomeTrends.map(d => d.amount);

        safeDestroyChart('incomeTrendsBarChart');
        activeChartInstances['incomeTrendsBarChart'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Income Inflow (₹)',
                    data: amounts,
                    backgroundColor: '#00E599',
                    borderRadius: 6,
                    barPercentage: 0.55
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) { return ' Income: ₹' + ctx.parsed.y.toLocaleString(); }
                        }
                    }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#94A3B8', font: { size: 11 } } },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            color: '#94A3B8',
                            callback: function(v) { return (v >= 1000) ? '₹' + (v / 1000) + 'k' : '₹' + v; }
                        }
                    }
                }
            }
        });
    }

    // 4. Expenses Page - Monthly Outflow Trends Bar Chart
    const expenseTrendCanvas = document.getElementById('expenseTrendsBarChart');
    if (expenseTrendCanvas && window.finoraExpenseTrends) {
        const ctx = expenseTrendCanvas.getContext('2d');
        const labels = window.finoraExpenseTrends.map(d => d.label);
        const amounts = window.finoraExpenseTrends.map(d => d.amount);

        safeDestroyChart('expenseTrendsBarChart');
        activeChartInstances['expenseTrendsBarChart'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Expenditure (₹)',
                    data: amounts,
                    backgroundColor: '#FF536E',
                    borderRadius: 6,
                    barPercentage: 0.55
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) { return ' Outflow: ₹' + ctx.parsed.y.toLocaleString(); }
                        }
                    }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#94A3B8', font: { size: 11 } } },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            color: '#94A3B8',
                            callback: function(v) { return (v >= 1000) ? '₹' + (v / 1000) + 'k' : '₹' + v; }
                        }
                    }
                }
            }
        });
    }

    // 5. Analytics Trends Multi-Line Chart
    const trendCanvas = document.getElementById('analyticsTrendChart');
    if (trendCanvas && window.finoraTrendData) {
        const ctx = trendCanvas.getContext('2d');
        const labels = window.finoraTrendData.map(d => d.label);
        const income = window.finoraTrendData.map(d => d.income);
        const expense = window.finoraTrendData.map(d => d.expense);
        const savings = window.finoraTrendData.map(d => d.savings);

        safeDestroyChart('analyticsTrendChart');
        activeChartInstances['analyticsTrendChart'] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Income (₹)',
                        data: income,
                        borderColor: '#00E599',
                        backgroundColor: 'rgba(0, 229, 153, 0.1)',
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4,
                        pointBackgroundColor: '#00E599'
                    },
                    {
                        label: 'Expenses (₹)',
                        data: expense,
                        borderColor: '#FF536E',
                        backgroundColor: 'rgba(255, 83, 110, 0.1)',
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4,
                        pointBackgroundColor: '#FF536E'
                    },
                    {
                        label: 'Net Savings (₹)',
                        data: savings,
                        borderColor: '#38BDF8',
                        borderDash: [5, 5],
                        tension: 0.35,
                        fill: false,
                        pointRadius: 4,
                        pointBackgroundColor: '#38BDF8'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        align: 'end',
                        labels: { boxWidth: 12, useBorderRadius: true, color: '#CBD5E1' }
                    }
                },
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#94A3B8' } },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            color: '#94A3B8',
                            callback: function(v) { return (v >= 1000) ? '₹' + (v / 1000) + 'k' : '₹' + v; }
                        }
                    }
                }
            }
        });
    }

    // 6. Analytics Category Doughnut Chart
    const analyticsDoughnut = document.getElementById('analyticsCategoryDoughnut');
    if (analyticsDoughnut && window.finoraCategoryData) {
        const ctx = analyticsDoughnut.getContext('2d');
        const labels = window.finoraCategoryData.map(c => c.name);
        const data = window.finoraCategoryData.map(c => c.amount);

        const palette = [
            '#00E599', '#38BDF8', '#FBBF24', '#FF536E', '#A855F7',
            '#EC4899', '#06B6D4', '#818CF8', '#10B981', '#F43F5E'
        ];

        safeDestroyChart('analyticsCategoryDoughnut');
        activeChartInstances['analyticsCategoryDoughnut'] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: palette.slice(0, labels.length),
                    borderWidth: 2,
                    borderColor: cardBgColor,
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { boxWidth: 10, boxHeight: 10, useBorderRadius: true, color: '#CBD5E1', font: { size: 11 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) { return ' ' + ctx.label + ': ₹' + Number(ctx.parsed).toLocaleString(); }
                        }
                    }
                }
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', window.initAllCharts);
