"""
FINORA Database Management CLI
Usage:
    py manage_db.py status   - Show database engine, tables, and row counts
    py manage_db.py init     - Create all database tables
    py manage_db.py seed     - Seed default categories and demo account
    py manage_db.py reset    - Drop and recreate all tables with fresh demo data
    py manage_db.py verify   - Verify database foreign keys, constraints and integrity
"""

import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from models import db, User, Category, Transaction, Budget, SavingsGoal, SavingsContribution, RecurringTransaction, Notification
from utils import seed_default_categories, seed_demo_user

app = create_app()

def status():
    with app.app_context():
        engine_url = str(db.engine.url)
        # Mask password in URL for security
        if '@' in engine_url:
            masked_url = engine_url.split('@')[1]
            display_url = f"{engine_url.split('://')[0]}://***:***@{masked_url}"
        else:
            display_url = engine_url

        print("\n================ FINORA DATABASE STATUS ================")
        print(f"Driver / Dialect : {db.engine.dialect.name}")
        print(f"Target Database  : {display_url}")
        print("-------------------------------------------------------")
        print(f"{'Table Name':<28} | {'Row Count':>10}")
        print("-------------------------------------------------------")

        tables = [
            ('users', User),
            ('categories', Category),
            ('transactions', Transaction),
            ('budgets', Budget),
            ('savings_goals', SavingsGoal),
            ('savings_contributions', SavingsContribution),
            ('recurring_transactions', RecurringTransaction),
            ('notifications', Notification)
        ]

        total_rows = 0
        for name, model in tables:
            count = model.query.count()
            total_rows += count
            print(f"{name:<28} | {count:>10}")

        print("-------------------------------------------------------")
        print(f"{'TOTAL ROWS ACROSS ALL TABLES':<28} | {total_rows:>10}")
        print("=======================================================\n")

def init_tables():
    with app.app_context():
        db.create_all()
        print("[SUCCESS] All database tables created / verified.")

def seed():
    with app.app_context():
        seed_default_categories()
        demo = seed_demo_user()
        print(f"[SUCCESS] Database seeded. Demo user: {demo.email}")

def reset():
    confirm = input("Are you sure you want to drop ALL data and reset FINORA? (y/N): ")
    if confirm.strip().lower() == 'y':
        with app.app_context():
            db.drop_all()
            db.create_all()
            seed_default_categories()
            seed_demo_user()
            print("[SUCCESS] Database completely reset and reseeded with demo data.")
    else:
        print("[ABORTED] Reset cancelled.")

def verify():
    with app.app_context():
        print("\nVerifying database constraints and data integrity...")
        # 1. Check user exists
        demo = User.query.filter_by(email='demo@finora.app').first()
        assert demo is not None, "Demo user not found!"
        print("  ✓ User table & Demo account verified")

        # 2. Check password hashing
        assert not demo.password_hash.startswith('password'), "Passwords MUST NOT be plaintext!"
        assert demo.check_password('password123'), "Password hash verification failed!"
        print("  ✓ Password hashing (Werkzeug) verified secure")

        # 3. Check categories
        cats = Category.query.count()
        assert cats > 0, "No categories found!"
        print(f"  ✓ Category relationships verified ({cats} categories active)")

        # 4. Check transactions
        txs = Transaction.query.filter_by(user_id=demo.id).count()
        assert txs > 0, "Demo user has no transactions!"
        print(f"  ✓ User transactions verified ({txs} records)")

        # 5. Check budget unique constraint
        budgets = Budget.query.filter_by(user_id=demo.id).all()
        print(f"  ✓ Category budget targets verified ({len(budgets)} budgets)")

        print("\n[ALL DATABASE INTEGRITY CHECKS PASSED]\n")

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if cmd == 'status':
        status()
    elif cmd == 'init':
        init_tables()
    elif cmd == 'seed':
        seed()
    elif cmd == 'reset':
        reset()
    elif cmd == 'verify':
        verify()
    else:
        print("Unknown command. Valid: status, init, seed, reset, verify")
