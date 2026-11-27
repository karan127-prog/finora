/* FINORA - Financial Calendar JavaScript */

document.addEventListener('DOMContentLoaded', () => {
    const calendarCells = document.querySelectorAll('.calendar-day-cell');
    const dayModal = document.getElementById('dayDetailsModal');
    const modalDateTitle = document.getElementById('modalSelectedDate');
    const modalDayEvents = document.getElementById('modalDayEvents');
    const calendarQuickAddBtn = document.getElementById('calendarQuickAddBtn');

    let activeSelectedIsoDate = '';

    calendarCells.forEach(cell => {
        cell.addEventListener('click', () => {
            const dateStr = cell.getAttribute('data-date');
            const isoDate = cell.getAttribute('data-iso-date');
            const dataAttr = cell.getAttribute('data-events');
            const currencySymbol = cell.getAttribute('data-currency') || '₹';
            if (!dateStr || !dataAttr) return;

            activeSelectedIsoDate = isoDate || '';

            try {
                const events = JSON.parse(dataAttr);
                if (modalDateTitle) {
                    modalDateTitle.innerText = dateStr;
                }

                let html = '';

                // Summary cards row
                html += `
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 18px;">
                        <div style="padding: 10px 12px; background: rgba(142, 173, 152, 0.15); border-radius: 10px; border: 1px solid rgba(142, 173, 152, 0.3);">
                            <div style="font-size: 0.68rem; color: #4b6e55; text-transform: uppercase; font-weight: 700;">Inflows</div>
                            <div style="font-size: 1.05rem; font-weight: 800; color: #4b6e55;">+${currencySymbol}${Number(events.income_sum || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                        </div>
                        <div style="padding: 10px 12px; background: rgba(213, 154, 154, 0.15); border-radius: 10px; border: 1px solid rgba(213, 154, 154, 0.3);">
                            <div style="font-size: 0.68rem; color: #8c4747; text-transform: uppercase; font-weight: 700;">Outflows</div>
                            <div style="font-size: 1.05rem; font-weight: 800; color: #8c4747;">-${currencySymbol}${Number(events.expense_sum || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                        </div>
                        ${events.savings_sum > 0 ? `
                        <div style="padding: 10px 12px; background: rgba(120, 155, 184, 0.15); border-radius: 10px; border: 1px solid rgba(120, 155, 184, 0.3);">
                            <div style="font-size: 0.68rem; color: #3b5f7e; text-transform: uppercase; font-weight: 700;">Saved</div>
                            <div style="font-size: 1.05rem; font-weight: 800; color: #3b5f7e;">+${currencySymbol}${Number(events.savings_sum).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                        </div>` : ''}
                    </div>
                `;

                // 1. Transactions List
                if (events.transactions && events.transactions.length > 0) {
                    html += '<h5 style="margin: 0 0 8px 0; font-size: 0.88rem; font-weight: 700; color: var(--text-primary);">Settled Transactions</h5>';
                    html += '<div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">';
                    events.transactions.forEach(t => {
                        const isInc = t.type === 'income';
                        html += `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: var(--background); border: 1px solid var(--border); border-radius: 10px;">
                                <div>
                                    <div style="font-weight: 600; font-size: 0.86rem; color: var(--text-primary);">${t.title}</div>
                                    <div style="font-size: 0.72rem; color: var(--text-secondary); margin-top: 2px;">
                                        <span class="badge" style="background: var(--sidebar); color: var(--secondary); font-size: 0.68rem; padding: 2px 6px;">${t.category}</span>
                                        <span style="margin-left: 4px;">• ${t.payment_method}</span>
                                    </div>
                                </div>
                                <div class="tx-amount ${t.type}" style="font-size: 0.92rem; font-weight: 700;">
                                    ${isInc ? '+' : '-'}${currencySymbol}${Number(t.amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                }

                // 2. Due Bills & Recurring Payments
                if (events.recurring && events.recurring.length > 0) {
                    html += '<h5 style="margin: 0 0 8px 0; font-size: 0.88rem; font-weight: 700; color: var(--text-primary);">Scheduled & Recurring Obligations</h5>';
                    html += '<div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">';
                    events.recurring.forEach(r => {
                        html += `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: #E6EFF6; border-radius: 10px; border-left: 3px solid var(--secondary);">
                                <div>
                                    <div style="font-weight: 600; font-size: 0.86rem; color: var(--text-primary);">${r.title}</div>
                                    <div style="font-size: 0.72rem; color: var(--secondary); margin-top: 2px;">
                                        Recurring (${r.frequency}) • ${r.payment_method}
                                    </div>
                                </div>
                                <div style="font-weight: 700; font-size: 0.92rem; color: var(--text-primary);">
                                    ${currencySymbol}${Number(r.amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                }

                // 3. Savings Contributions
                if (events.savings && events.savings.length > 0) {
                    html += '<h5 style="margin: 0 0 8px 0; font-size: 0.88rem; font-weight: 700; color: var(--text-primary);">Savings Goal Deposits</h5>';
                    html += '<div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px;">';
                    events.savings.forEach(s => {
                        html += `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: rgba(169, 197, 220, 0.2); border-radius: 10px; border-left: 3px solid var(--primary);">
                                <div>
                                    <div style="font-weight: 600; font-size: 0.86rem; color: var(--text-primary);">${s.goal_name}</div>
                                    ${s.notes ? `<div style="font-size: 0.72rem; color: var(--text-secondary); margin-top: 2px;">${s.notes}</div>` : ''}
                                </div>
                                <div style="font-weight: 700; font-size: 0.92rem; color: #3b5f7e;">
                                    +${currencySymbol}${Number(s.amount).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                                </div>
                            </div>
                        `;
                    });
                    html += '</div>';
                }

                if ((!events.transactions || events.transactions.length === 0) &&
                    (!events.recurring || events.recurring.length === 0) &&
                    (!events.savings || events.savings.length === 0)) {
                    html += `
                        <div style="text-align: center; color: var(--text-secondary); padding: 32px 16px;">
                            <i data-lucide="calendar-x" style="width: 32px; height: 32px; color: var(--accent); margin-bottom: 8px;"></i>
                            <div style="font-weight: 600; font-size: 0.9rem; color: var(--text-primary);">No financial movements</div>
                            <div style="font-size: 0.78rem; margin-top: 2px;">No settled transactions or due bills on this date.</div>
                        </div>
                    `;
                }

                if (modalDayEvents) {
                    modalDayEvents.innerHTML = html;
                }

                if (window.lucide) window.lucide.createIcons();
                window.openModal('dayDetailsModal');
            } catch (e) {
                console.error('Failed to parse calendar day data', e);
            }
        });
    });

    // Hook quick add button from calendar modal
    if (calendarQuickAddBtn) {
        calendarQuickAddBtn.addEventListener('click', () => {
            window.closeModal('dayDetailsModal');
            window.openQuickAddModal('expense');
            const quickDateInput = document.querySelector('#quickAddModal input[name="date"]');
            if (quickDateInput && activeSelectedIsoDate) {
                quickDateInput.value = activeSelectedIsoDate;
            }
        });
    }
});
