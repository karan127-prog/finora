from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, RecurringTransaction, Transaction, Category, Notification

recurring_bp = Blueprint('recurring', __name__)

@recurring_bp.route('/recurring')
@login_required
def index():
    items = RecurringTransaction.query.filter_by(user_id=current_user.id).order_by(RecurringTransaction.next_date.asc()).all()
    categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None))
    ).order_by(Category.name.asc()).all()

    today = date.today()
    total_recurring_monthly = 0.0
    active_count = 0
    upcoming_7_days = []
    overdue_count = 0

    for r in items:
        if r.is_active:
            active_count += 1
            if r.frequency == 'monthly':
                total_recurring_monthly += r.amount
            elif r.frequency == 'yearly':
                total_recurring_monthly += (r.amount / 12)
            elif r.frequency == 'weekly':
                total_recurring_monthly += (r.amount * 4.33)
            elif r.frequency == 'daily':
                total_recurring_monthly += (r.amount * 30)

            # Check due status
            if r.next_date < today:
                overdue_count += 1
            elif r.next_date <= today + timedelta(days=7):
                upcoming_7_days.append(r)

    today_str = today.strftime('%Y-%m-%d')

    return render_template(
        'recurring/index.html',
        recurring_items=items,
        categories=categories,
        total_recurring_monthly=round(total_recurring_monthly, 2),
        active_count=active_count,
        overdue_count=overdue_count,
        upcoming_7_days=upcoming_7_days,
        today=today,
        today_str=today_str
    )

@recurring_bp.route('/recurring/add', methods=['POST'])
@login_required
def add():
    title = request.form.get('title', '').strip()
    amount_str = request.form.get('amount', '0')
    t_type = request.form.get('type', 'expense')
    category_id = request.form.get('category_id')
    frequency = request.form.get('frequency', 'monthly')
    start_date_str = request.form.get('start_date')
    payment_method = request.form.get('payment_method', 'Net Banking')
    description = request.form.get('description', '')

    if not title:
        flash('Title is required.', 'danger')
        return redirect(url_for('recurring.index'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        flash('Invalid amount. Please specify a positive number.', 'danger')
        return redirect(url_for('recurring.index'))

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else date.today()
    except ValueError:
        start_date = date.today()

    cat_id = int(category_id) if category_id and category_id.isdigit() else None

    item = RecurringTransaction(
        user_id=current_user.id,
        category_id=cat_id,
        title=title,
        amount=amount,
        type=t_type,
        frequency=frequency,
        start_date=start_date,
        next_date=start_date,
        payment_method=payment_method,
        description=description,
        is_active=True
    )
    db.session.add(item)
    db.session.commit()

    flash(f'Recurring activity "{title}" created successfully.', 'success')
    return redirect(url_for('recurring.index'))

@recurring_bp.route('/recurring/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    item = RecurringTransaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    title = request.form.get('title', '').strip()
    amount_str = request.form.get('amount', '0')
    t_type = request.form.get('type', 'expense')
    category_id = request.form.get('category_id')
    frequency = request.form.get('frequency', 'monthly')
    next_date_str = request.form.get('next_date')
    payment_method = request.form.get('payment_method', 'Net Banking')
    description = request.form.get('description', '')

    if not title:
        flash('Title is required.', 'danger')
        return redirect(url_for('recurring.index'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        flash('Invalid amount. Please specify a positive number.', 'danger')
        return redirect(url_for('recurring.index'))

    try:
        next_date = datetime.strptime(next_date_str, '%Y-%m-%d').date() if next_date_str else item.next_date
    except ValueError:
        next_date = item.next_date

    cat_id = int(category_id) if category_id and category_id.isdigit() else None

    item.title = title
    item.amount = amount
    item.type = t_type
    item.category_id = cat_id
    item.frequency = frequency
    item.next_date = next_date
    item.payment_method = payment_method
    item.description = description

    db.session.commit()
    flash(f'Recurring activity "{title}" updated successfully.', 'success')
    return redirect(url_for('recurring.index'))

@recurring_bp.route('/recurring/toggle/<int:id>', methods=['POST'])
@login_required
def toggle(id):
    item = RecurringTransaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    item.is_active = not item.is_active
    db.session.commit()
    status_str = 'enabled' if item.is_active else 'paused'
    flash(f'Recurring activity "{item.title}" is now {status_str}.', 'info')
    return redirect(url_for('recurring.index'))

@recurring_bp.route('/recurring/process-due', methods=['POST'])
@login_required
def process_due():
    """Execute due recurring payments into real transactions and increment next_date without duplicating."""
    today = date.today()
    due_items = RecurringTransaction.query.filter(
        RecurringTransaction.user_id == current_user.id,
        RecurringTransaction.is_active == True,
        RecurringTransaction.next_date <= today
    ).all()

    processed_count = 0
    for item in due_items:
        # Check if transaction for this item on next_date already exists to avoid duplicates
        existing = Transaction.query.filter_by(
            user_id=current_user.id,
            title=item.title,
            date=item.next_date
        ).first()

        if not existing:
            tx = Transaction(
                user_id=current_user.id,
                category_id=item.category_id,
                title=item.title,
                amount=item.amount,
                type=item.type,
                date=item.next_date,
                payment_method=item.payment_method,
                description=f'Recurring auto-execution ({item.frequency})'
            )
            db.session.add(tx)
            processed_count += 1

            # Generate in-app notification
            notif = Notification(
                user_id=current_user.id,
                title=f"Recurring Processed: {item.title}",
                message=f"Recorded {item.type} of ₹{item.amount:,.2f} for '{item.title}' scheduled on {item.next_date.strftime('%d-%b-%Y')}.",
                type='success'
            )
            db.session.add(notif)

        # Calculate next due date
        if item.frequency == 'daily':
            item.next_date += timedelta(days=1)
        elif item.frequency == 'weekly':
            item.next_date += timedelta(weeks=1)
        elif item.frequency == 'monthly':
            next_m = item.next_date.month % 12 + 1
            next_y = item.next_date.year + (item.next_date.month // 12)
            try:
                item.next_date = item.next_date.replace(year=next_y, month=next_m)
            except ValueError:
                item.next_date += timedelta(days=30)
        elif item.frequency == 'yearly':
            item.next_date = item.next_date.replace(year=item.next_date.year + 1)

    db.session.commit()
    if processed_count > 0:
        flash(f'Successfully processed {processed_count} recurring payment(s) into your transaction ledger!', 'success')
    else:
        flash('All recurring payments are up to date. No pending payments were due for execution today.', 'info')

    return redirect(url_for('recurring.index'))

@recurring_bp.route('/recurring/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    item = RecurringTransaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    title = item.title
    db.session.delete(item)
    db.session.commit()
    flash(f'Recurring activity "{title}" deleted.', 'info')
    return redirect(url_for('recurring.index'))
