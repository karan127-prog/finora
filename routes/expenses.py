from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import db, Transaction, Category, Budget

expenses_bp = Blueprint('expenses', __name__)

@expenses_bp.route('/expenses')
@login_required
def index():
    today = date.today()
    current_month_str = today.strftime('%Y-%m')
    current_year_str = str(today.year)

    # Query params for filters & search
    search_query = request.args.get('search', '').strip()
    category_filter = request.args.get('category_id', '').strip()
    month_filter = request.args.get('month', '').strip()
    sort_by = request.args.get('sort', 'date_desc')
    page = request.args.get('page', 1, type=int)
    per_page = 15

    # Fetch all expense categories for this user (including default)
    expense_categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        Category.type == 'expense'
    ).order_by(Category.name.asc()).all()

    # Base query for all user expense transactions
    all_expenses_query = Transaction.query.filter_by(
        user_id=current_user.id,
        type='expense'
    )
    all_expenses_txs = all_expenses_query.order_by(Transaction.date.desc()).all()

    # Calculate overall metrics
    current_month_expenses = sum(t.amount for t in all_expenses_txs if t.date.strftime('%Y-%m') == current_month_str)
    ytd_expenses = sum(t.amount for t in all_expenses_txs if str(t.date.year) == current_year_str)
    all_time_expenses = sum(t.amount for t in all_expenses_txs)

    # Daily average burn for current month
    days_passed = max(1, today.day)
    avg_daily_spend = round(current_month_expenses / days_passed, 1)

    # Highest single expense item ever recorded
    highest_tx = max(all_expenses_txs, key=lambda x: x.amount) if all_expenses_txs else None

    # Fetch active budgets for current month to calculate utilization
    monthly_budgets = {b.category_id: b.limit_amount for b in Budget.query.filter_by(user_id=current_user.id, month=current_month_str).all()}

    # Category totals for current month
    cat_totals = {}
    cat_counts = {}
    for t in all_expenses_txs:
        if t.date.strftime('%Y-%m') == current_month_str:
            c_name = t.category_name
            cat_totals[c_name] = cat_totals.get(c_name, 0.0) + t.amount
            cat_counts[c_name] = cat_counts.get(c_name, 0) + 1

    cat_meta_map = {c.name: {'icon': c.icon, 'color': c.color, 'id': c.id} for c in expense_categories}

    expense_breakdown = []
    for cat_name, amt in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True):
        pct = round((amt / current_month_expenses * 100), 1) if current_month_expenses > 0 else 0
        meta = cat_meta_map.get(cat_name, {'icon': 'credit-card', 'color': '#D59A9A', 'id': None})
        cat_id = meta['id']
        b_limit = monthly_budgets.get(cat_id)
        b_utilization = round((amt / b_limit * 100), 1) if b_limit and b_limit > 0 else None

        expense_breakdown.append({
            'name': cat_name,
            'amount': amt,
            'percentage': pct,
            'count': cat_counts.get(cat_name, 0),
            'icon': meta['icon'],
            'color': meta['color'],
            'id': cat_id,
            'budget_limit': b_limit,
            'budget_utilization': b_utilization
        })

    # Distinct active months for filter
    distinct_months = set(t.date.strftime('%Y-%m') for t in all_expenses_txs)
    available_months_set = sorted(distinct_months, reverse=True)
    available_months = []
    for m in available_months_set:
        try:
            d = datetime.strptime(m, '%Y-%m')
            available_months.append({'value': m, 'label': d.strftime('%B %Y')})
        except ValueError:
            pass

    # Monthly trends (last 6 months) for visualization
    monthly_trends = []
    for i in range(5, -1, -1):
        m_date = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        m_str = m_date.strftime('%Y-%m')
        m_label = m_date.strftime('%b %Y')
        m_sum = sum(t.amount for t in all_expenses_txs if t.date.strftime('%Y-%m') == m_str)
        monthly_trends.append({'label': m_label, 'month': m_str, 'amount': m_sum})

    # Filtered Query for the ledger table
    filter_query = Transaction.query.filter_by(user_id=current_user.id, type='expense')

    if search_query:
        filter_query = filter_query.filter(
            (Transaction.title.ilike(f'%{search_query}%')) |
            (Transaction.description.ilike(f'%{search_query}%')) |
            (Transaction.payment_method.ilike(f'%{search_query}%'))
        )

    if category_filter and category_filter.isdigit():
        filter_query = filter_query.filter(Transaction.category_id == int(category_filter))

    if month_filter and month_filter != 'all':
        try:
            m_dt = datetime.strptime(month_filter, '%Y-%m')
            start_d = m_dt.date().replace(day=1)
            next_m = (start_d.replace(day=28) + timedelta(days=4)).replace(day=1)
            end_d = next_m - timedelta(days=1)
            filter_query = filter_query.filter(Transaction.date >= start_d, Transaction.date <= end_d)
        except ValueError:
            pass

    # Sorting
    if sort_by == 'date_asc':
        filter_query = filter_query.order_by(Transaction.date.asc(), Transaction.id.asc())
    elif sort_by == 'amount_desc':
        filter_query = filter_query.order_by(Transaction.amount.desc())
    elif sort_by == 'amount_asc':
        filter_query = filter_query.order_by(Transaction.amount.asc())
    else:
        filter_query = filter_query.order_by(Transaction.date.desc(), Transaction.id.desc())

    # Pagination
    pagination = filter_query.paginate(page=page, per_page=per_page, error_out=False)
    expense_transactions = pagination.items

    filtered_total = sum(t.amount for t in filter_query.all())
    filtered_count = filter_query.count()

    today_str = today.strftime('%Y-%m-%d')

    return render_template(
        'expenses/index.html',
        expense_transactions=expense_transactions,
        pagination=pagination,
        expense_categories=expense_categories,
        current_month_expenses=current_month_expenses,
        ytd_expenses=ytd_expenses,
        all_time_expenses=all_time_expenses,
        avg_daily_spend=avg_daily_spend,
        highest_tx=highest_tx,
        expense_breakdown=expense_breakdown,
        available_months=available_months,
        monthly_trends=monthly_trends,
        search_query=search_query,
        category_filter=category_filter,
        month_filter=month_filter,
        sort_by=sort_by,
        filtered_total=filtered_total,
        filtered_count=filtered_count,
        today_str=today_str
    )
