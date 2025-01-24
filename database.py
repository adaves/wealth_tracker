import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name):
        self.db_name = db_name
        self.setup_database()

    def setup_database(self):
        """Create the database and tables if they don't exist"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    category TEXT,
                    account TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def add_transaction(self, date, description, amount, category, account):
        """Add a new transaction to the database"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (date, description, amount, category, account)
                VALUES (?, ?, ?, ?, ?)
            ''', (date, description, amount, category, account))
            conn.commit()

    def get_all_transactions(self):
        """Retrieve all transactions from the database"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM transactions ORDER BY date DESC')
            return cursor.fetchall()

    def clear_all_data(self):
        """Clear all data from the transactions table"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM transactions')
            conn.commit()

    def add_pnc_transaction(self, date, description, withdrawal, deposit, category, balance):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (date, description, amount, category, account)
                VALUES (?, ?, ?, ?, ?)
            ''', (date, description, withdrawal, category, 'PNC Checking'))
            cursor.execute('''
                INSERT INTO transactions (date, description, amount, category, account)
                VALUES (?, ?, ?, ?, ?)
            ''', (date, description, deposit, category, 'PNC Checking'))
            conn.commit()

    def add_capital_one_transaction(self, date, description, category, debit, credit):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (date, description, amount, category, account)
                VALUES (?, ?, ?, ?, ?)
            ''', (date, description, debit, category, 'Capital One'))
            cursor.execute('''
                INSERT INTO transactions (date, description, amount, category, account)
                VALUES (?, ?, ?, ?, ?)
            ''', (date, description, credit, category, 'Capital One'))
            conn.commit()

    def add_chase_transaction(self, date, description, category, type_, amount):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (date, description, amount, category, account)
                VALUES (?, ?, ?, ?, ?)
            ''', (date, description, amount, category, 'Chase'))
            conn.commit()

    def get_monthly_spending_by_category(self, year=None, month=None):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            query = '''
                SELECT 
                    strftime('%Y-%m', date) as month,
                    category,
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as spending
                FROM transactions
                WHERE amount < 0
            '''
            params = []
            if year:
                query += ' AND strftime("%Y", date) = ?'
                params.append(str(year))
            if month:
                query += ' AND strftime("%m", date) = ?'
                params.append(str(month).zfill(2))
            
            query += ' GROUP BY month, category ORDER BY month DESC, spending DESC'
            
            cursor.execute(query, params)
            return cursor.fetchall() 