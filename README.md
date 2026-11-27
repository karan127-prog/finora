# FINORA — Personal Finance & Budget Management SaaS Platform
> **Tagline:** *"Your Money. Your Control."*

FINORA is a modern, full-stack personal finance and budget management platform inspired by premier SaaS banking and budgeting tools. It combines the aesthetic elegance of modern fintech applications with comprehensive personal financial tracking.

---

## 🎨 Design Identity & Color System
Finora is built around a bespoke **Powder Blue + Frost White + Muted Silver** palette:

| Variable | Hex Value | Purpose |
|---|---|---|
| `--background` | `#F3F7FA` | Frost white canvas |
| `--sidebar` | `#E6EFF6` | Powder blue navigation pane |
| `--card` | `#FFFFFF` | Rounded surface cards |
| `--primary` | `#A9C5DC` | Soft powder accent |
| `--secondary` | `#789BB8` | Elegant steel/slate highlight |
| `--accent` | `#C5D2DC` | Subtle dividers & hovers |
| `--text-primary` | `#344454` | High-contrast deep slate text |
| `--text-secondary`| `#8799A8` | Muted subtitle text |
| `--income` | `#8EAD98` | Sage green positive inflows |
| `--expense` | `#D59A9A` | Soft rose expenditures |
| `--warning` | `#D6B77A` | Amber budget alert threshold |
| `--border` | `#E1EAF0` | Thin elegant borders |

---

## 🚀 Key Features

### 1. Financial Overview Dashboard
- **4 Main KPI Cards:** Total Balance, Total Income, Total Expenses, and Total Savings in INR (₹) with month-over-month percentage changes and visual trend badges.
- **Financial Overview:** Interactive Bar Chart comparing monthly cash inflow vs outflow with monthly/yearly view toggle.
- **Expense Breakdown:** Interactive Doughnut Chart showing category-wise spending distribution.
- **Budget Utilization:** Real-time allocated budget, spent, remaining safe buffer, and progress bar.
- **Savings Goals:** Active milestones with target dates and visual completion meters.
- **Recent Transactions:** Recent transaction ledger with instant status indicators.
- **Dynamic Smart Insights:** Automatically calculated from real transaction data (e.g., highest spending category, monthly savings rate, budget warnings).

### 2. Transaction Management
- Add, Edit, Delete transactions.
- Multi-parameter filtering: Keyword search, transaction type (income/expense), category, and date range.
- Sorting by date and amount with pagination.
- Support for multiple payment methods: UPI, Credit Card, Debit Card, Net Banking, and Cash.

### 3. Income & Expense Management
- Dedicated views with category distribution, monthly totals, and velocity analysis.
- Standard categories:
  - **Income:** Salary, Freelancing, Business, Pocket Money, Investments, Gifts, Other Income.
  - **Expense:** Food, Shopping, Transportation, Education, Entertainment, Healthcare, Bills, Rent, Travel, Subscriptions, Other Expenses.

### 4. Category-Wise Budget Planner
- Create monthly spending limits per category.
- Live warning indicators:
  - `< 70%`: Healthy / On Track (Sage Green)
  - `70% - 90%`: Approaching Limit (Amber Warning)
  - `90% - 100%`: Critical Warning
  - `> 100%`: Budget Exceeded (Rose Danger)

### 5. Savings Goals
- Set targets for Emergency Funds, Tech Purchases, Vacations, etc.
- Interactive "Add Money" modal with contribution history and progress calculation.

### 6. Recurring Transactions & Due Bill Processing
- Manage daily, weekly, monthly, and yearly recurring payments.
- Next due date tracking.
- One-click "Process Due Payments" button that creates actual transactions and advances the due date without duplicates.

### 7. Interactive Financial Calendar
- Month-by-month calendar grid displaying daily income sums (+₹), expense sums (-₹), and upcoming bill alerts.
- Click any date to view all transactions and scheduled events for that day.

### 8. Official Reports & Exports
- **PDF Financial Statements:** Formatted report generated via **ReportLab** matching Finora's brand aesthetic.
- **CSV Data Export:** Complete transaction ledgers ready for spreadsheet analysis.

### 9. Authentication & Multi-User Security
- Secure registration & login with password hashing via **Werkzeug**.
- Session management via **Flask-Login**.
- Per-user data isolation.
- **One-Click Instant Demo Access** pre-loaded with realistic portfolio data.

---

## 💻 Tech Stack
- **Backend:** Python Flask
- **ORM / Database:** Flask-SQLAlchemy with MySQL support (PyMySQL) and automatic, seamless SQLite fallback (`finora.db`).
- **Frontend:** HTML5, CSS3, JavaScript, Chart.js, Lucide Icons, Plus Jakarta Sans & Inter typography.
- **Reports:** ReportLab (PDF generation) & Python CSV.

---

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.10+ (Python 3.14 recommended)
- Optional: MySQL server

### 1. Clone or Open Project Directory
```powershell
cd C:\Users\KARAN\.gemini\antigravity\scratch\finora
```

### 2. Install Dependencies
```powershell
py -m pip install -r requirements.txt
```

### 3. Database Configuration
By default, FINORA automatically initializes an SQLite database (`finora.db`) if MySQL is not configured. To connect to MySQL:
Create a `.env` file from `.env.example`:
```env
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/finora_db
```

### 4. Run the Application
```powershell
py app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

### 5. Demo Account Credentials
- **Email:** `demo@finora.app`
- **Password:** `password123`
*(Or simply click the "One-Click Instant Demo Access" button on the sign-in page!)*
