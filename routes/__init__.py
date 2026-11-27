from .auth import auth_bp
from .dashboard import dashboard_bp
from .transactions import transactions_bp
from .income import income_bp
from .expenses import expenses_bp
from .budgets import budgets_bp
from .savings import savings_bp
from .analytics import analytics_bp
from .recurring import recurring_bp
from .calendar import calendar_bp
from .reports import reports_bp
from .settings import settings_bp
from .api import api_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(income_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(budgets_bp)
    app.register_blueprint(savings_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(recurring_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(api_bp)
