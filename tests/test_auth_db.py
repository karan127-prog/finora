import sys
import os
import unittest

sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from models import db, User, Transaction, Category, Budget, SavingsGoal, RecurringTransaction

class TestAuthAndDatabase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure in-memory or dedicated test database
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def setUp(self):
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_01_password_hashing_security(self):
        """Verify passwords are never stored in plain text and hashing works."""
        u = User(name='Test Security', email='sec_test@finora.app')
        u.set_password('SecretPass123')
        
        self.assertNotEqual(u.password_hash, 'SecretPass123')
        self.assertFalse(u.password_hash.startswith('SecretPass'))
        self.assertTrue(u.check_password('SecretPass123'))
        self.assertFalse(u.check_password('WrongPass'))

    def test_02_registration_validation(self):
        """Verify registration input validation rules."""
        # 1. Invalid email
        res = self.client.post('/register', data={
            'name': 'Bad Email',
            'email': 'not-an-email',
            'password': 'password123',
            'confirm_password': 'password123',
            'currency': 'INR'
        }, follow_redirects=True)
        self.assertIn(b'valid email', res.data.lower())

        # 2. Short password (< 6 chars)
        res = self.client.post('/register', data={
            'name': 'Short Pass',
            'email': 'short@finora.app',
            'password': '123',
            'confirm_password': '123',
            'currency': 'INR'
        }, follow_redirects=True)
        self.assertIn(b'at least 6 characters', res.data.lower())

        # 3. Mismatched passwords
        res = self.client.post('/register', data={
            'name': 'Mismatch Pass',
            'email': 'mismatch@finora.app',
            'password': 'password123',
            'confirm_password': 'different_pass',
            'currency': 'INR'
        }, follow_redirects=True)
        self.assertIn(b'passwords do not match', res.data.lower())

    def test_03_registration_and_category_seeding(self):
        """Verify successful registration auto-seeds user default categories."""
        email = 'new_registered_user@finora.app'
        # Clean up if existing
        old = User.query.filter_by(email=email).first()
        if old:
            db.session.delete(old)
            db.session.commit()

        res = self.client.post('/register', data={
            'name': 'Riya Kapoor',
            'email': email,
            'password': 'riya_secure_password_2026',
            'confirm_password': 'riya_secure_password_2026',
            'currency': 'INR'
        }, follow_redirects=True)
        
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dashboard', res.data)

        # Verify in DB
        user = User.query.filter_by(email=email).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, 'Riya Kapoor')

        # Check default categories seeded for this user
        user_cats = Category.query.filter_by(user_id=user.id).all()
        self.assertGreater(len(user_cats), 0)
        cat_names = [c.name for c in user_cats]
        self.assertIn('Salary', cat_names)
        self.assertIn('Food', cat_names)

    def test_04_duplicate_email_prevention(self):
        """Verify system prevents duplicate email registration."""
        res = self.client.post('/register', data={
            'name': 'Duplicate User',
            'email': 'demo@finora.app',  # Already exists
            'password': 'password123',
            'confirm_password': 'password123',
            'currency': 'INR'
        }, follow_redirects=True)
        self.assertIn(b'already exists', res.data.lower())

    def test_05_login_validation(self):
        """Verify login authentication flows."""
        # Bad password
        res = self.client.post('/login', data={
            'email': 'demo@finora.app',
            'password': 'wrong_password_xyz'
        }, follow_redirects=True)
        self.assertIn(b'invalid email address or password', res.data.lower())

        # Nonexistent email
        res = self.client.post('/login', data={
            'email': 'nonexistent_person_404@finora.app',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'invalid email address or password', res.data.lower())

        # Good login
        res = self.client.post('/login', data={
            'email': 'demo@finora.app',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Financial Overview', res.data)

    def test_06_protected_routes_redirect(self):
        """Verify unauthenticated requests cannot access protected financial data."""
        # New client without session
        fresh_client = self.app.test_client()
        for path in ['/dashboard', '/transactions', '/income', '/expenses', '/budgets', '/savings', '/reports', '/settings']:
            res = fresh_client.get(path)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/login', res.headers['Location'])

    def test_07_open_redirect_protection(self):
        """Verify evil next_page URLs are blocked and defaulted to dashboard."""
        client = self.app.test_client()
        # Attempt malicious next parameter
        res = client.post('/login?next=https://malicious-phishing-site.com', data={
            'email': 'demo@finora.app',
            'password': 'password123'
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        # Must redirect to dashboard, not the external url
        self.assertNotIn('malicious-phishing-site', res.headers['Location'])

    def test_08_strict_per_user_data_isolation(self):
        """
        Verify that User A cannot see, edit, or delete User B's financial data.
        """
        # 1. Create User A and User B
        user_a = User.query.filter_by(email='user_a@finora.app').first()
        if not user_a:
            user_a = User(name='User A', email='user_a@finora.app')
            user_a.set_password('pass12345')
            db.session.add(user_a)
            db.session.commit()

        user_b = User.query.filter_by(email='user_b@finora.app').first()
        if not user_b:
            user_b = User(name='User B', email='user_b@finora.app')
            user_b.set_password('pass12345')
            db.session.add(user_b)
            db.session.commit()

        # 2. Add confidential transaction for User A
        tx_a = Transaction(
            user_id=user_a.id,
            title='Confidential Salary Bonus A',
            amount=99999.0,
            type='income'
        )
        db.session.add(tx_a)
        db.session.commit()

        # 3. Log in as User B
        client_b = self.app.test_client()
        client_b.post('/login', data={'email': 'user_b@finora.app', 'password': 'pass12345'})

        # User B visits transactions list
        res = client_b.get('/transactions')
        self.assertNotIn(b'Confidential Salary Bonus A', res.data)
        self.assertNotIn(b'99999.00', res.data)

        # 4. User B attempts unauthorized EDIT of User A's transaction
        res_edit = client_b.post(f'/transactions/edit/{tx_a.id}', data={
            'title': 'Hacked by User B',
            'amount': '1.00',
            'type': 'expense'
        })
        self.assertEqual(res_edit.status_code, 404, "Cross-user edit must be forbidden with 404!")

        # Verify transaction remained untouched
        recheck_tx = Transaction.query.get(tx_a.id)
        self.assertEqual(recheck_tx.title, 'Confidential Salary Bonus A')

        # 5. User B attempts unauthorized DELETE of User A's transaction
        res_delete = client_b.post(f'/transactions/delete/{tx_a.id}')
        self.assertEqual(res_delete.status_code, 404, "Cross-user delete must be forbidden with 404!")

        # Verify transaction still exists
        self.assertIsNotNone(Transaction.query.get(tx_a.id))

    def test_09_cascade_delete_integrity(self):
        """Verify that deleting a user cleanly purges all their associated records."""
        # Create temporary user with records
        u = User(name='Temp User', email='temp_to_delete@finora.app')
        u.set_password('password123')
        db.session.add(u)
        db.session.commit()

        tx = Transaction(user_id=u.id, title='Delete Me Tx', amount=500.0, type='expense')
        db.session.add(tx)
        db.session.commit()
        tx_id = tx.id

        # Delete user
        db.session.delete(u)
        db.session.commit()

        # Verify transaction was cascade-deleted
        self.assertIsNone(Transaction.query.get(tx_id))

if __name__ == '__main__':
    unittest.main()
