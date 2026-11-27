import os
from flask import Flask
from flask_login import LoginManager
from config import Config
from models import db, User
from routes import register_blueprints
from utils import seed_default_categories, seed_demo_user

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'
    login_manager.init_app(app)

    # Session & Cookie Security
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config.setdefault('REMEMBER_COOKIE_HTTPONLY', True)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register all routes
    register_blueprints(app)

    @app.context_processor
    def inject_global_data():
        from datetime import date
        from flask_login import current_user
        from models import Category

        if current_user.is_authenticated:
            income_cats = Category.query.filter(
                (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
                Category.type == 'income'
            ).order_by(Category.name.asc()).all()

            expense_cats = Category.query.filter(
                (Category.user_id == current_user.id) | (Category.user_id.is_(None)),
                Category.type == 'expense'
            ).order_by(Category.name.asc()).all()
        else:
            income_cats = []
            expense_cats = []

        return {
            'income_categories': income_cats,
            'expense_categories': expense_cats,
            'today_str': date.today().strftime('%Y-%m-%d'),
            'current_date_display': date.today().strftime('%A, %d %B %Y')
        }

    # Initialize tables and seed demo user on first run
    with app.app_context():
        db.create_all()
        # Seed default categories
        seed_default_categories()
        # Seed rich demo user
        seed_demo_user()

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("\n* FINORA Server running!")
    print(f"* Local PC access:     http://127.0.0.1:{port}")
    print(f"* Phone/Mobile access:  http://192.168.1.2:{port} (connected to same Wi-Fi)\n")
    app.run(host='0.0.0.0', port=port, debug=False)
