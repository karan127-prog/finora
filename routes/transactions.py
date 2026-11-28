from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Transaction, Category

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/transactions')
@login_required
def index():
    # Query parameters for filters
    search_query = request.args.get('search', '').strip()
    type_filter = request.args.get('type', '')
    category_filter = request.args.get('category', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    sort_by = request.args.get('sort', 'date_desc')
    page = request.args.get('page', 1, type=int)
    per_page = 15

    query = Transaction.query.filter_by(user_id=current_user.id)

    # Search filter
    if search_query:
        query = query.filter(
            (Transaction.title.ilike(f'%{search_query}%')) |
            (Transaction.description.ilike(f'%{search_query}%')) |
            (Transaction.payment_method.ilike(f'%{search_query}%'))
        )

    # Type filter
    if type_filter in ('income', 'expense'):
        query = query.filter(Transaction.type == type_filter)

    # Category filter
    if category_filter and category_filter.isdigit():
        query = query.filter(Transaction.category_id == int(category_filter))

    # Date range filters
    if start_date:
        try:
            sd = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date >= sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date <= ed)
        except ValueError:
            pass

    # Sorting
    if sort_by == 'date_asc':
        query = query.order_by(Transaction.date.asc(), Transaction.id.asc())
    elif sort_by == 'amount_desc':
        query = query.order_by(Transaction.amount.desc())
    elif sort_by == 'amount_asc':
        query = query.order_by(Transaction.amount.asc())
    else:  # default date_desc
        query = query.order_by(Transaction.date.desc(), Transaction.id.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    transactions = pagination.items

    # Fetch categories for filter dropdowns
    categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None))
    ).order_by(Category.name.asc()).all()

    income_categories = [c for c in categories if c.type == 'income']
    expense_categories = [c for c in categories if c.type == 'expense']

    # Total counts and sums
    total_tx_count = query.count()
    all_matched = query.all()
    filtered_income = sum(t.amount for t in all_matched if t.type == 'income')
    filtered_expense = sum(t.amount for t in all_matched if t.type == 'expense')

    today_str = date.today().strftime('%Y-%m-%d')

    return render_template(
        'transactions/index.html',
        transactions=transactions,
        pagination=pagination,
        categories=categories,
        income_categories=income_categories,
        expense_categories=expense_categories,
        search_query=search_query,
        type_filter=type_filter,
        category_filter=category_filter,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        total_tx_count=total_tx_count,
        filtered_income=filtered_income,
        filtered_expense=filtered_expense,
        today_str=today_str
    )

@transactions_bp.route('/transactions/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title', '').strip()
    amount_str = request.form.get('amount', '0')
    t_type = request.form.get('type', 'expense')
    category_id = request.form.get('category_id')
    date_str = request.form.get('date', date.today().strftime('%Y-%m-%d'))
    payment_method = request.form.get('payment_method', 'UPI')
    description = request.form.get('description', '').strip()
    notes = request.form.get('notes', '').strip()

    if not title:
        flash('Transaction title is required.', 'danger')
        return redirect(request.referrer or url_for('transactions.index'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        flash('Please enter a valid positive transaction amount.', 'danger')
        return redirect(request.referrer or url_for('transactions.index'))

    try:
        t_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        t_date = date.today()

    cat_id = int(category_id) if category_id and category_id.isdigit() else None

    tx = Transaction(
        user_id=current_user.id,
        category_id=cat_id,
        title=title,
        amount=amount,
        type=t_type,
        date=t_date,
        payment_method=payment_method,
        description=description,
        notes=notes
    )
    db.session.add(tx)
    db.session.commit()

    flash(f'Transaction "{title}" of {current_user.currency_symbol}{amount:,.2f} recorded.', 'success')
    return redirect(request.referrer or url_for('transactions.index'))

@transactions_bp.route('/transactions/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    tx = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    title = request.form.get('title', '').strip()
    amount_str = request.form.get('amount', '0')
    t_type = request.form.get('type', tx.type)
    category_id = request.form.get('category_id')
    date_str = request.form.get('date')
    payment_method = request.form.get('payment_method', tx.payment_method)
    description = request.form.get('description', '').strip()
    notes = request.form.get('notes', '').strip()

    if not title:
        flash('Title cannot be empty.', 'danger')
        return redirect(request.referrer or url_for('transactions.index'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        flash('Invalid amount.', 'danger')
        return redirect(request.referrer or url_for('transactions.index'))

    if date_str:
        try:
            tx.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    tx.title = title
    tx.amount = amount
    tx.type = t_type
    tx.category_id = int(category_id) if category_id and category_id.isdigit() else None
    tx.payment_method = payment_method
    tx.description = description
    tx.notes = notes

    db.session.commit()
    flash('Transaction updated successfully.', 'success')
    return redirect(request.referrer or url_for('transactions.index'))

@transactions_bp.route('/transactions/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    tx = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    title = tx.title
    db.session.delete(tx)
    db.session.commit()
    flash(f'Transaction "{title}" deleted.', 'info')
    return redirect(request.referrer or url_for('transactions.index'))

@transactions_bp.route('/transactions/clear-past', methods=['POST'])
@login_required
def clear_past():
    today = date.today()
    deleted_count = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date < today
    ).delete(synchronize_session=False)
    db.session.commit()
    flash(f'Cleared {deleted_count} past transaction(s). Fresh tracking starts from today ({today.strftime("%d %b %Y")})!', 'success')
    return redirect(url_for('transactions.index'))

@transactions_bp.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    name = request.form.get('name', '').strip()
    cat_type = request.form.get('type', 'expense').strip().lower()
    icon = request.form.get('icon', 'tag').strip()
    color = request.form.get('color', '#789BB8').strip()

    if not name:
        flash('Category name is required.', 'danger')
        return redirect(request.referrer or url_for('transactions.index'))

    if cat_type not in ('income', 'expense'):
        cat_type = 'expense'

    # Check if category already exists for this user or globally
    existing = Category.query.filter(
        ((Category.user_id == current_user.id) | (Category.user_id.is_(None))),
        Category.name.ilike(name),
        Category.type == cat_type
    ).first()

    if existing:
        flash(f'Category "{name}" already exists in {cat_type.title()} categories.', 'warning')
        return redirect(request.referrer or url_for('transactions.index'))

    new_cat = Category(
        user_id=current_user.id,
        name=name,
        type=cat_type,
        icon=icon,
        color=color,
        is_default=False
    )
    db.session.add(new_cat)
    db.session.commit()

    flash(f'New {cat_type} category "{name}" created successfully.', 'success')
    return redirect(request.referrer or url_for('transactions.index'))

@transactions_bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    cat = Category.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    if cat.is_default:
        flash('Default system categories cannot be deleted.', 'warning')
        return redirect(request.referrer or url_for('transactions.index'))

    name = cat.name
    # Reassign transactions to null category
    Transaction.query.filter_by(category_id=cat.id).update({'category_id': None})
    db.session.delete(cat)
    db.session.commit()

    flash(f'Custom category "{name}" deleted.', 'info')
    return redirect(request.referrer or url_for('transactions.index'))
