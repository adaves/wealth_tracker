from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QLabel, QPushButton
)
from PyQt6.QtCore import Qt
from database import Database
from decimal import Decimal

class AccountWindow(QMainWindow):
    def __init__(self, database: Database, account_name: str):
        super().__init__()
        self.database = database
        self.account_name = account_name
        
        self.setWindowTitle(f"Spending Tracker - {account_name}")
        self.setMinimumSize(1000, 600)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Account header
        header = QLabel(account_name)
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Add refresh button
        refresh_btn = QPushButton("Refresh Transactions")
        refresh_btn.clicked.connect(self.load_transactions)
        layout.addWidget(refresh_btn)
        
        # Transaction table
        self.setup_transaction_table(layout)
        self.load_transactions()
    
    def setup_transaction_table(self, parent_layout):
        """Setup transaction display table"""
        self.transaction_table = QTableWidget()
        self.transaction_table.setColumnCount(5)
        
        # Set headers
        headers = ["Date", "Description", "Amount", "Category", "Balance"]
        self.transaction_table.setHorizontalHeaderLabels(headers)
        
        # Set table properties
        header = self.transaction_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Description column stretches
        for i in [0, 2, 3, 4]:  # Fixed width columns
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        # Style with better contrast
        self.transaction_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                alternate-background-color: #f7f7f7;
                color: #333333;  /* Dark gray text */
            }
            QHeaderView::section {
                background-color: #4a4a4a;  /* Dark header background */
                color: white;  /* White header text */
                padding: 5px;
                border: 1px solid #d0d0d0;
            }
            QTableWidget::item {
                color: #333333;  /* Dark gray text for items */
                padding: 2px;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;  /* Windows blue selection */
                color: white;
            }
        """)
        
        parent_layout.addWidget(self.transaction_table)

    def load_transactions(self):
        """Load transactions for this account"""
        self.transaction_table.setRowCount(0)
        transactions = self.database.get_account_transactions(self.account_name)
        
        for trans in transactions:
            row = self.transaction_table.rowCount()
            self.transaction_table.insertRow(row)
            
            # Date
            date_item = QTableWidgetItem(trans.date.strftime('%Y-%m-%d'))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.transaction_table.setItem(row, 0, date_item)
            
            # Description
            desc_item = QTableWidgetItem(trans.description)
            self.transaction_table.setItem(row, 1, desc_item)
            
            # Amount
            amount_str = f"${abs(trans.amount):,.2f}"
            if trans.is_debit:
                amount_str = f"-{amount_str}"
            amount_item = QTableWidgetItem(amount_str)
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            if trans.is_debit:
                amount_item.setForeground(Qt.GlobalColor.red)
            else:
                amount_item.setForeground(Qt.GlobalColor.darkGreen)
            self.transaction_table.setItem(row, 2, amount_item)
            
            # Category
            category_item = QTableWidgetItem(trans.category or "")
            self.transaction_table.setItem(row, 3, category_item)
            
            # Balance
            if trans.balance is not None:
                balance_item = QTableWidgetItem(f"${trans.balance:,.2f}")
                balance_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                self.transaction_table.setItem(row, 4, balance_item)
            else:
                self.transaction_table.setItem(row, 4, QTableWidgetItem(""))

    # ... rest of the AccountWindow implementation 