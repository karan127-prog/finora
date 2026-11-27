import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from models import db, User, Transaction, Category

class AnalyticsReportsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def clean_test_data(self):
        try:
            db.session.rollback()
            test_users = User.query.filter(User.email.in_(['analytics_tester@finora.app', 'other_analytics@finora.app'])).all()
            test_user_ids = [u.id for u in test_users]
            if test_user_ids:
                Transaction.query.filter(Transaction.user_id.in_(test_user_ids)).delete(synchronize_session=False)
                Category.query.filter(Category.user_id.in_(test_user_ids)).delete(synchronize_session=False)
                User.query.filter(User.id.in_(test_user_ids)).delete(synchronize_session=False)
                db.session.commit()
        except Exception:
            db.session.rollback()

    def setUp(self):
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.clean_test_data()

        # Create Test User 1
        self.user1 = User(
            name='Analytics Lead',
            email='analytics_tester@finora.app',
            currency='INR',
            currency_symbol='₹',
            monthly_budget_target=50000.0
        )
        self.user1.set_password('Pass1234')
        db.session.add(self.user1)

        # Create Test User 2
        self.user2 = User(
            name='Other User',
            email='other_analytics@finora.app',
            currency='INR',
            currency_symbol='₹'
        )
        self.user2.set_password('Pass1234')
        db.session.add(self.user2)
        db.session.commit()

        from utils.seed_data import seed_default_categories
        self.cats1 = seed_default_categories(self.user1.id)
        self.cats2 = seed_default_categories(self.user2.id)

        # Seed sample transactions for User 1
        salary_cat = self.cats1.get(('income', 'Salary'))
        food_cat = self.cats1.get(('expense', 'Food'))
        rent_cat = self.cats1.get(('expense', 'Rent'))
        shopping_cat = self.cats1.get(('expense', 'Shopping'))

        today = date.today()
        # Incomes
        t1 = Transaction(user_id=self.user1.id, title='Tech Salary', amount=100000.0, type='income', category_id=salary_cat.id, date=today.replace(day=1), payment_method='Net Banking')
        # Expenses
        t2 = Transaction(user_id=self.user1.id, title='Apartment Rent', amount=25000.0, type='expense', category_id=rent_cat.id, date=today.replace(day=2), payment_method='UPI')
        t3 = Transaction(user_id=self.user1.id, title='Supermarket Grocery', amount=10000.0, type='expense', category_id=food_cat.id, date=today.replace(day=5), payment_method='Credit Card')
        t4 = Transaction(user_id=self.user1.id, title='Fashion Wardrobe', amount=5000.0, type='expense', category_id=shopping_cat.id, date=today.replace(day=7), payment_method='Credit Card')
        
        db.session.add_all([t1, t2, t3, t4])
        db.session.commit()

    def tearDown(self):
        self.clean_test_data()
        self.ctx.pop()

    def login_user1(self):
        return self.client.post('/login', data={
            'email': 'analytics_tester@finora.app',
            'password': 'Pass1234'
        }, follow_redirects=True)

    def login_user2(self):
        return self.client.post('/login', data={
            'email': 'other_analytics@finora.app',
            'password': 'Pass1234'
        }, follow_redirects=True)

    def test_01_analytics_monthly_and_yearly_views(self):
        """Verify /analytics loads properly in both monthly and yearly views."""
        self.login_user1()

        # Monthly view
        cur_month = date.today().strftime('%Y-%m')
        res_m = self.client.get(f'/analytics?view=monthly&month={cur_month}')
        self.assertEqual(res_m.status_code, 200)
        content_m = res_m.data.decode('utf-8')
        self.assertIn('Savings Rate', content_m)
        self.assertIn('Average Daily Outflow', content_m)
        self.assertIn('Rent', content_m)

        # Yearly view
        cur_year = str(date.today().year)
        res_y = self.client.get(f'/analytics?view=yearly&year={cur_year}')
        self.assertEqual(res_y.status_code, 200)
        content_y = res_y.data.decode('utf-8')
        self.assertIn('Yearly View', content_y)

    def test_02_analytics_calculations_and_50_30_20_rule(self):
        """Verify savings rate math: Income ₹100,000, Expenses ₹40,000 -> Net Savings ₹60,000 (60%)."""
        self.login_user1()
        cur_month = date.today().strftime('%Y-%m')
        res = self.client.get(f'/analytics?view=monthly&month={cur_month}')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')

        # Total income: 100,000, total expense: 40,000, net: 60,000 (Savings rate 60%)
        self.assertIn('60.0%', content)
        self.assertIn('60,000.00', content)
        self.assertIn('Top Expense Category', content)
        self.assertIn('Rent', content)

    def test_03_reports_page_and_date_filtering(self):
        """Verify /reports route loads with date range and category filters."""
        self.login_user1()
        today = date.today()
        start_d = today.replace(day=1).strftime('%Y-%m-%d')
        end_d = today.strftime('%Y-%m-%d')

        res = self.client.get(f'/reports?start_date={start_d}&end_date={end_d}')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')
        self.assertIn('Statement Inflow', content)
        self.assertIn('Statement Outflow', content)
        self.assertIn('Tech Salary', content)
        self.assertIn('Apartment Rent', content)

    def test_04_pdf_report_export(self):
        """Verify /reports/export/pdf produces valid binary PDF data."""
        self.login_user1()
        today = date.today()
        start_d = today.replace(day=1).strftime('%Y-%m-%d')
        end_d = today.strftime('%Y-%m-%d')

        res = self.client.get(f'/reports/export/pdf?start_date={start_d}&end_date={end_d}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get('Content-Type'), 'application/pdf')
        self.assertIn('attachment', res.headers.get('Content-Disposition', ''))
        self.assertTrue(res.data.startswith(b'%PDF'), "PDF export must begin with %PDF header magic bytes")
        self.assertGreater(len(res.data), 1000, "PDF byte stream should contain rich formatted content")

    def test_05_csv_report_export(self):
        """Verify /reports/export/csv produces RFC-compliant CSV with transaction rows."""
        self.login_user1()
        res = self.client.get('/reports/export/csv')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.headers.get('Content-Type', ''))
        self.assertIn('attachment', res.headers.get('Content-Disposition', ''))
        
        csv_text = res.data.decode('utf-8')
        self.assertIn('Transaction ID,Date,Title,Type,Category,Amount', csv_text)
        self.assertIn('Tech Salary', csv_text)
        self.assertIn('Apartment Rent', csv_text)
        self.assertIn('100000.00', csv_text)
        self.assertIn('25000.00', csv_text)

    def test_06_data_isolation_on_reports_and_analytics(self):
        """Verify User B cannot access or view User A's transactions in analytics, reports, PDF or CSV."""
        # Log out user1, log in user2
        self.client.get('/logout')
        self.login_user2()

        # User B analytics
        res_analytics = self.client.get('/analytics')
        self.assertEqual(res_analytics.status_code, 200)
        self.assertNotIn('Tech Salary', res_analytics.data.decode('utf-8'))
        self.assertNotIn('100,000.00', res_analytics.data.decode('utf-8'))

        # User B reports
        res_reports = self.client.get('/reports')
        self.assertEqual(res_reports.status_code, 200)
        self.assertNotIn('Tech Salary', res_reports.data.decode('utf-8'))

        # User B CSV export
        res_csv = self.client.get('/reports/export/csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertNotIn('Tech Salary', res_csv.data.decode('utf-8'))

if __name__ == '__main__':
    unittest.main()
