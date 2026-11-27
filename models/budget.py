from datetime import datetime
from .database import db

class Budget(db.Model):
    __tablename__ = 'budgets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # Format 'YYYY-MM', e.g. '2026-11'
    limit_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'category_id', 'month', name='uq_user_category_month'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'category_id': self.category_id,
            'category_name': self.category_rel.name if self.category_rel else 'Unknown',
            'month': self.month,
            'limit_amount': self.limit_amount
        }
