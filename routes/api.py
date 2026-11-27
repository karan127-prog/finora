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

@api_bp.route('/api/transactions/quick-add-detected', methods=['POST'])
def quick_add_detected():
    """
    Endpoint called directly by Android PaymentNotificationListener or 1-tap notification action
    when a payment notification from GPay, PhonePe, Paytm, or bank SMS is captured.
    Works seamlessly whether session cookie is attached or directly for the primary user.
    """
    target_user = None
    if current_user.is_authenticated:
        target_user = current_user
    else:
        # Fallback to the primary active user for background headless Android sync
        target_user = User.query.order_by(User.id.asc()).first()

    if not target_user:
        return jsonify({'success': False, 'error': 'No active user found'}), 400

    data = request.get_json(silent=True) or request.form
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid amount'}), 400

    if amount <= 0:
        return jsonify({'success': False, 'error': 'Amount must be greater than zero'}), 400

    payee = str(data.get('payee', 'UPI Payment')).strip()
    payment_method = str(data.get('payment_method', 'UPI')).strip()
    source_app = str(data.get('source_app', 'Payment App')).strip()

    # Smart Auto-Categorization based on payee keyword
    payee_lower = payee.lower()
    suggested_category_name = "Miscellaneous"

    food_keywords = ['swiggy', 'zomato', 'restaurant', 'cafe', 'mcdonald', 'kfc', 'dominos', 'burger', 'starbucks', 'tea', 'dhaba', 'pizza', 'food']
    transport_keywords = ['uber', 'ola', 'rapido', 'metro', 'fuel', 'petrol', 'diesel', 'indian oil', 'hp petrol', 'bharat petroleum', 'fastag', 'toll', 'parking']
    groceries_keywords = ['blinkit', 'zepto', 'instamart', 'supermarket', 'mart', 'grocer', 'bigbasket', 'dmart', 'kirana', 'milk', 'vegetable']
    shopping_keywords = ['amazon', 'flipkart', 'myntra', 'nykaa', 'zara', 'h&m', 'meesho', 'ajio', 'croma', 'reliance']
    utilities_keywords = ['airtel', 'jio', 'vi', 'vodafone', 'electricity', 'bescom', 'tata play', 'dish', 'broadband', 'wifi', 'bill']
    entertainment_keywords = ['netflix', 'spotify', 'hotstar', 'prime', 'pvr', 'inox', 'movie', 'bookmyshow', 'youtube', 'gaming']

    if any(k in payee_lower for k in food_keywords):
        suggested_category_name = "Food & Dining"
    elif any(k in payee_lower for k in transport_keywords):
        suggested_category_name = "Transportation"
    elif any(k in payee_lower for k in groceries_keywords):
        suggested_category_name = "Groceries"
    elif any(k in payee_lower for k in shopping_keywords):
        suggested_category_name = "Shopping"
    elif any(k in payee_lower for k in utilities_keywords):
        suggested_category_name = "Utilities"
    elif any(k in payee_lower for k in entertainment_keywords):
        suggested_category_name = "Entertainment"

    # Find matching category for target_user or default
    category = Category.query.filter(
        (Category.user_id == target_user.id) | (Category.user_id.is_(None)),
        Category.type == 'expense',
        Category.name.ilike(f"%{suggested_category_name}%")
    ).first()

    if not category:
        category = Category.query.filter(
            (Category.user_id == target_user.id) | (Category.user_id.is_(None)),
            Category.type == 'expense'
        ).first()

    category_id = category.id if category else None

    # Check for duplicate transaction within today (same amount & payee)
    recent_dup = Transaction.query.filter(
        Transaction.user_id == target_user.id,
        Transaction.amount == amount,
        Transaction.title == payee,
        Transaction.date == date.today()
    ).first()

    if recent_dup:
        return jsonify({'success': True, 'message': 'Payment already recorded', 'transaction_id': recent_dup.id})

    # Create new Transaction
    tx = Transaction(
        user_id=target_user.id,
        title=payee,
        amount=amount,
        type='expense',
        category_id=category_id,
        date=date.today(),
        payment_method=payment_method,
        description=f"Auto-captured via {source_app} payment notification"
    )
    db.session.add(tx)

    # In-app notification confirming capture
    capture_notif = Notification(
        user_id=target_user.id,
        title=f"Captured: ₹{amount:,.2f} at {payee}",
        message=f"Automatically recorded from {source_app} to {category.name if category else 'Expenses'}.",
        type='success',
        link='/transactions'
    )
    db.session.add(capture_notif)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f"Recorded ₹{amount:,.2f} to {payee}",
        'transaction_id': tx.id,
        'category': category.name if category else 'Expense'
    })
