import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from models import db, User, Transaction, Category

class IncomeExpenseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Clean existing test users if any
        User.query.filter(User.email.in_(['earner@finora.app', 'other@finora.app'])).delete()
        db.session.commit()

        # Create Test User 1
        self.user1 = User(
            name='Test Earner',
            email='earner@finora.app',
            currency='INR',
            currency_symbol='₹',
            monthly_budget_target=60000.0
        )
        self.user1.set_password('Pass1234')
        db.session.add(self.user1)

        # Create Test User 2 (for isolation check)
        self.user2 = User(
            name='Other Earner',
            email='other@finora.app',
            currency='INR',
            currency_symbol='₹'
        )
        self.user2.set_password('Pass1234')
        db.session.add(self.user2)
        db.session.commit()

        # Seed categories for both
        from utils.seed_data import seed_default_categories
        self.cats1 = seed_default_categories(self.user1.id)
        self.cats2 = seed_default_categories(self.user2.id)

    def tearDown(self):
        User.query.filter(User.email.in_(['earner@finora.app', 'other@finora.app'])).delete()
        db.session.commit()
        self.ctx.pop()

    def login_user1(self, client=None):
        c = client or self.client
        return c.post('/login', data={
            'email': 'earner@finora.app',
            'password': 'Pass1234'
        }, follow_redirects=True)

    def login_user2(self, client=None):
        c = client or self.client
        return c.post('/login', data={
            'email': 'other@finora.app',
            'password': 'Pass1234'
        }, follow_redirects=True)

    def test_01_income_page_loads_with_default_categories(self):
        """Verify /income page loads with all 7 required income categories."""
        self.login_user1()
        res = self.client.get('/income')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')
        
        required_income_cats = [
            'Salary', 'Freelancing', 'Business', 'Pocket Money',
            'Investments', 'Gifts', 'Other Income'
        ]
        for cat in required_income_cats:
            self.assertIn(cat, content, f"Income category '{cat}' missing from /income page")

    def test_02_expenses_page_loads_with_default_categories(self):
        """Verify /expenses page loads with all 11 required default expense categories."""
        self.login_user1()
        res = self.client.get('/expenses')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')

        required_expense_cats = [
            'Food', 'Shopping', 'Transportation', 'Education', 'Entertainment',
            'Healthcare', 'Bills', 'Rent', 'Travel', 'Subscriptions', 'Other Expenses'
        ]
        for cat in required_expense_cats:
            self.assertIn(cat, content, f"Expense category '{cat}' missing from /expenses page")

    def test_03_add_edit_delete_income_flow(self):
        """Verify full lifecycle of adding, editing, and deleting income entries."""
        self.login_user1()
        salary_cat = self.cats1.get(('income', 'Salary'))

        # 1. Add Income
        add_res = self.client.post('/transactions/add', data={
            'title': 'Monthly Consulting Retainer',
            'amount': '85000.00',
            'type': 'income',
            'category_id': str(salary_cat.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'payment_method': 'Net Banking',
            'description': 'Direct contract deposit',
            'notes': 'Quarterly tax eligible'
        }, follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)

        # Check DB
        tx = Transaction.query.filter_by(user_id=self.user1.id, title='Monthly Consulting Retainer').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 85000.0)
        self.assertEqual(tx.type, 'income')
        self.assertEqual(tx.payment_method, 'Net Banking')

        # Check /income shows the added amount
        inc_page = self.client.get('/income')
        self.assertIn('85,000.00', inc_page.data.decode('utf-8'))
        self.assertIn('Monthly Consulting Retainer', inc_page.data.decode('utf-8'))

        # 2. Edit Income
        edit_res = self.client.post(f'/transactions/edit/{tx.id}', data={
            'title': 'Consulting Retainer Revised',
            'amount': '92000.00',
            'type': 'income',
            'category_id': str(salary_cat.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'payment_method': 'Direct Transfer',
            'description': 'Updated contract rate',
            'notes': 'Reviewed'
        }, follow_redirects=True)
        self.assertEqual(edit_res.status_code, 200)

        updated_tx = db.session.get(Transaction, tx.id)
        self.assertEqual(updated_tx.title, 'Consulting Retainer Revised')
        self.assertEqual(updated_tx.amount, 92000.0)
        self.assertEqual(updated_tx.payment_method, 'Direct Transfer')

        # 3. Delete Income
        del_res = self.client.post(f'/transactions/delete/{tx.id}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertIsNone(db.session.get(Transaction, tx.id))

    def test_04_add_edit_delete_expense_flow(self):
        """Verify full lifecycle of adding, editing, and deleting expense entries."""
        self.login_user1()
        food_cat = self.cats1.get(('expense', 'Food'))

        # 1. Add Expense
        add_res = self.client.post('/transactions/add', data={
            'title': 'Organic Grocery Superstore',
            'amount': '4250.50',
            'type': 'expense',
            'category_id': str(food_cat.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'payment_method': 'Credit Card',
            'description': 'Weekly provisions',
            'notes': 'Organic aisle'
        }, follow_redirects=True)
        self.assertEqual(add_res.status_code, 200)

        tx = Transaction.query.filter_by(user_id=self.user1.id, title='Organic Grocery Superstore').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 4250.50)
        self.assertEqual(tx.type, 'expense')

        # Verify /expenses reflects this outflow
        exp_page = self.client.get('/expenses')
        self.assertIn('4,250.50', exp_page.data.decode('utf-8'))
        self.assertIn('Organic Grocery Superstore', exp_page.data.decode('utf-8'))

        # 2. Edit Expense
        edit_res = self.client.post(f'/transactions/edit/{tx.id}', data={
            'title': 'Organic Grocery Superstore (Discounted)',
            'amount': '3950.00',
            'type': 'expense',
            'category_id': str(food_cat.id),
            'date': date.today().strftime('%Y-%m-%d'),
            'payment_method': 'UPI',
            'description': 'Coupon applied',
            'notes': 'Saved ₹300'
        }, follow_redirects=True)
        self.assertEqual(edit_res.status_code, 200)

        updated_tx = db.session.get(Transaction, tx.id)
        self.assertEqual(updated_tx.amount, 3950.00)
        self.assertEqual(updated_tx.title, 'Organic Grocery Superstore (Discounted)')

        # 3. Delete Expense
        del_res = self.client.post(f'/transactions/delete/{tx.id}', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertIsNone(db.session.get(Transaction, tx.id))

    def test_05_custom_category_creation_and_deletion(self):
        """Verify custom income and expense categories can be created and managed."""
        self.login_user1()

        # Create custom income stream
        res_inc = self.client.post('/categories/add', data={
            'name': 'YouTube Sponsorships',
            'type': 'income',
            'icon': 'video',
            'color': '#8EAD98'
        }, follow_redirects=True)
        self.assertEqual(res_inc.status_code, 200)

        custom_inc = Category.query.filter_by(user_id=self.user1.id, name='YouTube Sponsorships').first()
        self.assertIsNotNone(custom_inc)
        self.assertEqual(custom_inc.type, 'income')
        self.assertFalse(custom_inc.is_default)

        # Create custom expense category
        res_exp = self.client.post('/categories/add', data={
            'name': 'Pet Veterinary & Care',
            'type': 'expense',
            'icon': 'activity',
            'color': '#D59A9A'
        }, follow_redirects=True)
        self.assertEqual(res_exp.status_code, 200)

        custom_exp = Category.query.filter_by(user_id=self.user1.id, name='Pet Veterinary & Care').first()
        self.assertIsNotNone(custom_exp)
        self.assertEqual(custom_exp.type, 'expense')

        # Delete custom category
        del_cat = self.client.post(f'/categories/delete/{custom_exp.id}', follow_redirects=True)
        self.assertEqual(del_cat.status_code, 200)
        self.assertIsNone(db.session.get(Category, custom_exp.id))

        # Attempt to delete default category (should be prevented)
        default_cat = self.cats1.get(('expense', 'Rent'))
        del_default = self.client.post(f'/categories/delete/{default_cat.id}', follow_redirects=True)
        self.assertEqual(del_default.status_code, 200)
        self.assertIsNotNone(db.session.get(Category, default_cat.id))

    def test_06_income_and_expense_filtering(self):
        """Verify keyword search, category filtering, and sorting."""
        self.login_user1()
        salary_cat = self.cats1.get(('income', 'Salary'))
        freelance_cat = self.cats1.get(('income', 'Freelancing'))

        t1 = Transaction(user_id=self.user1.id, title='Tech Salary Alpha', amount=80000.0, type='income', category_id=salary_cat.id, date=date.today())
        t2 = Transaction(user_id=self.user1.id, title='Website Redesign Contract', amount=25000.0, type='income', category_id=freelance_cat.id, date=date.today() - timedelta(days=5))
        db.session.add_all([t1, t2])
        db.session.commit()

        # Search filter
        res_search = self.client.get('/income?search=Alpha')
        content = res_search.data.decode('utf-8')
        self.assertIn('Tech Salary Alpha', content)
        self.assertNotIn('Website Redesign Contract', content)

        # Category filter
        res_cat = self.client.get(f'/income?category_id={freelance_cat.id}')
        content_cat = res_cat.data.decode('utf-8')
        self.assertIn('Website Redesign Contract', content_cat)
        self.assertNotIn('Tech Salary Alpha', content_cat)

    def test_07_unauthorized_access_prevented(self):
        """Verify User A cannot edit or delete User B's financial entries."""
        # 1. User 1 logs in and adds a confidential transaction
        self.login_user1()
        food_cat = self.cats1.get(('expense', 'Food'))
        tx = Transaction(
            user_id=self.user1.id,
            title='Confidential Expense',
            amount=999.0,
            type='expense',
            category_id=food_cat.id,
            date=date.today()
        )
        db.session.add(tx)
        db.session.commit()

        # 2. Log out User 1 and log in User 2
        self.client.get('/logout')
        self.login_user2()

        # 3. User 2 attempts unauthorized edit of User 1's transaction
        edit_res = self.client.post(f'/transactions/edit/{tx.id}', data={
            'title': 'Hacked Title',
            'amount': '1.00',
            'type': 'expense'
        })
        self.assertEqual(edit_res.status_code, 404, "Cross-user edit must return 404 Forbidden")

        # 4. User 2 attempts unauthorized delete of User 1's transaction
        del_res = self.client.post(f'/transactions/delete/{tx.id}')
        self.assertEqual(del_res.status_code, 404, "Cross-user delete must return 404 Forbidden")

        # 5. Verify record remained completely untouched
        surviving_tx = db.session.get(Transaction, tx.id)
        self.assertIsNotNone(surviving_tx)
        self.assertEqual(surviving_tx.title, 'Confidential Expense')
        self.assertEqual(surviving_tx.amount, 999.0)

    def test_08_negative_or_invalid_amounts_rejected(self):
        """Verify invalid or non-positive amounts cannot be recorded."""
        self.login_user1()
        food_cat = self.cats1.get(('expense', 'Food'))

        res_neg = self.client.post('/transactions/add', data={
            'title': 'Invalid Negative Entry',
            'amount': '-500',
            'type': 'expense',
            'category_id': str(food_cat.id)
        }, follow_redirects=True)
        self.assertIn('Please enter a valid positive transaction amount', res_neg.data.decode('utf-8'))
        self.assertIsNone(Transaction.query.filter_by(title='Invalid Negative Entry').first())

if __name__ == '__main__':
    unittest.main()
