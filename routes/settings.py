from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Transaction, Budget, SavingsGoal, RecurringTransaction, Notification
from utils import seed_default_categories, seed_demo_user

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
@login_required
def index():
    return render_template('settings/index.html', user=current_user)

@settings_bp.route('/settings/profile', methods=['POST'])
@login_required
def update_profile():
    name = request.form.get('name', '').strip()
    currency = request.form.get('currency', 'INR')
    budget_target_str = request.form.get('monthly_budget_target', '50000')

    if not name:
        flash('Name is required.', 'danger')
        return redirect(url_for('settings.index'))

    symbols = {'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£'}
    current_user.name = name
    current_user.currency = currency
    current_user.currency_symbol = symbols.get(currency, '₹')

    try:
        current_user.monthly_budget_target = float(budget_target_str)
    except ValueError:
        pass

    db.session.commit()
    flash('Profile preferences updated successfully.', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/settings/password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not current_user.check_password(current_password):
        flash('Current password verification failed.', 'danger')
        return redirect(url_for('settings.index'))

    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'danger')
        return redirect(url_for('settings.index'))

    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('settings.index'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/settings/users', methods=['GET'])
@login_required
def users():
    if current_user.email != 'karank55509@gmail.com':
        flash('Access Denied: Only master administrator (karank55509@gmail.com) can manage or delete user accounts.', 'danger')
        return redirect(url_for('settings.index'))
    all_users = User.query.order_by(User.id.asc()).all()
    return render_template('settings/users.html', users=all_users)

@settings_bp.route('/settings/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.email != 'karank55509@gmail.com':
        flash('Access Denied: Only master administrator (karank55509@gmail.com) has permission to delete user accounts.', 'danger')
        return redirect(url_for('settings.index'))

    target_user = User.query.get_or_404(user_id)
    if target_user.email == 'karank55509@gmail.com':
        flash('Action blocked: Master administrator account is permanent and cannot be deleted.', 'danger')
        return redirect(url_for('settings.users'))

    u_name = target_user.name
    u_email = target_user.email
    db.session.delete(target_user)
    db.session.commit()
    flash(f'User account "{u_name}" ({u_email}) has been permanently deleted.', 'success')
    return redirect(url_for('settings.users'))
