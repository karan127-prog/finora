/* FINORA - Charts & Visualizations (Chart.js) */

document.addEventListener('DOMContentLoaded', () => {
    // Set Chart.js global theme defaults
    if (window.Chart) {
        Chart.defaults.font.family = "'Manrope', 'Inter', sans-serif";
        Chart.defaults.color = '#8799A8';
        Chart.defaults.plugins.tooltip.backgroundColor = '#344454';
        Chart.defaults.plugins.tooltip.titleColor = '#FFFFFF';
        Chart.defaults.plugins.tooltip.bodyColor = '#E6EFF6';
        Chart.defaults.plugins.tooltip.padding = 12;
        Chart.defaults.plugins.tooltip.cornerRadius = 10;
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.plugins.tooltip.borderColor = '#789BB8';
    }

    // 1. Dashboard Overview Bar Chart (Income vs Expense)
    const overviewCanvas = document.getElementById('overviewBarChart');
    if (overviewCanvas) {
        let overviewChart = null;

        function loadOverviewChart(view = 'monthly') {
            fetch(`/api/chart-data?view=${view}`)
                .then(r => r.json())
                .then(data => {
                    const ctx = overviewCanvas.getContext('2d');
                    if (overviewChart) {
                        overviewChart.destroy();
                    }

                    overviewChart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: data.overview.labels,
                            datasets: [
                                {
                                    label: 'Income (₹)',
                                    data: data.overview.income,
                                    backgroundColor: '#8EAD98',
                                    borderRadius: 8,
                                    barPercentage: 0.6,
                                    categoryPercentage: 0.7
                                },
                                {
                                    label: 'Expenses (₹)',
                                    data: data.overview.expense,
                                    backgroundColor: '#D59A9A',
                                    borderRadius: 8,
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
                                        borderRadius: 4,
                                        font: { size: 12, weight: '500' }
                                    }
                                }
                            },
                            scales: {
                                x: {
                                    grid: { display: false },
                                    ticks: { font: { size: 11 } }
                                },
                                y: {
                                    grid: { color: '#E1EAF0' },
                                    ticks: {
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
            monthlyToggle.addEventListener('click', () => {
                monthlyToggle.classList.add('active');
                yearlyToggle.classList.remove('active');
                loadOverviewChart('monthly');
            });
            yearlyToggle.addEventListener('click', () => {
                yearlyToggle.classList.add('active');
                monthlyToggle.classList.remove('active');
                loadOverviewChart('yearly');
            });
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
                    '#789BB8', '#A9C5DC', '#8EAD98', '#D6B77A', '#D59A9A',
                    '#C5D2DC', '#8799A8', '#546E7A', '#7E909A', '#90A4AE'
                ];

                if (labels.length === 0 || values.every(v => v === 0)) {
                    doughnutCanvas.parentElement.innerHTML = `
                        <div class="empty-state" style="padding: 30px;">
                            <div class="empty-state-desc">No expense records found for this period.</div>
                        </div>
                    `;
                    return;
                }

                new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: palette.slice(0, labels.length),
                            borderWidth: 2,
                            borderColor: '#FFFFFF',
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
                                    font: { size: 11 }
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

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Income Inflow (₹)',
                    data: amounts,
                    backgroundColor: '#8EAD98',
                    borderRadius: 8,
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
                    x: { grid: { display: false }, ticks: { font: { size: 11 } } },
                    y: {
                        grid: { color: '#E1EAF0' },
                        ticks: {
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

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Expenditure (₹)',
                    data: amounts,
                    backgroundColor: '#D59A9A',
                    borderRadius: 8,
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
                    x: { grid: { display: false }, ticks: { font: { size: 11 } } },
                    y: {
                        grid: { color: '#E1EAF0' },
                        ticks: {
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

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Income (₹)',
                        data: income,
                        borderColor: '#8EAD98',
                        backgroundColor: 'rgba(142, 173, 152, 0.1)',
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4,
                        pointBackgroundColor: '#8EAD98'
                    },
                    {
                        label: 'Expenses (₹)',
                        data: expense,
                        borderColor: '#D59A9A',
                        backgroundColor: 'rgba(213, 154, 154, 0.1)',
                        tension: 0.35,
                        fill: true,
                        pointRadius: 4,
                        pointBackgroundColor: '#D59A9A'
                    },
                    {
                        label: 'Net Savings (₹)',
                        data: savings,
                        borderColor: '#789BB8',
                        borderDash: [5, 5],
                        tension: 0.35,
                        fill: false,
                        pointRadius: 4,
                        pointBackgroundColor: '#789BB8'
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
                        labels: { boxWidth: 12, useBorderRadius: true }
                    }
                },
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        grid: { color: '#E1EAF0' },
                        ticks: {
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
            '#789BB8', '#A9C5DC', '#8EAD98', '#D6B77A', '#D59A9A',
            '#C5D2DC', '#8799A8', '#546E7A', '#7E909A', '#90A4AE'
        ];

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: palette.slice(0, labels.length),
                    borderWidth: 2,
                    borderColor: '#FFFFFF',
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
                        labels: { boxWidth: 10, boxHeight: 10, useBorderRadius: true, font: { size: 11 } }
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
});
