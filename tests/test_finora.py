import unittest
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from models import db, User, Transaction, Category, Budget, SavingsGoal, RecurringTransaction

class FinoraFullIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        db.session.remove()
        self.app_context.pop()

    def test_database_initialization(self):
        user_count = User.query.count()
        cat_count = Category.query.count()

        self.assertGreaterEqual(user_count, 1, "Demo user must exist")
        self.assertGreaterEqual(cat_count, 10, "Categories must be seeded")

    def test_demo_login_and_all_routes(self):
        # Test login page
        res_login = self.client.get('/login')
        self.assertEqual(res_login.status_code, 200)

        # Perform demo login
        res_post_login = self.client.post('/login', data={'action': 'demo_login'}, follow_redirects=True)
        self.assertEqual(res_post_login.status_code, 200)

        # Test all authenticated application routes
        routes_to_test = [
            ('/dashboard', 200),
            ('/transactions', 200),
            ('/income', 200),
            ('/expenses', 200),
            ('/budgets', 200),
            ('/savings', 200),
            ('/analytics', 200),
            ('/recurring', 200),
            ('/calendar', 200),
            ('/reports', 200),
            ('/settings', 200),
            ('/api/chart-data', 200),
            ('/api/notifications', 200),
            ('/reports/export/pdf', 200),
            ('/reports/export/csv', 200),
        ]

        for route, expected_status in routes_to_test:
            with self.subTest(route=route):
                r = self.client.get(route)
                self.assertEqual(r.status_code, expected_status, f"Route {route} failed with {r.status_code}")

if __name__ == '__main__':
    unittest.main()
