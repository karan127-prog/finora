/* FINORA - Transactions, Income & Expense Helper JavaScript */

function openEditTransactionModal(id, title, amount, type, categoryId, date, paymentMethod, description, notes) {
    const form = document.getElementById('editTransactionForm');
    if (!form) return;

    form.action = `/transactions/edit/${id}`;
    
    const titleInput = document.getElementById('editTxTitle');
    const amountInput = document.getElementById('editTxAmount');
    const typeSelect = document.getElementById('editTxType');
    const catSelect = document.getElementById('editTxCategory');
    const dateInput = document.getElementById('editTxDate');
    const methodSelect = document.getElementById('editTxPaymentMethod');
    const descInput = document.getElementById('editTxDescription');
    const notesInput = document.getElementById('editTxNotes');

    if (titleInput) titleInput.value = title;
    if (amountInput) amountInput.value = amount;
    if (typeSelect) {
        typeSelect.value = type;
        filterEditCategories(type);
    }
    if (catSelect) catSelect.value = categoryId || '';
    if (dateInput) dateInput.value = date;
    if (methodSelect) methodSelect.value = paymentMethod || 'UPI';
    if (descInput) descInput.value = description || '';
    if (notesInput) notesInput.value = notes || '';

    window.openModal('editTransactionModal');
}

function filterEditCategories(type) {
    const catSelect = document.getElementById('editTxCategory');
    if (!catSelect) return;

    const options = catSelect.querySelectorAll('option[data-type]');
    options.forEach(opt => {
        if (opt.getAttribute('data-type') === type) {
            opt.style.display = '';
        } else {
            opt.style.display = 'none';
        }
    });
}

function openDeleteConfirmModal(id, title) {
    const form = document.getElementById('deleteTransactionForm');
    const titleSpan = document.getElementById('deleteTxTitleSpan');
    if (!form) return;

    form.action = `/transactions/delete/${id}`;
    if (titleSpan) titleSpan.innerText = title;

    window.openModal('deleteConfirmModal');
}

function openAddCategoryModal(defaultType = 'expense') {
    const typeSelect = document.getElementById('customCategoryTypeSelect');
    const modalTitle = document.getElementById('addCategoryModalTitle');
    if (typeSelect) {
        typeSelect.value = defaultType;
    }
    if (modalTitle) {
        modalTitle.innerText = defaultType === 'income' ? 'Create Custom Income Stream' : 'Create Custom Expense Category';
    }
    window.openModal('addCategoryModal');
}
