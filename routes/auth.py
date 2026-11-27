import re
from urllib.parse import urlparse, urljoin
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from utils import seed_default_categories, seed_demo_user

auth_bp = Blueprint('auth', __name__)

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

def is_safe_url(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        action = request.form.get('action')
        
        # Quick Demo Account login
        if action == 'demo_login':
            demo_user = seed_demo_user()
            login_user(demo_user, remember=True)
            flash('Logged in as Demo User with realistic portfolio data.', 'success')
            return redirect(url_for('dashboard.index'))

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        if not email or not password:
            flash('Please provide both email address and password.', 'warning')
            return render_template('auth/login.html')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid email address or password. Please try again.', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        currency = request.form.get('currency', 'INR')

        if not name or not email or not password:
            flash('All required fields must be filled.', 'danger')
            return render_template('auth/register.html')

        if not EMAIL_REGEX.match(email):
            flash('Please enter a valid email address.', 'warning')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match. Please verify.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/register.html')

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('An account with this email already exists. Please log in.', 'warning')
            return redirect(url_for('auth.login'))

        symbols = {'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£'}
        new_user = User(
            name=name,
            email=email,
            currency=currency,
            currency_symbol=symbols.get(currency, '₹')
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        # Seed initial categories for new user
        seed_default_categories(new_user.id)

        login_user(new_user)
        flash('Account successfully created! Welcome to FINORA.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been securely logged out.', 'info')
    return redirect(url_for('auth.login'))
