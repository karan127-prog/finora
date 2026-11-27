from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import db, Transaction, Category

income_bp = Blueprint('income', __name__)

@income_bp.route('/income')
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

    # Fetch all income categories for this user (including default)
    income_categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        Category.type == 'income'
    ).order_by(Category.name.asc()).all()

    # Base query for all user income transactions (used for overall metrics)
    all_income_query = Transaction.query.filter_by(
        user_id=current_user.id,
        type='income'
    )
    all_income_txs = all_income_query.order_by(Transaction.date.desc()).all()

    # Calculate overall metrics
    current_month_income = sum(t.amount for t in all_income_txs if t.date.strftime('%Y-%m') == current_month_str)
    ytd_income = sum(t.amount for t in all_income_txs if str(t.date.year) == current_year_str)
    all_time_income = sum(t.amount for t in all_income_txs)

    # Distinct active months for monthly average calculation
    distinct_months = set(t.date.strftime('%Y-%m') for t in all_income_txs)
    monthly_avg_income = (all_time_income / len(distinct_months)) if distinct_months else 0.0

    # Source breakdown (lifetime)
    source_totals = {}
    source_counts = {}
    for t in all_income_txs:
        cat_name = t.category_name
        source_totals[cat_name] = source_totals.get(cat_name, 0.0) + t.amount
        source_counts[cat_name] = source_counts.get(cat_name, 0) + 1

    top_source = max(source_totals.items(), key=lambda x: x[1]) if source_totals else ('None', 0.0)
    top_source_pct = round((top_source[1] / all_time_income * 100), 1) if all_time_income > 0 else 0.0

    # Category meta map for icons and colors
    cat_meta_map = {c.name: {'icon': c.icon, 'color': c.color, 'id': c.id} for c in income_categories}

    source_breakdown = []
    for cat_name, amt in sorted(source_totals.items(), key=lambda x: x[1], reverse=True):
        pct = round((amt / all_time_income * 100), 1) if all_time_income > 0 else 0
        meta = cat_meta_map.get(cat_name, {'icon': 'briefcase', 'color': '#789BB8', 'id': None})
        source_breakdown.append({
            'name': cat_name,
            'amount': amt,
            'percentage': pct,
            'count': source_counts.get(cat_name, 0),
            'icon': meta['icon'],
            'color': meta['color'],
            'id': meta['id']
        })

    # Available months for dropdown filter
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
        m_sum = sum(t.amount for t in all_income_txs if t.date.strftime('%Y-%m') == m_str)
        monthly_trends.append({'label': m_label, 'month': m_str, 'amount': m_sum})

    # Filtered Query for the ledger table
    filter_query = Transaction.query.filter_by(user_id=current_user.id, type='income')

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
    income_transactions = pagination.items

    filtered_total = sum(t.amount for t in filter_query.all())
    filtered_count = filter_query.count()

    today_str = today.strftime('%Y-%m-%d')

    return render_template(
        'income/index.html',
        income_transactions=income_transactions,
        pagination=pagination,
        income_categories=income_categories,
        current_month_income=current_month_income,
        ytd_income=ytd_income,
        all_time_income=all_time_income,
        monthly_avg_income=monthly_avg_income,
        top_source_name=top_source[0],
        top_source_amount=top_source[1],
        top_source_pct=top_source_pct,
        source_breakdown=source_breakdown,
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
