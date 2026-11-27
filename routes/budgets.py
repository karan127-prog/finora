from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Budget, Category, Transaction, Notification

budgets_bp = Blueprint('budgets', __name__)

@budgets_bp.route('/budgets')
@login_required
def index():
    today = date.today()
    selected_month = request.args.get('month', today.strftime('%Y-%m'))

    # Calculate previous and next month strings for convenient month switching
    try:
        cur_dt = datetime.strptime(selected_month, '%Y-%m').date()
    except ValueError:
        cur_dt = today.replace(day=1)
        selected_month = today.strftime('%Y-%m')

    prev_month_date = (cur_dt.replace(day=1) - timedelta(days=1)).replace(day=1)
    prev_month_str = prev_month_date.strftime('%Y-%m')
    next_month_date = (cur_dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    next_month_str = next_month_date.strftime('%Y-%m')

    # Fetch all expense categories for current user (including defaults)
    expense_categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        Category.type == 'expense'
    ).order_by(Category.name.asc()).all()

    # Fetch existing budgets for selected month
    budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=selected_month
    ).all()

    # Fetch all expense transactions for the selected month
    month_txs = Transaction.query.filter_by(
        user_id=current_user.id,
        type='expense'
    ).all()
    
    cat_spent_map = {}
    for t in month_txs:
        if t.date.strftime('%Y-%m') == selected_month:
            cat_spent_map[t.category_id] = cat_spent_map.get(t.category_id, 0.0) + t.amount

    budget_cards = []
    total_budget_limit = 0.0
    total_budget_spent = 0.0
    overspent_categories = []
    approaching_categories = []
    budgeted_cat_ids = set()

    for b in budgets:
        budgeted_cat_ids.add(b.category_id)
        spent = cat_spent_map.get(b.category_id, 0.0)
        rem = b.limit_amount - spent
        pct = round((spent / b.limit_amount * 100), 1) if b.limit_amount > 0 else 0
        total_budget_limit += b.limit_amount
        total_budget_spent += spent

        # Warning threshold rules:
        # < 70%: Normal / On Track (Safe)
        # 70% - 89.9%: Approaching limit (Warning)
        # 90% - 99.9%: Critical warning (Critical)
        # >= 100%: Budget exceeded (Exceeded)
        if pct >= 100:
            status_level = 'exceeded'
            badge_label = 'Budget Exceeded (100%+)'
            badge_class = 'badge-danger'
            bar_class = 'exceeded'
            overspent_categories.append({
                'name': b.category_rel.name if b.category_rel else 'General',
                'limit': b.limit_amount,
                'spent': spent,
                'exceeded_by': abs(rem)
            })
        elif pct >= 90:
            status_level = 'critical'
            badge_label = 'Critical Warning (90%+)'
            badge_class = 'badge-warning'
            bar_class = 'critical'
            approaching_categories.append({
                'name': b.category_rel.name if b.category_rel else 'General',
                'percentage': pct,
                'remaining': rem
            })
        elif pct >= 70:
            status_level = 'approaching'
            badge_label = 'Approaching Limit (70%+)'
            badge_class = 'badge-caution'
            bar_class = 'warning'
            approaching_categories.append({
                'name': b.category_rel.name if b.category_rel else 'General',
                'percentage': pct,
                'remaining': rem
            })
        else:
            status_level = 'healthy'
            badge_label = 'On Track'
            badge_class = 'badge-success'
            bar_class = 'safe'

        # Automated Smart Notification Generation when thresholds breached
        cat_name = b.category_rel.name if b.category_rel else 'General'
        if pct >= 70 and selected_month == today.strftime('%Y-%m'):
            # Check if alert already created this month for this category
            alert_prefix = f"Budget Alert [{selected_month}]: {cat_name}"
            recent_notif = Notification.query.filter(
                Notification.user_id == current_user.id,
                Notification.title == alert_prefix
            ).first()

            if not recent_notif:
                if pct >= 100:
                    notif_type = 'danger'
                    msg = f"You have exceeded your {cat_name} budget! Spent: {current_user.currency_symbol}{spent:,.2f} of {current_user.currency_symbol}{b.limit_amount:,.2f} (over by {current_user.currency_symbol}{abs(rem):,.2f})."
                elif pct >= 90:
                    notif_type = 'warning'
                    msg = f"Critical budget warning: You have used {pct}% of your {cat_name} budget. Only {current_user.currency_symbol}{rem:,.2f} remaining."
                else:
                    notif_type = 'warning'
                    msg = f"Approaching limit: You have used {pct}% of your {cat_name} budget. Please plan remaining expenses carefully."

                new_alert = Notification(
                    user_id=current_user.id,
                    title=alert_prefix,
                    message=msg,
                    type=notif_type
                )
                db.session.add(new_alert)
                db.session.commit()

        budget_cards.append({
            'id': b.id,
            'category_id': b.category_id,
            'category_name': b.category_rel.name if b.category_rel else 'General',
            'category_icon': b.category_rel.icon if b.category_rel else 'tag',
            'category_color': b.category_rel.color if b.category_rel else '#A9C5DC',
            'limit': b.limit_amount,
            'spent': spent,
            'remaining': rem,
            'percentage': pct,
            'status_level': status_level,
            'badge_label': badge_label,
            'badge_class': badge_class,
            'bar_class': bar_class
        })

    overall_remaining = max(0.0, total_budget_limit - total_budget_spent)
    overall_pct = round((total_budget_spent / total_budget_limit * 100), 1) if total_budget_limit > 0 else 0
    total_overspent = sum(item['exceeded_by'] for item in overspent_categories)

    # Categories not yet budgeted for in this month
    unbudgeted_categories = [c for c in expense_categories if c.id not in budgeted_cat_ids]

    return render_template(
        'budgets/index.html',
        budgets=budget_cards,
        expense_categories=expense_categories,
        unbudgeted_categories=unbudgeted_categories,
        selected_month=selected_month,
        prev_month=prev_month_str,
        next_month=next_month_str,
        total_budget_limit=total_budget_limit,
        total_budget_spent=total_budget_spent,
        overall_remaining=overall_remaining,
        overall_pct=overall_pct,
        overspent_categories=overspent_categories,
        approaching_categories=approaching_categories,
        total_overspent=total_overspent
    )

@budgets_bp.route('/budgets/add', methods=['POST'])
@login_required
def add():
    category_id = request.form.get('category_id')
    month = request.form.get('month', date.today().strftime('%Y-%m'))
    limit_str = request.form.get('limit_amount', '0')

    if not category_id or not category_id.isdigit():
        flash('Please select a valid expense category.', 'danger')
        return redirect(url_for('budgets.index', month=month))

    try:
        limit_amount = float(limit_str)
        if limit_amount <= 0:
            raise ValueError()
    except ValueError:
        flash('Please enter a valid positive budget limit.', 'danger')
        return redirect(url_for('budgets.index', month=month))

    # Verify category belongs to user or is system default
    cat = Category.query.filter(
        ((Category.user_id == current_user.id) | (Category.user_id.is_(None))),
        Category.id == int(category_id)
    ).first_or_404()

    # Check if budget already exists for this category and month (upsert)
    existing = Budget.query.filter_by(
        user_id=current_user.id,
        category_id=cat.id,
        month=month
    ).first()

    if existing:
        existing.limit_amount = limit_amount
        flash(f'Budget target for "{cat.name}" updated to {current_user.currency_symbol}{limit_amount:,.2f}.', 'success')
    else:
        new_budget = Budget(
            user_id=current_user.id,
            category_id=cat.id,
            month=month,
            limit_amount=limit_amount
        )
        db.session.add(new_budget)
        flash(f'New budget of {current_user.currency_symbol}{limit_amount:,.2f} set for "{cat.name}".', 'success')

    db.session.commit()
    return redirect(url_for('budgets.index', month=month))

@budgets_bp.route('/budgets/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    budget = Budget.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    limit_str = request.form.get('limit_amount', '0')
    month = request.form.get('month', budget.month)

    try:
        limit_amount = float(limit_str)
        if limit_amount <= 0:
            raise ValueError()
    except ValueError:
        flash('Please enter a valid positive budget amount.', 'danger')
        return redirect(url_for('budgets.index', month=budget.month))

    budget.limit_amount = limit_amount
    budget.month = month
    db.session.commit()

    cat_name = budget.category_rel.name if budget.category_rel else 'Category'
    flash(f'Budget limit for "{cat_name}" updated to {current_user.currency_symbol}{limit_amount:,.2f}.', 'success')
    return redirect(url_for('budgets.index', month=month))

@budgets_bp.route('/budgets/copy-previous', methods=['POST'])
@login_required
def copy_previous():
    to_month = request.form.get('to_month', date.today().strftime('%Y-%m'))
    from_month = request.form.get('from_month')

    if not from_month:
        try:
            d = datetime.strptime(to_month, '%Y-%m').date()
            prev_d = (d.replace(day=1) - timedelta(days=1)).replace(day=1)
            from_month = prev_d.strftime('%Y-%m')
        except ValueError:
            from_month = date.today().strftime('%Y-%m')

    # Fetch previous budgets
    prev_budgets = Budget.query.filter_by(user_id=current_user.id, month=from_month).all()
    if not prev_budgets:
        flash(f'No budget targets found in period {from_month} to copy.', 'warning')
        return redirect(url_for('budgets.index', month=to_month))

    copied_count = 0
    for pb in prev_budgets:
        existing = Budget.query.filter_by(user_id=current_user.id, category_id=pb.category_id, month=to_month).first()
        if not existing:
            nb = Budget(
                user_id=current_user.id,
                category_id=pb.category_id,
                month=to_month,
                limit_amount=pb.limit_amount
            )
            db.session.add(nb)
            copied_count += 1

    db.session.commit()
    if copied_count > 0:
        flash(f'Successfully cloned {copied_count} budget targets from {from_month} into {to_month}.', 'success')
    else:
        flash('All budget categories for this month were already configured.', 'info')

    return redirect(url_for('budgets.index', month=to_month))

@budgets_bp.route('/budgets/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    budget = Budget.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    month = budget.month
    cat_name = budget.category_rel.name if budget.category_rel else 'Category'
    db.session.delete(budget)
    db.session.commit()
    flash(f'Budget target for "{cat_name}" removed.', 'info')
    return redirect(url_for('budgets.index', month=month))
