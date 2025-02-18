# Spending Tracker

A Python desktop application for tracking and visualizing personal spending across multiple bank accounts.

## Features

- **Multi-Bank Support**: Import transactions from multiple banks:
  - PNC Bank
  - Capital One
  - Chase

- **CSV Import**: Automatically process and import transaction data from bank CSV files
  - Detects bank type automatically
  - Moves processed files to a separate directory
  - Prevents duplicate imports

- **Transaction Management**:
  - View all transactions in a sortable table
  - Filter transactions by date and category
  - Clear all data with a single click

- **Analytics & Visualizations**:
  - Monthly spending trends
  - Spending distribution by account
  - Top spending categories
  - Year-over-year spending comparison with selectable years

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd spending-tracker
```

2. Create a virtual environment and activate it:
```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory:

```

spending_tracker/
├── src/
│   ├── __init__.py
│   ├── main.py           # Application entry point
│   ├── database.py       # Database operations
│   ├── file_handler.py   # CSV/Excel processing
│   ├── models/
│   │   ├── __init__.py
│   │   └── transaction.py
│   └── ui/
│       ├── __init__.py
│       └── main_window.py
├── data/
│   └── spending_tracker.db
└── requirements.txt