import csv
import io

def generate_transactions_csv(transactions, currency_symbol='₹'):
    """
    Generate CSV data for the provided transactions.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Write headers
    writer.writerow([
        'Transaction ID',
        'Date',
        'Title',
        'Type',
        'Category',
        f'Amount ({currency_symbol})',
        'Payment Method',
        'Description',
        'Notes'
    ])

    for t in transactions:
        writer.writerow([
            t.id,
            t.date.strftime('%Y-%m-%d'),
            t.title,
            t.type.capitalize(),
            t.category_name,
            f"{t.amount:.2f}",
            t.payment_method or '',
            t.description or '',
            t.notes or ''
        ])

    output.seek(0)
    return output.getvalue()
