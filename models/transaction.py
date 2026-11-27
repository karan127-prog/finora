from datetime import datetime
from .database import db

class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'income' or 'expense'
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    payment_method = db.Column(db.String(50), default='UPI')  # UPI, Cash, Credit Card, Debit Card, Net Banking
    description = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def category_name(self):
        return self.category_rel.name if self.category_rel else 'Uncategorized'

    @property
    def category_icon(self):
        return self.category_rel.icon if self.category_rel else 'tag'

    @property
    def category_color(self):
        return self.category_rel.color if self.category_rel else '#A9C5DC'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'amount': self.amount,
            'type': self.type,
            'date': self.date.strftime('%Y-%m-%d'),
            'payment_method': self.payment_method,
            'category_id': self.category_id,
            'category_name': self.category_name,
            'category_icon': self.category_icon,
            'category_color': self.category_color,
            'description': self.description,
            'notes': self.notes
        }
