from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, SavingsGoal, SavingsContribution, Notification

savings_bp = Blueprint('savings', __name__)

@savings_bp.route('/savings')
@login_required
def index():
    today = date.today()
    status_filter = request.args.get('status', 'all')

    query = SavingsGoal.query.filter_by(user_id=current_user.id)
    if status_filter == 'in_progress':
        query = query.filter(SavingsGoal.status == 'in_progress', SavingsGoal.current_amount < SavingsGoal.target_amount)
    elif status_filter == 'completed':
        query = query.filter((SavingsGoal.status == 'completed') | (SavingsGoal.current_amount >= SavingsGoal.target_amount))

    all_user_goals = SavingsGoal.query.filter_by(user_id=current_user.id).order_by(SavingsGoal.created_at.desc()).all()
    goals = query.order_by(SavingsGoal.created_at.desc()).all()

    # Portfolio metrics (calculated over all goals)
    total_target = sum(g.target_amount for g in all_user_goals)
    total_saved = sum(g.current_amount for g in all_user_goals)
    total_remaining = max(0.0, total_target - total_saved)
    overall_progress = round((total_saved / total_target * 100), 1) if total_target > 0 else 0
    completed_count = sum(1 for g in all_user_goals if g.status == 'completed' or g.current_amount >= g.target_amount)
    in_progress_count = len(all_user_goals) - completed_count

    # Enrich goals with actionable analytics
    goal_cards = []
    for g in goals:
        days_left = (g.target_date - today).days
        is_completed = (g.status == 'completed' or g.current_amount >= g.target_amount)
        
        # Monthly recommended savings rate
        if not is_completed and days_left > 0:
            months_remaining = max(1.0, days_left / 30.4)
            monthly_recommended = round(g.remaining_amount / months_remaining, 2)
        else:
            monthly_recommended = 0.0

        # Contributions for history drawer
        contribs = g.contributions.order_by(SavingsContribution.date.desc(), SavingsContribution.id.desc()).all()

        goal_cards.append({
            'goal': g,
            'days_left': days_left,
            'is_completed': is_completed,
            'monthly_recommended': monthly_recommended,
            'contributions': contribs,
            'contribution_count': len(contribs)
        })

    # Recent contributions across all goals
    recent_contributions = SavingsContribution.query.join(SavingsGoal).filter(
        SavingsGoal.user_id == current_user.id
    ).order_by(SavingsContribution.date.desc(), SavingsContribution.id.desc()).limit(8).all()

    today_str = today.strftime('%Y-%m-%d')

    return render_template(
        'savings/index.html',
        goal_cards=goal_cards,
        status_filter=status_filter,
        total_target=total_target,
        total_saved=total_saved,
        total_remaining=total_remaining,
        overall_progress=overall_progress,
        completed_count=completed_count,
        in_progress_count=in_progress_count,
        recent_contributions=recent_contributions,
        today_str=today_str
    )

@savings_bp.route('/savings/add', methods=['POST'])
@login_required
def add():
    name = request.form.get('name', '').strip()
    target_str = request.form.get('target_amount', '0')
    current_str = request.form.get('current_amount', '0')
    date_str = request.form.get('target_date')
    icon = request.form.get('icon', 'target')
    color = request.form.get('color', '#789BB8')

    if not name:
        flash('Goal title is required.', 'danger')
        return redirect(url_for('savings.index'))

    try:
        target_amount = float(target_str)
        current_amount = float(current_str)
        if target_amount <= 0 or current_amount < 0:
            raise ValueError()
    except ValueError:
        flash('Please enter valid positive target amounts.', 'danger')
        return redirect(url_for('savings.index'))

    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today() + timedelta(days=90)
    except ValueError:
        target_date = date.today() + timedelta(days=90)

    status = 'completed' if current_amount >= target_amount else 'in_progress'

    goal = SavingsGoal(
        user_id=current_user.id,
        name=name,
        target_amount=target_amount,
        current_amount=current_amount,
        target_date=target_date,
        icon=icon,
        color=color,
        status=status
    )
    db.session.add(goal)
    db.session.flush()

    # Log initial opening deposit if > 0
    if current_amount > 0:
        init_contrib = SavingsContribution(
            goal_id=goal.id,
            amount=current_amount,
            date=date.today(),
            notes='Initial Opening Deposit'
        )
        db.session.add(init_contrib)

    db.session.commit()

    flash(f'Savings goal "{name}" of {current_user.currency_symbol}{target_amount:,.2f} created successfully.', 'success')
    return redirect(url_for('savings.index'))

@savings_bp.route('/savings/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    goal = SavingsGoal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    name = request.form.get('name', '').strip()
    target_str = request.form.get('target_amount', '0')
    date_str = request.form.get('target_date')
    icon = request.form.get('icon', goal.icon)
    color = request.form.get('color', goal.color)

    if not name:
        flash('Goal title cannot be empty.', 'danger')
        return redirect(url_for('savings.index'))

    try:
        target_amount = float(target_str)
        if target_amount <= 0:
            raise ValueError()
    except ValueError:
        flash('Target amount must be a positive number.', 'danger')
        return redirect(url_for('savings.index'))

    if date_str:
        try:
            goal.target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    goal.name = name
    goal.target_amount = target_amount
    goal.icon = icon
    goal.color = color
    goal.status = 'completed' if goal.current_amount >= target_amount else 'in_progress'

    db.session.commit()
    flash(f'Goal "{name}" updated successfully.', 'success')
    return redirect(url_for('savings.index'))

@savings_bp.route('/savings/contribute/<int:id>', methods=['POST'])
@login_required
def contribute(id):
    goal = SavingsGoal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    amount_str = request.form.get('amount', '0')
    notes = request.form.get('notes', 'Savings Contribution').strip()
    date_str = request.form.get('date', date.today().strftime('%Y-%m-%d'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        flash('Please enter a valid positive contribution amount.', 'danger')
        return redirect(url_for('savings.index'))

    try:
        contrib_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        contrib_date = date.today()

    goal.current_amount += amount

    # Check for goal completion
    was_completed = (goal.status == 'completed')
    if goal.current_amount >= goal.target_amount:
        goal.status = 'completed'
        if not was_completed:
            # Trigger milestone notification
            milestone_notif = Notification(
                user_id=current_user.id,
                title=f'Savings Milestone: {goal.name} Reached!',
                message=f'Congratulations! You achieved your target of {current_user.currency_symbol}{goal.target_amount:,.2f} for "{goal.name}".',
                type='success'
            )
            db.session.add(milestone_notif)

    contrib = SavingsContribution(
        goal_id=goal.id,
        amount=amount,
        date=contrib_date,
        notes=notes or 'Periodic Savings Deposit'
    )
    db.session.add(contrib)
    db.session.commit()

    flash(f'Deposited {current_user.currency_symbol}{amount:,.2f} towards "{goal.name}"! New progress: {goal.progress_percentage}%.', 'success')
    return redirect(url_for('savings.index'))

@savings_bp.route('/savings/withdraw/<int:id>', methods=['POST'])
@login_required
def withdraw(id):
    goal = SavingsGoal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    amount_str = request.form.get('amount', '0')
    notes = request.form.get('notes', 'Capital Withdrawal').strip()

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError()
        if amount > goal.current_amount:
            flash(f'Cannot withdraw more than current saved amount ({current_user.currency_symbol}{goal.current_amount:,.2f}).', 'danger')
            return redirect(url_for('savings.index'))
    except ValueError:
        flash('Please enter a valid withdrawal amount.', 'danger')
        return redirect(url_for('savings.index'))

    goal.current_amount -= amount
    if goal.current_amount < goal.target_amount:
        goal.status = 'in_progress'

    contrib = SavingsContribution(
        goal_id=goal.id,
        amount=-amount,
        date=date.today(),
        notes=notes or 'Capital Withdrawal'
    )
    db.session.add(contrib)
    db.session.commit()

    flash(f'Withdrew {current_user.currency_symbol}{amount:,.2f} from "{goal.name}".', 'info')
    return redirect(url_for('savings.index'))

@savings_bp.route('/savings/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    goal = SavingsGoal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    name = goal.name
    db.session.delete(goal)
    db.session.commit()
    flash(f'Savings goal "{name}" deleted.', 'info')
    return redirect(url_for('savings.index'))
