import unittest
from datetime import date, datetime, timedelta
from app import create_app
from models import db, User, Transaction, Category, Budget, SavingsGoal, SavingsContribution, RecurringTransaction, Notification

class RecurringCalendarNotificationsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean prior test fixtures
        self.clean_test_data()

        # Seed test user
        self.user = User(
            name='Test Phase6 User',
            email='phase6@finora.test',
            currency='INR',
            monthly_budget_target=50000.0
        )
        self.user.set_password('Phase6Pass!123')
        db.session.add(self.user)

        self.user2 = User(
            name='Test Phase6 Rival',
            email='phase6rival@finora.test',
            currency='INR',
            monthly_budget_target=30000.0
        )
        self.user2.set_password('Phase6Pass!123')
        db.session.add(self.user2)
        db.session.commit()

        # Categories
        self.cat_rent = Category.query.filter_by(name='Rent').first()
        if not self.cat_rent:
            self.cat_rent = Category(name='Rent', type='expense', icon='home', color='#789BB8')
            db.session.add(self.cat_rent)

        self.cat_salary = Category.query.filter_by(name='Salary').first()
        if not self.cat_salary:
            self.cat_salary = Category(name='Salary', type='income', icon='briefcase', color='#8EAD98')
            db.session.add(self.cat_salary)

        db.session.commit()

    def clean_test_data(self):
        u1 = User.query.filter_by(email='phase6@finora.test').first()
        u2 = User.query.filter_by(email='phase6rival@finora.test').first()
        u_ids = [u.id for u in (u1, u2) if u]
        if u_ids:
            Notification.query.filter(Notification.user_id.in_(u_ids)).delete(synchronize_session=False)
            RecurringTransaction.query.filter(RecurringTransaction.user_id.in_(u_ids)).delete(synchronize_session=False)
            Transaction.query.filter(Transaction.user_id.in_(u_ids)).delete(synchronize_session=False)
            goal_ids = [g.id for g in SavingsGoal.query.filter(SavingsGoal.user_id.in_(u_ids)).all()]
            if goal_ids:
                SavingsContribution.query.filter(SavingsContribution.goal_id.in_(goal_ids)).delete(synchronize_session=False)
            SavingsGoal.query.filter(SavingsGoal.user_id.in_(u_ids)).delete(synchronize_session=False)
            Budget.query.filter(Budget.user_id.in_(u_ids)).delete(synchronize_session=False)
            User.query.filter(User.id.in_(u_ids)).delete(synchronize_session=False)
            db.session.commit()

    def tearDown(self):
        self.clean_test_data()
        db.session.remove()
        self.app_context.pop()

    def login_user1(self):
        self.client.get('/logout')
        return self.client.post('/login', data={
            'email': 'phase6@finora.test',
            'password': 'Phase6Pass!123'
        }, follow_redirects=True)

    def login_user2(self):
        self.client.get('/logout')
        return self.client.post('/login', data={
            'email': 'phase6rival@finora.test',
            'password': 'Phase6Pass!123'
        }, follow_redirects=True)

    def test_01_recurring_crud(self):
        """Verify creating, editing, pausing/resuming, and deleting recurring payments."""
        self.login_user1()
        today = date.today()

        # 1. Create recurring item
        res = self.client.post('/recurring/add', data={
            'title': 'Phase6 High-Speed Fiber',
            'amount': '1499.00',
            'type': 'expense',
            'category_id': str(self.cat_rent.id),
            'frequency': 'monthly',
            'start_date': today.strftime('%Y-%m-%d'),
            'payment_method': 'UPI',
            'description': 'Monthly broadband subscription'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        item = RecurringTransaction.query.filter_by(user_id=self.user.id, title='Phase6 High-Speed Fiber').first()
        self.assertIsNotNone(item)
        self.assertEqual(item.amount, 1499.00)
        self.assertEqual(item.is_active, True)

        # 2. Edit recurring item
        res_edit = self.client.post(f'/recurring/edit/{item.id}', data={
            'title': 'Phase6 Gigabit Fiber Pro',
            'amount': '1999.00',
            'type': 'expense',
            'category_id': str(self.cat_rent.id),
            'frequency': 'monthly',
            'next_date': today.strftime('%Y-%m-%d'),
            'payment_method': 'Credit Card',
            'description': 'Upgraded broadband speed'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)

        db.session.refresh(item)
        self.assertEqual(item.title, 'Phase6 Gigabit Fiber Pro')
        self.assertEqual(item.amount, 1999.00)
        self.assertEqual(item.payment_method, 'Credit Card')

        # 3. Toggle recurring item (pause)
        res_toggle = self.client.post(f'/recurring/toggle/{item.id}', follow_redirects=True)
        self.assertEqual(res_toggle.status_code, 200)
        db.session.refresh(item)
        self.assertEqual(item.is_active, False)

        # 4. Delete recurring item
        res_del = self.client.post(f'/recurring/delete/{item.id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        deleted = RecurringTransaction.query.get(item.id)
        self.assertIsNone(deleted)

    def test_02_process_due_payments_without_duplicate(self):
        """Verify processing due payments creates transactions and avoids duplicate entries."""
        self.login_user1()
        today = date.today()

        # Create recurring item due today
        rec = RecurringTransaction(
            user_id=self.user.id,
            category_id=self.cat_rent.id,
            title='Phase6 Cloud Server Subscription',
            amount=2500.0,
            type='expense',
            frequency='monthly',
            start_date=today,
            next_date=today,
            payment_method='Auto-Debit',
            is_active=True
        )
        db.session.add(rec)
        db.session.commit()

        # 1. Execute process due
        res = self.client.post('/recurring/process-due', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Transaction should exist
        tx = Transaction.query.filter_by(
            user_id=self.user.id,
            title='Phase6 Cloud Server Subscription',
            date=today
        ).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.amount, 2500.0)

        # Next date should be advanced to next month
        db.session.refresh(rec)
        self.assertTrue(rec.next_date > today)

        # A notification should have been recorded
        notif = Notification.query.filter_by(user_id=self.user.id).filter(Notification.title.like('Recurring Processed%')).first()
        self.assertIsNotNone(notif)
        self.assertIn('Recurring Processed', notif.title)

        # 2. Re-trigger process due with next_date reset to today - should not duplicate transaction for today
        rec.next_date = today
        db.session.commit()

        res_second = self.client.post('/recurring/process-due', follow_redirects=True)
        self.assertEqual(res_second.status_code, 200)

        # Transaction count must remain exactly 1
        tx_count = Transaction.query.filter_by(
            user_id=self.user.id,
            title='Phase6 Cloud Server Subscription',
            date=today
        ).count()
        self.assertEqual(tx_count, 1)

    def test_03_financial_calendar_events_and_navigation(self):
        """Verify financial calendar shows income, expense, recurring, and savings events."""
        self.login_user1()
        today = date.today()

        # Seed transaction
        tx = Transaction(
            user_id=self.user.id,
            category_id=self.cat_salary.id,
            title='Phase6 Consulting Invoice',
            amount=45000.0,
            type='income',
            date=today,
            payment_method='Net Banking'
        )
        db.session.add(tx)

        # Seed savings contribution
        goal = SavingsGoal(
            user_id=self.user.id,
            name='Phase6 Goa Vacation',
            target_amount=30000.0,
            target_date=today + timedelta(days=90)
        )
        db.session.add(goal)
        db.session.commit()

        contrib = SavingsContribution(
            goal_id=goal.id,
            amount=5000.0,
            date=today,
            notes='Initial savings tranche'
        )
        db.session.add(contrib)
        db.session.commit()

        # Load calendar
        res = self.client.get(f'/calendar?year={today.year}&month={today.month}')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')

        self.assertIn('Financial Calendar', content)
        self.assertIn('Phase6 Consulting Invoice', content)
        self.assertIn('Phase6 Goa Vacation', content)

    def test_04_smart_notifications_generation_and_api(self):
        """Verify automated notifications generation, mark-as-read, and deletion."""
        self.login_user1()
        today = date.today()

        # Add upcoming recurring payment due tomorrow
        rec_tomorrow = RecurringTransaction(
            user_id=self.user.id,
            category_id=self.cat_rent.id,
            title='Phase6 Netflix 4K UHD',
            amount=649.0,
            type='expense',
            frequency='monthly',
            start_date=today,
            next_date=today + timedelta(days=1),
            payment_method='Credit Card',
            is_active=True
        )
        db.session.add(rec_tomorrow)
        db.session.commit()

        # Fetch notifications via API (this calls sync_smart_notifications)
        res_api = self.client.get('/api/notifications')
        self.assertEqual(res_api.status_code, 200)
        data = res_api.get_json()

        self.assertGreaterEqual(data['unread_count'], 1)
        self.assertTrue(any('Phase6 Netflix 4K UHD' in n['title'] for n in data['notifications']))

        first_notif_id = data['notifications'][0]['id']

        # Mark single as read
        res_read = self.client.post(f'/api/notifications/mark-read/{first_notif_id}')
        self.assertEqual(res_read.status_code, 200)
        self.assertTrue(res_read.get_json()['success'])

        # Mark all as read
        res_all = self.client.post('/api/notifications/mark-all-read')
        self.assertEqual(res_all.status_code, 200)

        # Delete notification
        res_del = self.client.post(f'/api/notifications/delete/{first_notif_id}')
        self.assertEqual(res_del.status_code, 200)
        self.assertIsNone(Notification.query.get(first_notif_id))

    def test_05_cross_user_isolation(self):
        """Verify User 2 cannot access, edit, toggle, or delete User 1 recurring items."""
        self.login_user1()
        today = date.today()

        rec = RecurringTransaction(
            user_id=self.user.id,
            title='Phase6 User 1 Secret Obligation',
            amount=50000.0,
            type='expense',
            frequency='yearly',
            start_date=today,
            next_date=today,
            payment_method='Cash',
            is_active=True
        )
        db.session.add(rec)
        db.session.commit()

        # User 2 tries to toggle User 1's recurring item
        self.login_user2()
        res_toggle = self.client.post(f'/recurring/toggle/{rec.id}', follow_redirects=False)
        self.assertEqual(res_toggle.status_code, 404)

        # User 2 tries to delete User 1's recurring item
        res_delete = self.client.post(f'/recurring/delete/{rec.id}', follow_redirects=False)
        self.assertEqual(res_delete.status_code, 404)

if __name__ == '__main__':
    unittest.main()
