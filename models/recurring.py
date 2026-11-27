from datetime import datetime
from .database import db

class RecurringTransaction(db.Model):
    __tablename__ = 'recurring_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'income' or 'expense'
    frequency = db.Column(db.String(20), nullable=False)  # 'daily', 'weekly', 'monthly', 'yearly'
    start_date = db.Column(db.Date, nullable=False)
    next_date = db.Column(db.Date, nullable=False)
    payment_method = db.Column(db.String(50), default='Net Banking')
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def category_name(self):
        return self.category_rel.name if self.category_rel else 'Uncategorized'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'amount': self.amount,
            'type': self.type,
            'frequency': self.frequency,
            'category_id': self.category_id,
            'category_name': self.category_name,
            'start_date': self.start_date.strftime('%Y-%m-%d'),
            'next_date': self.next_date.strftime('%Y-%m-%d'),
            'payment_method': self.payment_method,
            'is_active': self.is_active,
            'description': self.description
        }
