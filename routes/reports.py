from datetime import datetime, date
from flask import Blueprint, render_template, request, make_response, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from models import Transaction, Category
from utils import calculate_dashboard_metrics, generate_financial_pdf_report, generate_transactions_csv
import io

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
@login_required
def index():
    today = date.today()
    start_date = request.args.get('start_date', today.replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    tx_type = request.args.get('type', 'all')
    category_id = request.args.get('category_id', '')

    query = Transaction.query.filter_by(user_id=current_user.id)

    # Date range filters
    try:
        sd = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(Transaction.date >= sd)
    except ValueError:
        pass

    try:
        ed = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(Transaction.date <= ed)
    except ValueError:
        pass

    # Type filter
    if tx_type in ('income', 'expense'):
        query = query.filter(Transaction.type == tx_type)

    # Category filter
    if category_id and category_id.isdigit():
        query = query.filter(Transaction.category_id == int(category_id))

    transactions = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
    metrics = calculate_dashboard_metrics(current_user.id)

    total_income = sum(t.amount for t in transactions if t.type == 'income')
    total_expenses = sum(t.amount for t in transactions if t.type == 'expense')
    net_savings = total_income - total_expenses
    savings_rate = round((net_savings / total_income * 100), 1) if total_income > 0 else 0

    # Category distribution for statement preview
    cat_breakdown = {}
    for t in transactions:
        if t.type == 'expense':
            cat_breakdown[t.category_name] = cat_breakdown.get(t.category_name, 0.0) + t.amount

    category_summary = []
    for c_name, amt in sorted(cat_breakdown.items(), key=lambda x: x[1], reverse=True):
        pct = round((amt / total_expenses * 100), 1) if total_expenses > 0 else 0
        category_summary.append({'name': c_name, 'amount': amt, 'percentage': pct})

    # Categories for filter dropdown
    categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None))
    ).order_by(Category.name.asc()).all()

    return render_template(
        'reports/index.html',
        transactions=transactions,
        metrics=metrics,
        start_date=start_date,
        end_date=end_date,
        tx_type=tx_type,
        category_id=category_id,
        categories=categories,
        total_income=total_income,
        total_expenses=total_expenses,
        net_savings=net_savings,
        savings_rate=savings_rate,
        category_summary=category_summary
    )

@reports_bp.route('/reports/export/pdf')
@login_required
def export_pdf():
    today = date.today()
    start_date = request.args.get('start_date', today.replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    tx_type = request.args.get('type', 'all')
    category_id = request.args.get('category_id', '')

    query = Transaction.query.filter_by(user_id=current_user.id)
    if start_date:
        try:
            query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        except ValueError:
            pass
    if end_date:
        try:
            query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        except ValueError:
            pass

    if tx_type in ('income', 'expense'):
        query = query.filter(Transaction.type == tx_type)

    if category_id and category_id.isdigit():
        query = query.filter(Transaction.category_id == int(category_id))

    transactions = query.order_by(Transaction.date.desc()).all()
    metrics = calculate_dashboard_metrics(current_user.id)

    pdf_bytes = generate_financial_pdf_report(
        user=current_user,
        transactions=transactions,
        metrics=metrics,
        date_range_label=f"{start_date} to {end_date}"
    )

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Finora_Statement_{start_date}_to_{end_date}.pdf'
    return response

@reports_bp.route('/reports/export/csv')
@login_required
def export_csv():
    today = date.today()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    tx_type = request.args.get('type', 'all')
    category_id = request.args.get('category_id', '')

    query = Transaction.query.filter_by(user_id=current_user.id)
    if start_date:
        try:
            query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        except ValueError:
            pass
    if end_date:
        try:
            query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
        except ValueError:
            pass

    if tx_type in ('income', 'expense'):
        query = query.filter(Transaction.type == tx_type)

    if category_id and category_id.isdigit():
        query = query.filter(Transaction.category_id == int(category_id))

    transactions = query.order_by(Transaction.date.desc()).all()
    csv_data = generate_transactions_csv(transactions, currency_symbol=current_user.currency_symbol or '₹')

    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=Finora_Ledger_{datetime.now().strftime("%Y%m%d")}.csv'
    return response
