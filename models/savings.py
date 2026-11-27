from datetime import datetime
from .database import db

class SavingsGoal(db.Model):
    __tablename__ = 'savings_goals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date = db.Column(db.Date, nullable=False)
    icon = db.Column(db.String(50), default='target')
    color = db.Column(db.String(20), default='#789BB8')
    status = db.Column(db.String(20), default='in_progress')  # 'in_progress', 'completed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contributions = db.relationship('SavingsContribution', backref='goal', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def progress_percentage(self):
        if self.target_amount <= 0:
            return 100.0
        pct = (self.current_amount / self.target_amount) * 100
        return min(round(pct, 1), 100.0)

    @property
    def remaining_amount(self):
        rem = self.target_amount - self.current_amount
        return max(0.0, rem)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'target_amount': self.target_amount,
            'current_amount': self.current_amount,
            'remaining_amount': self.remaining_amount,
            'progress_percentage': self.progress_percentage,
            'target_date': self.target_date.strftime('%Y-%m-%d'),
            'icon': self.icon,
            'color': self.color,
            'status': self.status
        }

class SavingsContribution(db.Model):
    __tablename__ = 'savings_contributions'

    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('savings_goals.id', ondelete='CASCADE'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
