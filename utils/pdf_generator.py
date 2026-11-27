import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def generate_financial_pdf_report(user, transactions, metrics, date_range_label='Current Month'):
    """
    Generate an elegant, professional PDF statement using ReportLab.
    Adheres strictly to the Finora Powder Blue & Frost White palette.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom Color Palette
    c_primary = colors.HexColor('#789BB8')
    c_secondary = colors.HexColor('#344454')
    c_bg = colors.HexColor('#F3F7FA')
    c_border = colors.HexColor('#E1EAF0')
    c_income = colors.HexColor('#8EAD98')
    c_expense = colors.HexColor('#D59A9A')
    c_muted = colors.HexColor('#8799A8')

    # Typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=c_secondary,
        leading=28
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=c_muted,
        leading=14
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=c_secondary,
        leading=18,
        spaceAfter=8
    )
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=c_secondary,
        leading=12
    )
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=c_secondary,
        leading=12
    )

    # 1. Header Banner
    header_data = [
        [
            Paragraph("<b>FINORA</b>", title_style),
            Paragraph(f"<b>Financial Statement</b><br/><font color='#8799A8'>{date_range_label}</font>", ParagraphStyle('HRight', parent=subtitle_style, alignment=2))
        ],
        [
            Paragraph("Your Money. Your Control.", subtitle_style),
            Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}<br/>User: {user.name} ({user.email})", ParagraphStyle('SubRight', parent=subtitle_style, alignment=2))
        ]
    ]
    header_table = Table(header_data, colWidths=[3.5*inch, 4.0*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_border, spaceBefore=4, spaceAfter=14))

    # 2. Executive Financial Summary Cards Table
    sym = user.currency_symbol or '₹'
    summary_data = [
        ['Total Balance', 'Total Income', 'Total Expenses', 'Net Savings', 'Savings Rate'],
        [
            f"{sym}{metrics['total_balance']:,.2f}",
            f"{sym}{metrics['total_income']:,.2f}",
            f"{sym}{metrics['total_expenses']:,.2f}",
            f"{sym}{metrics['total_savings']:,.2f}",
            f"{metrics['savings_rate']}%"
        ]
    ]
    summary_table = Table(summary_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_bg),
        ('TEXTCOLOR', (0,0), (-1,0), c_muted),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,1), (-1,1), colors.white),
        ('TEXTCOLOR', (0,1), (0,1), c_secondary),
        ('TEXTCOLOR', (1,1), (1,1), c_income),
        ('TEXTCOLOR', (2,1), (2,1), c_expense),
        ('TEXTCOLOR', (3,1), (3,1), c_primary),
        ('FONTNAME', (0,1), (-1,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,1), 11),
        ('BOX', (0,0), (-1,-1), 1, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,1), (-1,1), 8),
        ('BOTTOMPADDING', (0,1), (-1,1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # 3. Category Spending Breakdown
    if metrics.get('category_breakdown'):
        story.append(Paragraph("Expense Category Breakdown", h2_style))
        cat_rows = [['Category', 'Amount', 'Distribution (%)']]
        for c in metrics['category_breakdown'][:8]:
            cat_rows.append([
                c['name'],
                f"{sym}{c['amount']:,.2f}",
                f"{c['percentage']}%"
            ])
        cat_table = Table(cat_rows, colWidths=[3.5*inch, 2.0*inch, 2.0*inch])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), c_bg),
            ('TEXTCOLOR', (0,0), (-1,0), c_secondary),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 20))

    # 4. Detailed Transaction Ledger
    story.append(Paragraph("Detailed Transaction History", h2_style))
    tx_rows = [['Date', 'Title', 'Category', 'Method', 'Type', 'Amount']]
    
    for t in transactions[:40]:  # up to 40 transactions in PDF
        is_inc = (t.type == 'income')
        amt_str = f"+{sym}{t.amount:,.2f}" if is_inc else f"-{sym}{t.amount:,.2f}"
        type_str = "Income" if is_inc else "Expense"
        
        tx_rows.append([
            t.date.strftime('%d-%b-%Y'),
            t.title[:28],
            t.category_name[:18],
            t.payment_method or 'UPI',
            type_str,
            amt_str
        ])

    if len(tx_rows) == 1:
        tx_rows.append(['-', 'No transactions recorded for this period', '-', '-', '-', '-'])

    tx_table = Table(tx_rows, colWidths=[1.1*inch, 2.2*inch, 1.4*inch, 1.0*inch, 0.8*inch, 1.0*inch])
    tx_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_bg),
        ('TEXTCOLOR', (0,0), (-1,0), c_secondary),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('ALIGN', (5,0), (5,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('FONTSIZE', (0,1), (-1,-1), 8),
    ]))
    story.append(tx_table)

    # Footer note
    story.append(Spacer(1, 20))
    story.append(Paragraph("This is an electronically generated statement from Finora Personal Finance Platform. Confidential.", subtitle_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
