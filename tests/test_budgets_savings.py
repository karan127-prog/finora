import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from models import db, User, Transaction, Category, Budget, SavingsGoal, SavingsContribution, Notification

class BudgetsSavingsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False

    def clean_test_data(self):
        try:
            db.session.rollback()
            test_users = User.query.filter(User.email.in_(['budget_tester@finora.app', 'other_tester@finora.app'])).all()
            test_user_ids = [u.id for u in test_users]
            if test_user_ids:
                Budget.query.filter(Budget.user_id.in_(test_user_ids)).delete(synchronize_session=False)
                Transaction.query.filter(Transaction.user_id.in_(test_user_ids)).delete(synchronize_session=False)
                Notification.query.filter(Notification.user_id.in_(test_user_ids)).delete(synchronize_session=False)
                
                # Delete goals and contributions
                goals = SavingsGoal.query.filter(SavingsGoal.user_id.in_(test_user_ids)).all()
                for g in goals:
                    db.session.delete(g)
                db.session.flush()

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
            name='Budget Tester',
            email='budget_tester@finora.app',
            currency='INR',
            currency_symbol='₹',
            monthly_budget_target=50000.0
        )
        self.user1.set_password('Pass1234')
        db.session.add(self.user1)

        # Create Test User 2
        self.user2 = User(
            name='Other Tester',
            email='other_tester@finora.app',
            currency='INR',
            currency_symbol='₹'
        )
        self.user2.set_password('Pass1234')
        db.session.add(self.user2)
        db.session.commit()

        from utils.seed_data import seed_default_categories
        self.cats1 = seed_default_categories(self.user1.id)
        self.cats2 = seed_default_categories(self.user2.id)

    def tearDown(self):
        self.clean_test_data()
        self.ctx.pop()

    def login_user1(self):
        return self.client.post('/login', data={
            'email': 'budget_tester@finora.app',
            'password': 'Pass1234'
        }, follow_redirects=True)

    def login_user2(self):
        return self.client.post('/login', data={
            'email': 'other_tester@finora.app',
            'password': 'Pass1234'
        }, follow_redirects=True)

    def test_01_budgets_page_renders_with_metrics(self):
        """Verify /budgets route renders properly with master overview cards."""
        self.login_user1()
        res = self.client.get('/budgets')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')
        self.assertIn('Total Allocated Budget', content)
        self.assertIn('Total Spent This Month', content)
        self.assertIn('Remaining Safe Buffer', content)

    def test_02_create_edit_delete_budget(self):
        """Verify creating, editing, and deleting a category budget."""
        self.login_user1()
        food_cat = self.cats1.get(('expense', 'Food'))
        cur_month = date.today().strftime('%Y-%m')

        # 1. Create Food Budget: ₹5,000
        res_add = self.client.post('/budgets/add', data={
            'category_id': str(food_cat.id),
            'month': cur_month,
            'limit_amount': '5000'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)

        b = Budget.query.filter_by(user_id=self.user1.id, category_id=food_cat.id, month=cur_month).first()
        self.assertIsNotNone(b)
        self.assertEqual(b.limit_amount, 5000.0)

        # 2. Edit Budget: Increase to ₹6,500
        res_edit = self.client.post(f'/budgets/edit/{b.id}', data={
            'limit_amount': '6500',
            'month': cur_month
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)

        updated_b = db.session.get(Budget, b.id)
        self.assertEqual(updated_b.limit_amount, 6500.0)

        # 3. Delete Budget
        res_del = self.client.post(f'/budgets/delete/{b.id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIsNone(db.session.get(Budget, b.id))

    def test_03_budget_math_and_threshold_warnings(self):
        """Verify Example: Food Budget: ₹5,000, Spent: ₹3,200, Remaining: ₹1,800 and threshold warnings."""
        self.login_user1()
        food_cat = self.cats1.get(('expense', 'Food'))
        cur_month = date.today().strftime('%Y-%m')

        # Set budget to ₹5,000
        b = Budget(user_id=self.user1.id, category_id=food_cat.id, month=cur_month, limit_amount=5000.0)
        db.session.add(b)
        # Add expense of ₹3,200
        tx = Transaction(
            user_id=self.user1.id,
            category_id=food_cat.id,
            title='Grocery Provisions',
            amount=3200.0,
            type='expense',
            date=date.today()
        )
        db.session.add(tx)
        db.session.commit()

        # Visit /budgets and verify math: Spent ₹3,200, Remaining ₹1,800
        res = self.client.get(f'/budgets?month={cur_month}')
        self.assertEqual(res.status_code, 200)
        content = res.data.decode('utf-8')

        self.assertIn('5,000', content)
        self.assertIn('3,200', content)
        self.assertIn('1,800', content)
        self.assertIn('On Track', content)

        # Add another ₹1,500 expense (Total spent = 4,700, which is 94% -> Critical Warning 90%+)
        tx2 = Transaction(
            user_id=self.user1.id,
            category_id=food_cat.id,
            title='Dinner Out',
            amount=1500.0,
            type='expense',
            date=date.today()
        )
        db.session.add(tx2)
        db.session.commit()

        res2 = self.client.get(f'/budgets?month={cur_month}')
        content2 = res2.data.decode('utf-8')
        self.assertIn('Critical Warning (90%+)', content2)

        # Add another ₹1,000 expense (Total spent = 5,700, which is 114% -> Exceeded 100%+)
        tx3 = Transaction(
            user_id=self.user1.id,
            category_id=food_cat.id,
            title='Snacks',
            amount=1000.0,
            type='expense',
            date=date.today()
        )
        db.session.add(tx3)
        db.session.commit()

        res3 = self.client.get(f'/budgets?month={cur_month}')
        content3 = res3.data.decode('utf-8')
        self.assertIn('Budget Exceeded', content3)
        self.assertIn('Exceeded by', content3)

    def test_04_clone_previous_month_budgets(self):
        """Verify cloning previous month's budget targets into current month."""
        self.login_user1()
        food_cat = self.cats1.get(('expense', 'Food'))
        rent_cat = self.cats1.get(('expense', 'Rent'))

        prev_month = '2026-06'
        curr_month = '2026-07'

        b1 = Budget(user_id=self.user1.id, category_id=food_cat.id, month=prev_month, limit_amount=12000.0)
        b2 = Budget(user_id=self.user1.id, category_id=rent_cat.id, month=prev_month, limit_amount=22000.0)
        db.session.add_all([b1, b2])
        db.session.commit()

        # Clone from 2026-06 into 2026-07
        res = self.client.post('/budgets/copy-previous', data={
            'from_month': prev_month,
            'to_month': curr_month
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify new budgets exist for curr_month
        cloned_food = Budget.query.filter_by(user_id=self.user1.id, category_id=food_cat.id, month=curr_month).first()
        cloned_rent = Budget.query.filter_by(user_id=self.user1.id, category_id=rent_cat.id, month=curr_month).first()
        self.assertIsNotNone(cloned_food)
        self.assertEqual(cloned_food.limit_amount, 12000.0)
        self.assertIsNotNone(cloned_rent)
        self.assertEqual(cloned_rent.limit_amount, 22000.0)

    def test_05_savings_goals_crud_lifecycle(self):
        """Verify creating, editing, and deleting savings goals."""
        self.login_user1()
        target_date = date.today() + timedelta(days=120)

        # 1. Create Goal: New Laptop (₹70,000)
        res_add = self.client.post('/savings/add', data={
            'name': 'New Laptop',
            'target_amount': '70000',
            'current_amount': '15000',
            'target_date': target_date.strftime('%Y-%m-%d'),
            'icon': 'laptop'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)

        goal = SavingsGoal.query.filter_by(user_id=self.user1.id, name='New Laptop').first()
        self.assertIsNotNone(goal)
        self.assertEqual(goal.target_amount, 70000.0)
        self.assertEqual(goal.current_amount, 15000.0)
        self.assertEqual(goal.status, 'in_progress')
        self.assertEqual(goal.progress_percentage, 21.4)
        self.assertEqual(goal.remaining_amount, 55000.0)

        # Verify initial contribution logged
        contrib = goal.contributions.first()
        self.assertIsNotNone(contrib)
        self.assertEqual(contrib.amount, 15000.0)

        # 2. Edit Goal: Update Target to ₹75,000
        res_edit = self.client.post(f'/savings/edit/{goal.id}', data={
            'name': 'MacBook Pro M3 Max',
            'target_amount': '75000',
            'target_date': target_date.strftime('%Y-%m-%d'),
            'icon': 'laptop'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)

        updated_goal = db.session.get(SavingsGoal, goal.id)
        self.assertEqual(updated_goal.name, 'MacBook Pro M3 Max')
        self.assertEqual(updated_goal.target_amount, 75000.0)

        # 3. Delete Goal
        res_del = self.client.post(f'/savings/delete/{goal.id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIsNone(db.session.get(SavingsGoal, goal.id))

    def test_06_add_money_and_goal_completion(self):
        """Verify depositing money towards goal and automated completion milestone."""
        self.login_user1()
        target_date = date.today() + timedelta(days=60)

        # Goal: Vacation (₹30,000) with initial ₹20,000
        goal = SavingsGoal(
            user_id=self.user1.id,
            name='Goa Vacation',
            target_amount=30000.0,
            current_amount=20000.0,
            target_date=target_date,
            icon='compass',
            status='in_progress'
        )
        db.session.add(goal)
        db.session.commit()

        # Deposit ₹5,000
        res1 = self.client.post(f'/savings/contribute/{goal.id}', data={
            'amount': '5000',
            'notes': 'Bonus payout'
        }, follow_redirects=True)
        self.assertEqual(res1.status_code, 200)

        g1 = db.session.get(SavingsGoal, goal.id)
        self.assertEqual(g1.current_amount, 25000.0)
        self.assertEqual(g1.status, 'in_progress')

        # Deposit remaining ₹5,000 to reach 100% completion
        res2 = self.client.post(f'/savings/contribute/{goal.id}', data={
            'amount': '5000',
            'notes': 'Final milestone deposit'
        }, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)

        g2 = db.session.get(SavingsGoal, goal.id)
        self.assertEqual(g2.current_amount, 30000.0)
        self.assertEqual(g2.status, 'completed')
        self.assertEqual(g2.progress_percentage, 100.0)

        # Verify milestone notification created
        notif = Notification.query.filter_by(user_id=self.user1.id, type='success').first()
        self.assertIsNotNone(notif)
        self.assertIn('Goa Vacation', notif.title)

    def test_07_savings_withdrawal(self):
        """Verify withdrawing money from savings goal."""
        self.login_user1()
        goal = SavingsGoal(
            user_id=self.user1.id,
            name='Emergency Fund',
            target_amount=20000.0,
            current_amount=15000.0,
            target_date=date.today() + timedelta(days=90),
            status='in_progress'
        )
        db.session.add(goal)
        db.session.commit()

        # Withdraw ₹3,000
        res = self.client.post(f'/savings/withdraw/{goal.id}', data={
            'amount': '3000',
            'notes': 'Urgent repair expense'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        g = db.session.get(SavingsGoal, goal.id)
        self.assertEqual(g.current_amount, 12000.0)

        # Attempt to withdraw more than saved
        res_invalid = self.client.post(f'/savings/withdraw/{goal.id}', data={
            'amount': '50000'
        }, follow_redirects=True)
        self.assertIn('Cannot withdraw more than current saved amount', res_invalid.data.decode('utf-8'))

    def test_08_cross_user_isolation(self):
        """Verify User A cannot edit, delete, or contribute to User B's budgets or goals."""
        self.login_user1()
        food_cat = self.cats1.get(('expense', 'Food'))
        b = Budget(user_id=self.user1.id, category_id=food_cat.id, month='2027-01', limit_amount=5000.0)
        g = SavingsGoal(user_id=self.user1.id, name='Private Goal', target_amount=10000.0, target_date=date.today())
        db.session.add_all([b, g])
        db.session.commit()

        # Log out user1, log in user2
        self.client.get('/logout')
        self.login_user2()

        # User B attempts to edit User A's budget -> 404
        res_b_edit = self.client.post(f'/budgets/edit/{b.id}', data={'limit_amount': '99999'})
        self.assertEqual(res_b_edit.status_code, 404)

        # User B attempts to delete User A's budget -> 404
        res_b_del = self.client.post(f'/budgets/delete/{b.id}')
        self.assertEqual(res_b_del.status_code, 404)

        # User B attempts to edit User A's savings goal -> 404
        res_g_edit = self.client.post(f'/savings/edit/{g.id}', data={'name': 'Hacked', 'target_amount': '1'})
        self.assertEqual(res_g_edit.status_code, 404)

        # User B attempts to contribute to User A's savings goal -> 404
        res_g_contrib = self.client.post(f'/savings/contribute/{g.id}', data={'amount': '100'})
        self.assertEqual(res_g_contrib.status_code, 404)

        # User B attempts to delete User A's savings goal -> 404
        res_g_del = self.client.post(f'/savings/delete/{g.id}')
        self.assertEqual(res_g_del.status_code, 404)

if __name__ == '__main__':
    unittest.main()
