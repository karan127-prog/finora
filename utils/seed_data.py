from datetime import datetime, date, timedelta
from models import db, User, Category, Transaction, Budget, SavingsGoal, SavingsContribution, RecurringTransaction, Notification

DEFAULT_INCOME_CATEGORIES = [
    {'name': 'Salary', 'icon': 'briefcase', 'color': '#789BB8'},
    {'name': 'Freelancing', 'icon': 'laptop', 'color': '#8EAD98'},
    {'name': 'Business', 'icon': 'trending-up', 'color': '#A9C5DC'},
    {'name': 'Pocket Money', 'icon': 'wallet', 'color': '#C5D2DC'},
    {'name': 'Investments', 'icon': 'pie-chart', 'color': '#789BB8'},
    {'name': 'Gifts', 'icon': 'gift', 'color': '#D6B77A'},
    {'name': 'Other Income', 'icon': 'plus-circle', 'color': '#8799A8'}
]

DEFAULT_EXPENSE_CATEGORIES = [
    {'name': 'Food', 'icon': 'utensils', 'color': '#D6B77A'},
    {'name': 'Shopping', 'icon': 'shopping-bag', 'color': '#A9C5DC'},
    {'name': 'Transportation', 'icon': 'car', 'color': '#789BB8'},
    {'name': 'Education', 'icon': 'book-open', 'color': '#8EAD98'},
    {'name': 'Entertainment', 'icon': 'film', 'color': '#C5D2DC'},
    {'name': 'Healthcare', 'icon': 'activity', 'color': '#D59A9A'},
    {'name': 'Bills', 'icon': 'file-text', 'color': '#8799A8'},
    {'name': 'Rent', 'icon': 'home', 'color': '#789BB8'},
    {'name': 'Travel', 'icon': 'compass', 'color': '#A9C5DC'},
    {'name': 'Subscriptions', 'icon': 'credit-card', 'color': '#D6B77A'},
    {'name': 'Other Expenses', 'icon': 'more-horizontal', 'color': '#8799A8'}
]

def seed_default_categories(user_id=None):
    """Ensure global and user categories exist."""
    created_cats = {}
    
    # Check income
    for item in DEFAULT_INCOME_CATEGORIES:
        cat = Category.query.filter_by(name=item['name'], type='income', user_id=user_id).first()
        if not cat:
            cat = Category(
                name=item['name'],
                type='income',
                icon=item['icon'],
                color=item['color'],
                user_id=user_id,
                is_default=True
            )
            db.session.add(cat)
            db.session.flush()
        created_cats[('income', item['name'])] = cat

    # Check expense
    for item in DEFAULT_EXPENSE_CATEGORIES:
        cat = Category.query.filter_by(name=item['name'], type='expense', user_id=user_id).first()
        if not cat:
            cat = Category(
                name=item['name'],
                type='expense',
                icon=item['icon'],
                color=item['color'],
                user_id=user_id,
                is_default=True
            )
            db.session.add(cat)
            db.session.flush()
        created_cats[('expense', item['name'])] = cat

    db.session.commit()
    return created_cats

def seed_demo_user():
    """Create a realistic demo account with extensive, rich financial history."""
    demo_user = User.query.filter_by(email='demo@finora.app').first()
    if demo_user:
        return demo_user

    demo_user = User(
        name='Aarav Sharma',
        email='demo@finora.app',
        currency='INR',
        currency_symbol='₹',
        monthly_budget_target=65000.0
    )
    demo_user.set_password('password123')
    db.session.add(demo_user)
    db.session.flush()

    cats = seed_default_categories(demo_user.id)
    today = date.today()
    current_month_str = today.strftime('%Y-%m')
    prev_month_date = (today.replace(day=1) - timedelta(days=1))
    prev_month_str = prev_month_date.strftime('%Y-%m')

    # 1. Budgets for current month
    budget_data = [
        ('Food', 12000.0),
        ('Rent', 22000.0),
        ('Shopping', 8000.0),
        ('Transportation', 5000.0),
        ('Entertainment', 4000.0),
        ('Bills', 6000.0),
        ('Subscriptions', 2500.0),
        ('Healthcare', 3500.0)
    ]
    for cat_name, limit in budget_data:
        cat = cats.get(('expense', cat_name))
        if cat:
            b = Budget(user_id=demo_user.id, category_id=cat.id, month=current_month_str, limit_amount=limit)
            db.session.add(b)

    # 2. Savings Goals
    g1 = SavingsGoal(
        user_id=demo_user.id,
        name='Emergency Fund',
        target_amount=150000.0,
        current_amount=95000.0,
        target_date=today + timedelta(days=120),
        icon='shield',
        color='#789BB8',
        status='in_progress'
    )
    g2 = SavingsGoal(
        user_id=demo_user.id,
        name='MacBook Pro M3',
        target_amount=180000.0,
        current_amount=125000.0,
        target_date=today + timedelta(days=60),
        icon='laptop',
        color='#8EAD98',
        status='in_progress'
    )
    g3 = SavingsGoal(
        user_id=demo_user.id,
        name='Japan Trip 2027',
        target_amount=250000.0,
        current_amount=85000.0,
        target_date=today + timedelta(days=240),
        icon='compass',
        color='#A9C5DC',
        status='in_progress'
    )
    db.session.add_all([g1, g2, g3])
    db.session.flush()

    # Contributions
    c1 = SavingsContribution(goal_id=g1.id, amount=15000.0, date=today - timedelta(days=12), notes='Monthly emergency allocation')
    c2 = SavingsContribution(goal_id=g2.id, amount=20000.0, date=today - timedelta(days=5), notes='Bonus payout savings')
    db.session.add_all([c1, c2])

    # 3. Recurring Transactions
    r1 = RecurringTransaction(
        user_id=demo_user.id,
        category_id=cats.get(('income', 'Salary')).id,
        title='Tech Corp Monthly Salary',
        amount=115000.0,
        type='income',
        frequency='monthly',
        start_date=today - timedelta(days=60),
        next_date=today + timedelta(days=4),
        payment_method='Net Banking',
        is_active=True,
        description='Direct bank deposit from employer'
    )
    r2 = RecurringTransaction(
        user_id=demo_user.id,
        category_id=cats.get(('expense', 'Rent')).id,
        title='Apartment Rent',
        amount=22000.0,
        type='expense',
        frequency='monthly',
        start_date=today - timedelta(days=60),
        next_date=today + timedelta(days=3),
        payment_method='UPI',
        is_active=True,
        description='Monthly apartment rent transfer'
    )
    r3 = RecurringTransaction(
        user_id=demo_user.id,
        category_id=cats.get(('expense', 'Subscriptions')).id,
        title='Netflix & Spotify Family',
        amount=1199.0,
        type='expense',
        frequency='monthly',
        start_date=today - timedelta(days=45),
        next_date=today + timedelta(days=8),
        payment_method='Credit Card',
        is_active=True,
        description='Digital media subscriptions'
    )
    db.session.add_all([r1, r2, r3])

    # 4. Realistic Transactions (Current month & Previous month)
    transactions = [
        # Current month incomes
        ('Tech Corp Monthly Salary', 115000.0, 'income', 'Salary', today.replace(day=1), 'Net Banking', 'Monthly primary salary'),
        ('UI/UX Design Consultation', 24000.0, 'income', 'Freelancing', today - timedelta(days=8), 'UPI', 'Client milestone payment'),
        ('Mutual Fund Dividend', 3500.0, 'income', 'Investments', today - timedelta(days=14), 'Net Banking', 'Quarterly index fund dividend'),
        
        # Current month expenses
        ('Apartment Rent', 22000.0, 'expense', 'Rent', today.replace(day=2), 'UPI', 'House rent paid to owner'),
        ('Whole Foods Grocery Market', 4850.0, 'expense', 'Food', today - timedelta(days=2), 'Credit Card', 'Weekly provisions and groceries'),
        ('Electricity & Water Bill', 3420.0, 'expense', 'Bills', today - timedelta(days=6), 'UPI', 'BESCOM & BWSSB utilities'),
        ('Metro & Uber Rides', 1450.0, 'expense', 'Transportation', today - timedelta(days=1), 'UPI', 'Work commute travel'),
        ('Zara Winter Wardrobe', 5200.0, 'expense', 'Shopping', today - timedelta(days=4), 'Credit Card', 'Seasonal clothing'),
        ('Weekend Bistro Dinner', 2650.0, 'expense', 'Food', today - timedelta(days=3), 'Credit Card', 'Dinner with college friends'),
        ('High-Speed Fiber Internet', 1299.0, 'expense', 'Bills', today - timedelta(days=10), 'UPI', 'Airtel Xstream broadband'),
        ('Health Checkup & Pharmacy', 1850.0, 'expense', 'Healthcare', today - timedelta(days=9), 'Debit Card', 'Annual preventive checkup'),
        ('Netflix & Spotify Subscription', 1199.0, 'expense', 'Subscriptions', today - timedelta(days=15), 'Credit Card', 'Streaming services'),
        ('Cinema & Popcorn', 950.0, 'expense', 'Entertainment', today - timedelta(days=7), 'UPI', 'Movie night with friends'),
        ('Organic Coffee Beans', 850.0, 'expense', 'Food', today - timedelta(days=11), 'UPI', 'Artisanal roast coffee'),

        # Previous month sample transactions (for MoM comparison)
        ('Tech Corp Monthly Salary', 115000.0, 'income', 'Salary', prev_month_date.replace(day=1), 'Net Banking', 'Prev month salary'),
        ('Freelance Website Redesign', 18000.0, 'income', 'Freelancing', prev_month_date.replace(day=12), 'UPI', 'Client contract'),
        ('Apartment Rent', 22000.0, 'expense', 'Rent', prev_month_date.replace(day=2), 'UPI', 'Prev rent'),
        ('Supermarket Groceries', 8900.0, 'expense', 'Food', prev_month_date.replace(day=10), 'Credit Card', 'Prev food'),
        ('Electricity Bill', 3100.0, 'expense', 'Bills', prev_month_date.replace(day=8), 'UPI', 'Prev bills'),
        ('Fuel & Commute', 3200.0, 'expense', 'Transportation', prev_month_date.replace(day=15), 'Credit Card', 'Prev transport'),
        ('Electronics & Gadgets', 12500.0, 'expense', 'Shopping', prev_month_date.replace(day=18), 'Credit Card', 'Noise cancelling headphones'),
    ]

    for title, amt, t_type, cat_name, t_date, method, desc in transactions:
        cat = cats.get((t_type, cat_name))
        tx = Transaction(
            user_id=demo_user.id,
            category_id=cat.id if cat else None,
            title=title,
            amount=amt,
            type=t_type,
            date=t_date,
            payment_method=method,
            description=desc
        )
        db.session.add(tx)

    # 5. Realistic In-App Notifications
    n1 = Notification(
        user_id=demo_user.id,
        title='Budget Alert: Food Spending',
        message='You have utilized 71% of your Food budget for this month. Slow down dining out to stay on target.',
        type='warning',
        is_read=False
    )
    n2 = Notification(
        user_id=demo_user.id,
        title='Upcoming Bill: Apartment Rent',
        message='Rent of ₹22,000 is scheduled due in 3 days. Please ensure sufficient account balance.',
        type='info',
        is_read=False
    )
    n3 = Notification(
        user_id=demo_user.id,
        title='Goal Milestone Achieved!',
        message='Congratulations! Your MacBook Pro M3 savings goal has reached 69.4% progress.',
        type='success',
        is_read=True
    )
    db.session.add_all([n1, n2, n3])
    db.session.commit()
    return demo_user
