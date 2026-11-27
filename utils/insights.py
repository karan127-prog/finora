from datetime import date, timedelta, datetime
from calendar import monthrange
from sqlalchemy import func
from models import db, Transaction, Budget, Category, SavingsGoal, RecurringTransaction, Notification

def calculate_dashboard_metrics(user_id):
    """
    Compute real-time financial KPI cards and smart insights for the user.
    Never hardcoded. Always computed from actual database records.
    """
    today = date.today()
    current_year = today.year
    current_month = today.month
    current_month_str = today.strftime('%Y-%m')

    # Previous month computation
    first_of_curr = today.replace(day=1)
    prev_month_date = first_of_curr - timedelta(days=1)
    prev_year = prev_month_date.year
    prev_month = prev_month_date.month

    # Current month Income & Expense
    curr_txs = Transaction.query.filter(
        Transaction.user_id == user_id,
        func.strftime('%Y-%m', Transaction.date) == current_month_str
    ).all() if 'sqlite' in db.engine.url.drivername else Transaction.query.filter(
        Transaction.user_id == user_id,
        func.extract('year', Transaction.date) == current_year,
        func.extract('month', Transaction.date) == current_month
    ).all()

    total_income = sum(t.amount for t in curr_txs if t.type == 'income')
    total_expenses = sum(t.amount for t in curr_txs if t.type == 'expense')
    net_balance = total_income - total_expenses
    total_savings = max(0.0, net_balance)

    # Previous month Income & Expense for percentage comparison
    prev_txs = Transaction.query.filter(
        Transaction.user_id == user_id,
        func.strftime('%Y-%m', Transaction.date) == prev_month_date.strftime('%Y-%m')
    ).all() if 'sqlite' in db.engine.url.drivername else Transaction.query.filter(
        Transaction.user_id == user_id,
        func.extract('year', Transaction.date) == prev_year,
        func.extract('month', Transaction.date) == prev_month
    ).all()

    prev_income = sum(t.amount for t in prev_txs if t.type == 'income')
    prev_expenses = sum(t.amount for t in prev_txs if t.type == 'expense')
    prev_savings = max(0.0, prev_income - prev_expenses)

    def calc_pct_change(curr, prev):
        if prev == 0:
            return 100.0 if curr > 0 else 0.0
        change = ((curr - prev) / prev) * 100
        return round(change, 1)

    income_pct_change = calc_pct_change(total_income, prev_income)
    expense_pct_change = calc_pct_change(total_expenses, prev_expenses)
    savings_pct_change = calc_pct_change(total_savings, prev_savings)
    balance_pct_change = calc_pct_change(net_balance, prev_income - prev_expenses)

    # Expense Category Breakdown
    cat_spending = {}
    for t in curr_txs:
        if t.type == 'expense':
            cat_name = t.category_name
            cat_spending[cat_name] = cat_spending.get(cat_name, 0.0) + t.amount

    category_breakdown = []
    highest_expense_cat = None
    highest_expense_amt = 0.0

    for cat_name, amt in sorted(cat_spending.items(), key=lambda x: x[1], reverse=True):
        pct = round((amt / total_expenses * 100), 1) if total_expenses > 0 else 0
        if amt > highest_expense_amt:
            highest_expense_amt = amt
            highest_expense_cat = cat_name
        category_breakdown.append({
            'name': cat_name,
            'amount': amt,
            'percentage': pct
        })

    # Overall Budget calculation
    budgets = Budget.query.filter_by(user_id=user_id, month=current_month_str).all()
    total_budget_limit = sum(b.limit_amount for b in budgets)
    budget_spent = 0.0
    budget_details = []

    for b in budgets:
        cat_spent = cat_spending.get(b.category_rel.name if b.category_rel else '', 0.0)
        budget_spent += cat_spent
        rem = b.limit_amount - cat_spent
        pct = round((cat_spent / b.limit_amount * 100), 1) if b.limit_amount > 0 else 0
        
        status = 'safe'
        if pct >= 100:
            status = 'exceeded'
        elif pct >= 90:
            status = 'critical'
        elif pct >= 70:
            status = 'warning'

        budget_details.append({
            'category_id': b.category_id,
            'category_name': b.category_rel.name if b.category_rel else 'General',
            'category_icon': b.category_rel.icon if b.category_rel else 'tag',
            'limit': b.limit_amount,
            'spent': cat_spent,
            'remaining': rem,
            'percentage': pct,
            'status': status
        })

    remaining_budget = max(0.0, total_budget_limit - budget_spent)
    overall_budget_pct = round((budget_spent / total_budget_limit * 100), 1) if total_budget_limit > 0 else 0

    # Savings Rate %
    savings_rate = round((total_savings / total_income * 100), 1) if total_income > 0 else 0.0

    # Average Daily Spending
    days_in_month = today.day
    avg_daily_spend = round((total_expenses / max(1, days_in_month)), 1)

    # Smart Insights generation from real data
    insights = []
    if highest_expense_cat and total_expenses > 0:
        high_pct = round((highest_expense_amt / total_expenses * 100), 1)
        insights.append({
            'icon': 'alert-circle',
            'type': 'warning' if high_pct > 35 else 'info',
            'title': 'Highest Spending Category',
            'text': f'{highest_expense_cat} accounts for {high_pct}% (₹{highest_expense_amt:,.2f}) of your total monthly expenses.'
        })

    if savings_rate >= 20:
        insights.append({
            'icon': 'check-circle-2',
            'type': 'success',
            'title': 'Healthy Savings Rate',
            'text': f'Your monthly savings rate is {savings_rate}%, well in line with recommended 50/30/20 financial guidelines.'
        })
    elif total_income > 0:
        insights.append({
            'icon': 'alert-triangle',
            'type': 'warning',
            'title': 'Low Savings Buffer',
            'text': f'Your current savings rate is {savings_rate}%. Consider reviewing discretionary shopping and entertainment.'
        })

    # Alert for any budget nearing or over limit
    over_budgets = [b for b in budget_details if b['status'] in ('warning', 'critical', 'exceeded')]
    if over_budgets:
        top_over = over_budgets[0]
        insights.append({
            'icon': 'trending-up',
            'type': 'danger' if top_over['status'] == 'exceeded' else 'warning',
            'title': f"{top_over['category_name']} Budget Alert",
            'text': f"You have spent {top_over['percentage']}% of your {top_over['category_name']} budget (₹{top_over['spent']:,.2f} of ₹{top_over['limit']:,.2f})."
        })

    return {
        'total_balance': net_balance,
        'balance_pct_change': balance_pct_change,
        'total_income': total_income,
        'income_pct_change': income_pct_change,
        'total_expenses': total_expenses,
        'expense_pct_change': expense_pct_change,
        'total_savings': total_savings,
        'savings_pct_change': savings_pct_change,
        'savings_rate': savings_rate,
        'avg_daily_spend': avg_daily_spend,
        'category_breakdown': category_breakdown,
        'total_budget_limit': total_budget_limit,
        'budget_spent': budget_spent,
        'remaining_budget': remaining_budget,
        'overall_budget_pct': overall_budget_pct,
        'budget_details': budget_details,
        'insights': insights
    }

def sync_smart_notifications(user_id):
    """
    Evaluates real user financial data and generates in-app notifications
    for budget overages, upcoming bills, high spending velocity, and savings improvements.
    Includes time-window deduplication to avoid repetitive alert spam.
    """
    today = date.today()
    current_month_str = today.strftime('%Y-%m')
    now = datetime.utcnow()

    def has_recent_notification(title_prefix, days_window=3):
        cutoff = now - timedelta(days=days_window)
        return Notification.query.filter(
            Notification.user_id == user_id,
            Notification.title.like(f"{title_prefix}%"),
            Notification.created_at >= cutoff
        ).first() is not None

    new_count = 0

    # 1. Upcoming Recurring Payments & Due Bills in the next 3 days
    three_days_out = today + timedelta(days=3)
    due_bills = RecurringTransaction.query.filter(
        RecurringTransaction.user_id == user_id,
        RecurringTransaction.is_active == True,
        RecurringTransaction.next_date >= today,
        RecurringTransaction.next_date <= three_days_out
    ).all()

    for bill in due_bills:
        days_left = (bill.next_date - today).days
        due_text = "today" if days_left == 0 else ("tomorrow" if days_left == 1 else f"in {days_left} days")
        notif_title = f"Upcoming Bill: {bill.title}"
        if not has_recent_notification(notif_title, days_window=3):
            n = Notification(
                user_id=user_id,
                title=notif_title,
                message=f"Your {bill.frequency} payment of ₹{bill.amount:,.2f} for '{bill.title}' is due {due_text} ({bill.next_date.strftime('%d-%b')}).",
                type='info'
            )
            db.session.add(n)
            new_count += 1

    # 2. Overdue Recurring Bills (next_date < today)
    overdue_bills = RecurringTransaction.query.filter(
        RecurringTransaction.user_id == user_id,
        RecurringTransaction.is_active == True,
        RecurringTransaction.next_date < today
    ).all()

    for bill in overdue_bills:
        days_over = (today - bill.next_date).days
        notif_title = f"Overdue Payment: {bill.title}"
        if not has_recent_notification(notif_title, days_window=2):
            n = Notification(
                user_id=user_id,
                title=notif_title,
                message=f"'{bill.title}' (₹{bill.amount:,.2f}) was due {days_over} day(s) ago on {bill.next_date.strftime('%d-%b')}. Click 'Execute Due Payments' on Recurring page.",
                type='warning'
            )
            db.session.add(n)
            new_count += 1

    # 3. Budget Limits (70% approaching, 90% critical, 100%+ exceeded)
    budgets = Budget.query.filter_by(user_id=user_id, month=current_month_str).all()
    for b in budgets:
        cat_name = b.category_rel.name if b.category_rel else 'General'
        cat_txs = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.category_id == b.category_id,
            Transaction.type == 'expense',
            func.strftime('%Y-%m', Transaction.date) == current_month_str if 'sqlite' in db.engine.url.drivername else (
                (func.extract('year', Transaction.date) == today.year) & (func.extract('month', Transaction.date) == today.month)
            )
        ).all()
        cat_spent = sum(t.amount for t in cat_txs)
        pct = round((cat_spent / b.limit_amount * 100), 1) if b.limit_amount > 0 else 0

        if pct >= 100:
            notif_title = f"Budget Exceeded: {cat_name}"
            if not has_recent_notification(notif_title, days_window=5):
                n = Notification(
                    user_id=user_id,
                    title=notif_title,
                    message=f"You have exceeded your {cat_name} budget! Spent ₹{cat_spent:,.2f} of ₹{b.limit_amount:,.2f} ({pct}%).",
                    type='danger'
                )
                db.session.add(n)
                new_count += 1
        elif pct >= 90:
            notif_title = f"Critical Budget Alert: {cat_name}"
            if not has_recent_notification(notif_title, days_window=4):
                n = Notification(
                    user_id=user_id,
                    title=notif_title,
                    message=f"Critical alert: You have reached {pct}% of your {cat_name} budget (₹{cat_spent:,.2f} of ₹{b.limit_amount:,.2f}).",
                    type='warning'
                )
                db.session.add(n)
                new_count += 1
        elif pct >= 70:
            notif_title = f"Budget Alert: {cat_name}"
            if not has_recent_notification(notif_title, days_window=4):
                n = Notification(
                    user_id=user_id,
                    title=notif_title,
                    message=f"You have used {pct}% of your {cat_name} budget (₹{cat_spent:,.2f} of ₹{b.limit_amount:,.2f}).",
                    type='warning'
                )
                db.session.add(n)
                new_count += 1

    # 4. Spending Velocity Alert (>15% increase compared to previous month)
    metrics = calculate_dashboard_metrics(user_id)
    if metrics['expense_pct_change'] >= 15.0 and metrics['total_expenses'] > 0:
        notif_title = "Monthly Outflow Surge"
        if not has_recent_notification(notif_title, days_window=10):
            n = Notification(
                user_id=user_id,
                title=notif_title,
                message=f"Your expenses increased by {metrics['expense_pct_change']}% this month compared to last month. Total spent: ₹{metrics['total_expenses']:,.2f}.",
                type='warning'
            )
            db.session.add(n)
            new_count += 1

    # 5. Month-over-Month Savings Milestone
    prev_first = today.replace(day=1) - timedelta(days=1)
    prev_month_str = prev_first.strftime('%Y-%m')
    prev_txs = Transaction.query.filter(
        Transaction.user_id == user_id,
        func.strftime('%Y-%m', Transaction.date) == prev_month_str if 'sqlite' in db.engine.url.drivername else (
            (func.extract('year', Transaction.date) == prev_first.year) & (func.extract('month', Transaction.date) == prev_first.month)
        )
    ).all()
    prev_inc = sum(t.amount for t in prev_txs if t.type == 'income')
    prev_exp = sum(t.amount for t in prev_txs if t.type == 'expense')
    prev_savings = max(0.0, prev_inc - prev_exp)
    curr_savings = metrics['total_savings']

    if curr_savings > prev_savings and prev_savings > 0 and (curr_savings - prev_savings) >= 500:
        saved_more = curr_savings - prev_savings
        notif_title = "Savings Growth Milestone"
        if not has_recent_notification(notif_title, days_window=14):
            n = Notification(
                user_id=user_id,
                title=notif_title,
                message=f"Excellent discipline! You saved ₹{saved_more:,.2f} more than last month. Total retained: ₹{curr_savings:,.2f}.",
                type='success'
            )
            db.session.add(n)
            new_count += 1

    if new_count > 0:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return new_count
