from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Transaction, Budget, SavingsGoal, Category
from utils import calculate_dashboard_metrics, sync_smart_notifications

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Sync smart notifications and insights from real activity
    sync_smart_notifications(current_user.id)

    metrics = calculate_dashboard_metrics(current_user.id)
    
    # Recent 6 transactions
    recent_transactions = Transaction.query.filter_by(user_id=current_user.id)\
        .order_by(Transaction.date.desc(), Transaction.id.desc()).limit(6).all()

    # Active savings goals
    savings_goals = SavingsGoal.query.filter_by(user_id=current_user.id, status='in_progress')\
        .order_by(SavingsGoal.target_date.asc()).limit(4).all()

    # Categories for quick add modals
    income_categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        Category.type == 'income'
    ).order_by(Category.name.asc()).all()

    expense_categories = Category.query.filter(
        (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
        Category.type == 'expense'
    ).order_by(Category.name.asc()).all()

    today_str = date.today().strftime('%Y-%m-%d')
    current_date_display = date.today().strftime('%A, %d %B %Y')

    return render_template(
        'dashboard/index.html',
        metrics=metrics,
        recent_transactions=recent_transactions,
        savings_goals=savings_goals,
        income_categories=income_categories,
        expense_categories=expense_categories,
        today_str=today_str,
        current_date_display=current_date_display
    )
