from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import Transaction, Category, Budget
from utils import calculate_dashboard_metrics

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics')
@login_required
def index():
    today = date.today()
    view_type = request.args.get('view', 'monthly')  # 'monthly' or 'yearly'
    selected_month = request.args.get('month', today.strftime('%Y-%m'))
    selected_year = request.args.get('year', str(today.year))

    # Parse active dates based on view_type
    if view_type == 'yearly':
        try:
            yr = int(selected_year)
        except ValueError:
            yr = today.year
            selected_year = str(yr)
        start_date = date(yr, 1, 1)
        end_date = date(yr, 12, 31)
        period_label = f"Year {selected_year}"
        
        # Previous period for YoY comparison
        prev_start = date(yr - 1, 1, 1)
        prev_end = date(yr - 1, 12, 31)
        days_in_period = 365
    else:  # 'monthly'
        try:
            cur_dt = datetime.strptime(selected_month, '%Y-%m').date()
        except ValueError:
            cur_dt = today.replace(day=1)
            selected_month = today.strftime('%Y-%m')
        
        start_date = cur_dt.replace(day=1)
        next_month_d = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month_d - timedelta(days=1)
        period_label = cur_dt.strftime('%B %Y')

        # Previous period for MoM comparison
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end.replace(day=1)
        
        # Days passed in current month for daily average
        if selected_month == today.strftime('%Y-%m'):
            days_in_period = max(1, today.day)
        else:
            days_in_period = (end_date - start_date).days + 1

    # Fetch transactions for current user in active period
    all_user_txs = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    
    period_txs = [t for t in all_user_txs if start_date <= t.date <= end_date]
    prev_txs = [t for t in all_user_txs if prev_start <= t.date <= prev_end]

    # Period Totals
    period_income = sum(t.amount for t in period_txs if t.type == 'income')
    period_expense = sum(t.amount for t in period_txs if t.type == 'expense')
    net_savings = period_income - period_expense
    savings_rate = round((net_savings / period_income * 100), 1) if period_income > 0 else 0.0

    # Daily Average Spend
    avg_daily_spend = round(period_expense / days_in_period, 1) if days_in_period > 0 else 0.0

    # Previous Period Totals for MoM / YoY Comparison
    prev_income = sum(t.amount for t in prev_txs if t.type == 'income')
    prev_expense = sum(t.amount for t in prev_txs if t.type == 'expense')
    prev_savings = prev_income - prev_expense

    def calc_change(current_val, prev_val):
        if prev_val == 0:
            return 100.0 if current_val > 0 else 0.0
        return round(((current_val - prev_val) / prev_val) * 100, 1)

    income_change_pct = calc_change(period_income, prev_income)
    expense_change_pct = calc_change(period_expense, prev_expense)
    savings_change_pct = calc_change(net_savings, prev_savings)

    # Category breakdown for period
    cat_distribution = {}
    cat_counts = {}
    for t in period_txs:
        if t.type == 'expense':
            cat_name = t.category_name
            cat_distribution[cat_name] = cat_distribution.get(cat_name, 0.0) + t.amount
            cat_counts[cat_name] = cat_counts.get(cat_name, 0) + 1

    category_chart_data = []
    for c_name, amt in sorted(cat_distribution.items(), key=lambda x: x[1], reverse=True):
        pct = round((amt / period_expense * 100), 1) if period_expense > 0 else 0
        category_chart_data.append({
            'name': c_name,
            'amount': amt,
            'percentage': pct,
            'count': cat_counts.get(c_name, 0)
        })

    # Highest spending category
    if category_chart_data:
        highest_cat = category_chart_data[0]
    else:
        highest_cat = {'name': 'None', 'amount': 0.0, 'percentage': 0.0}

    # 50/30/20 Financial Health Rule Breakdown
    # Needs: Food, Rent, Bills, Healthcare, Transportation, Education
    # Wants: Shopping, Entertainment, Travel, Subscriptions, Other Expenses
    # Savings: Net Savings (investments, cash savings)
    needs_categories = {'food', 'rent', 'bills', 'healthcare', 'transportation', 'education'}
    wants_categories = {'shopping', 'entertainment', 'travel', 'subscriptions', 'other expenses'}

    needs_spent = sum(amt for c_name, amt in cat_distribution.items() if c_name.lower() in needs_categories)
    wants_spent = sum(amt for c_name, amt in cat_distribution.items() if c_name.lower() in wants_categories)
    
    total_inflow_ref = max(period_income, period_expense)
    needs_pct = round((needs_spent / total_inflow_ref * 100), 1) if total_inflow_ref > 0 else 0.0
    wants_pct = round((wants_spent / total_inflow_ref * 100), 1) if total_inflow_ref > 0 else 0.0
    savings_pct = round((max(0.0, net_savings) / total_inflow_ref * 100), 1) if total_inflow_ref > 0 else 0.0

    # 6-Month Financial Trends
    months_trend = []
    for i in range(5, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        m_str = f"{year:04d}-{month:02d}"
        m_label = date(year, month, 1).strftime('%b %Y')

        m_inc = sum(t.amount for t in all_user_txs if t.date.strftime('%Y-%m') == m_str and t.type == 'income')
        m_exp = sum(t.amount for t in all_user_txs if t.date.strftime('%Y-%m') == m_str and t.type == 'expense')
        m_sav = max(0.0, m_inc - m_exp)

        months_trend.append({
            'label': m_label,
            'income': m_inc,
            'expense': m_exp,
            'savings': m_sav
        })

    # Available months and years for selection
    distinct_months = sorted(list(set(t.date.strftime('%Y-%m') for t in all_user_txs)), reverse=True)
    if today.strftime('%Y-%m') not in distinct_months:
        distinct_months.insert(0, today.strftime('%Y-%m'))

    distinct_years = sorted(list(set(str(t.date.year) for t in all_user_txs)), reverse=True)
    if str(today.year) not in distinct_years:
        distinct_years.insert(0, str(today.year))

    metrics = calculate_dashboard_metrics(current_user.id)

    return render_template(
        'analytics/index.html',
        metrics=metrics,
        view_type=view_type,
        selected_month=selected_month,
        selected_year=selected_year,
        period_label=period_label,
        period_income=period_income,
        period_expense=period_expense,
        net_savings=net_savings,
        savings_rate=savings_rate,
        avg_daily_spend=avg_daily_spend,
        highest_cat=highest_cat,
        income_change_pct=income_change_pct,
        expense_change_pct=expense_change_pct,
        savings_change_pct=savings_change_pct,
        category_chart_data=category_chart_data,
        months_trend=months_trend,
        distinct_months=distinct_months,
        distinct_years=distinct_years,
        needs_spent=needs_spent,
        wants_spent=wants_spent,
        needs_pct=needs_pct,
        wants_pct=wants_pct,
        savings_pct=savings_pct
    )
