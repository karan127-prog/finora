from datetime import date
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, Notification, Transaction, Category
from utils import calculate_dashboard_metrics, sync_smart_notifications

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/notifications')
@login_required
def get_notifications():
    # Sync live notifications from real financial data
    sync_smart_notifications(current_user.id)

    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).limit(15).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()

    return jsonify({
        'unread_count': unread_count,
        'notifications': [n.to_dict() for n in notifications]
    })

@api_bp.route('/api/notifications/mark-read/<int:id>', methods=['POST'])
@login_required
def mark_read(id):
    notif = Notification.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/api/notifications/delete/<int:id>', methods=['POST'])
@login_required
def delete_notification(id):
    notif = Notification.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(notif)
    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/api/chart-data')
@login_required
def chart_data():
    """Return JSON data for dynamic Chart.js rendering."""
    view_type = request.args.get('view', 'monthly')  # 'monthly' or 'yearly'
    today = date.today()

    labels = []
    income_points = []
    expense_points = []

    if view_type == 'yearly':
        # Last 4 years
        for yr in range(today.year - 3, today.year + 1):
            labels.append(str(yr))
            txs = Transaction.query.filter(
                Transaction.user_id == current_user.id
            ).all()
            inc = sum(t.amount for t in txs if t.date.year == yr and t.type == 'income')
            exp = sum(t.amount for t in txs if t.date.year == yr and t.type == 'expense')
            income_points.append(inc)
            expense_points.append(exp)
    else:
        # Last 6 months
        for i in range(5, -1, -1):
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            m_str = f"{year:04d}-{month:02d}"
            labels.append(date(year, month, 1).strftime('%b %Y'))

            txs = Transaction.query.filter(
                Transaction.user_id == current_user.id
            ).all()
            inc = sum(t.amount for t in txs if t.date.strftime('%Y-%m') == m_str and t.type == 'income')
            exp = sum(t.amount for t in txs if t.date.strftime('%Y-%m') == m_str and t.type == 'expense')
            income_points.append(inc)
            expense_points.append(exp)

    # Category breakdown for current month
    metrics = calculate_dashboard_metrics(current_user.id)

    cat_labels = [c['name'] for c in metrics['category_breakdown']]
    cat_values = [c['amount'] for c in metrics['category_breakdown']]

    return jsonify({
        'overview': {
            'labels': labels,
            'income': income_points,
            'expense': expense_points
        },
        'categories': {
            'labels': cat_labels,
            'data': cat_values
        }
    })
