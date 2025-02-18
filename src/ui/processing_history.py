from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton
)
from PyQt6.QtCore import Qt
from database import Database
from datetime import datetime

class ProcessingHistory(QMainWindow):
    def __init__(self, database: Database, parent=None):
        super().__init__(parent)
        self.database = database
        
        self.setWindowTitle("File Processing History")
        self.setMinimumSize(800, 400)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create history table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels([
            "Filename", "Account", "Processed Date", "Transaction Count"
        ])
        
        # Set table properties
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in [1, 2, 3]:
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.history_table)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.load_history)
        layout.addWidget(refresh_btn)
        
        # Load initial data
        self.load_history()
    
    def load_history(self):
        """Load processing history from database"""
        with self.database.get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    f.filename,
                    a.name as account,
                    strftime('%Y-%m-%d %H:%M:%S', f.processed_at) as processed_at,
                    COUNT(t.id) as transaction_count
                FROM processed_files f
                JOIN accounts a ON f.account_id = a.id
                LEFT JOIN transactions t ON t.file_id = f.id
                GROUP BY f.id
                ORDER BY f.processed_at DESC
            ''')
            
            history = cursor.fetchall()
            self.history_table.setRowCount(len(history))
            
            for row, (filename, account, processed_at, count) in enumerate(history):
                # Filename
                self.history_table.setItem(row, 0, QTableWidgetItem(filename))
                
                # Account
                self.history_table.setItem(row, 1, QTableWidgetItem(account))
                
                # Date
                date_item = QTableWidgetItem(processed_at)  # Already formatted by SQLite
                date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history_table.setItem(row, 2, date_item)
                
                # Count
                count_item = QTableWidgetItem(str(count))
                count_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                self.history_table.setItem(row, 3, count_item) 