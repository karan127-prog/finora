import calendar
from datetime import date, datetime
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Transaction, RecurringTransaction, SavingsContribution, SavingsGoal, Category

calendar_bp = Blueprint('calendar', __name__)

@calendar_bp.route('/calendar')
@login_required
def index():
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)

    # Validate month and year boundaries
    if month < 1 or month > 12:
        month = today.month
    if year < 2000 or year > 2100:
        year = today.year

    cal = calendar.Calendar(firstweekday=6)  # Sunday start
    month_days = cal.monthdatescalendar(year, month)

    month_name = date(year, month, 1).strftime('%B %Y')

    first_date = month_days[0][0]
    last_date = month_days[-1][-1]

    # 1. Fetch transactions in this display range
    txs = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= first_date,
        Transaction.date <= last_date
    ).all()

    # 2. Fetch recurring payment schedules active in this range
    recurrings = RecurringTransaction.query.filter(
        RecurringTransaction.user_id == current_user.id,
        RecurringTransaction.is_active == True,
        RecurringTransaction.next_date >= first_date,
        RecurringTransaction.next_date <= last_date
    ).all()

    # 3. Fetch savings contributions in this range
    contributions = SavingsContribution.query.join(SavingsGoal).filter(
        SavingsGoal.user_id == current_user.id,
        SavingsContribution.date >= first_date,
        SavingsContribution.date <= last_date
    ).all()

    # 4. Fetch user categories for quick transaction creation from calendar modal
    categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None))
    ).order_by(Category.name.asc()).all()

    # Group by date string YYYY-MM-DD
    events_by_date = {}
    for d_list in month_days:
        for d in d_list:
            d_key = d.strftime('%Y-%m-%d')
            events_by_date[d_key] = {
                'income_sum': 0.0,
                'expense_sum': 0.0,
                'savings_sum': 0.0,
                'transactions': [],
                'recurring': [],
                'savings': []
            }

    for t in txs:
        d_key = t.date.strftime('%Y-%m-%d')
        if d_key in events_by_date:
            if t.type == 'income':
                events_by_date[d_key]['income_sum'] += t.amount
            else:
                events_by_date[d_key]['expense_sum'] += t.amount
            events_by_date[d_key]['transactions'].append(t)

    for r in recurrings:
        d_key = r.next_date.strftime('%Y-%m-%d')
        if d_key in events_by_date:
            events_by_date[d_key]['recurring'].append(r)

    for c in contributions:
        d_key = c.date.strftime('%Y-%m-%d')
        if d_key in events_by_date:
            events_by_date[d_key]['savings_sum'] += c.amount
            events_by_date[d_key]['savings'].append({
                'goal_name': c.goal.name if c.goal else 'Savings Target',
                'amount': c.amount,
                'notes': c.notes or ''
            })

    # Prev and Next month navigation
    prev_month = 12 if month == 1 else month - 1
    prev_year = year - 1 if month == 1 else year

    next_month = 1 if month == 12 else month + 1
    next_year = year + 1 if month == 12 else year

    return render_template(
        'calendar/index.html',
        month_days=month_days,
        events_by_date=events_by_date,
        current_year=year,
        current_month=month,
        month_name=month_name,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        categories=categories
    )
