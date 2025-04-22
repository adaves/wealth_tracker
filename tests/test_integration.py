import unittest
import os
import sys
import time
import uuid
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from datetime import datetime, timedelta
from decimal import Decimal
from models.transaction import Transaction
from database import Database
from file_handler import FileHandler
from main import main
import shutil

class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment for all tests"""
        # Create QApplication instance
        cls.app = QApplication(sys.argv)
        
        # Create unique test directories
        cls.test_id = str(uuid.uuid4())
        cls.test_db_path = f"test_spending_tracker_{cls.test_id}.db"
        cls.test_dir = f"test_csv_files_{cls.test_id}"
        cls.test_processed_dir = f"test_processed_files_{cls.test_id}"

    def setUp(self):
        """Set up test environment for each test"""
        # Clean up any existing files
        self._cleanup_files()
        
        # Create test directories
        os.makedirs(self.test_dir, exist_ok=True)
        os.makedirs(self.test_processed_dir, exist_ok=True)
        
        # Initialize components
        self.database = Database(self.test_db_path)
        self.file_handler = FileHandler(
            watch_dir=self.test_dir,
            processed_dir=self.test_processed_dir
        )

    def tearDown(self):
        """Clean up test environment after each test"""
        # Close database connection
        if hasattr(self, 'database'):
            self.database.close()
        
        # Clean up files
        self._cleanup_files()

    def _cleanup_files(self):
        """Helper method to clean up test files"""
        # Remove test database file
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        # Remove test directories
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(self.test_processed_dir):
            shutil.rmtree(self.test_processed_dir)

    def test_file_import_and_export(self):
        """Test the complete workflow of importing and exporting transactions"""
        # Create test transactions
        test_transactions = [
            Transaction(
                date=datetime.now() - timedelta(days=i),
                description=f"Test Transaction {i}",
                amount=Decimal(f"{i+1}.00"),
                category="Test",
                account="Test Account"
            )
            for i in range(5)
        ]
        
        # Add transactions to database
        with self.database.get_connection() as conn:
            self.database.add_transactions_with_file(conn, test_transactions, 1)
        
        # Export transactions
        export_path = os.path.join(self.test_dir, "export_test.csv")
        success = self.database.export_transactions_to_csv(
            output_path=export_path,
            start_date=datetime.now() - timedelta(days=10),
            end_date=datetime.now()
        )
        
        self.assertTrue(success)
        self.assertTrue(os.path.exists(export_path))
        
        # Verify exported file contents
        with open(export_path, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 6)  # Header + 5 transactions

    def test_account_balance_updates(self):
        """Test that account balances are updated correctly after transactions"""
        # Get initial balance
        initial_balance = self.database.get_account_balance("Test Account")
        
        # Add test transaction
        test_transaction = Transaction(
            date=datetime.now(),
            description="Balance Test",
            amount=Decimal("100.00"),
            category="Test",
            account="Test Account"
        )
        
        with self.database.get_connection() as conn:
            self.database.add_transactions_with_file(conn, [test_transaction], 1)
        
        # Verify balance update
        new_balance = self.database.get_account_balance("Test Account")
        self.assertEqual(new_balance, initial_balance + Decimal("100.00"))

    def test_date_range_filtering(self):
        """Test that date range filtering works across components"""
        # Create test transactions with different dates
        test_transactions = [
            Transaction(
                date=datetime.now() - timedelta(days=i),
                description=f"Date Test {i}",
                amount=Decimal("10.00"),
                category="Test",
                account="Test Account"
            )
            for i in range(10)
        ]
        
        # Add transactions
        with self.database.get_connection() as conn:
            self.database.add_transactions_with_file(conn, test_transactions, 1)
        
        # Test date range filtering
        start_date = datetime.now() - timedelta(days=5)
        end_date = datetime.now() - timedelta(days=2)
        
        filtered_transactions = self.database.get_transactions_by_date_range(
            start_date=start_date,
            end_date=end_date
        )
        
        self.assertEqual(len(filtered_transactions), 4)  # Days 2-5 inclusive

    def test_undo_import_workflow(self):
        """Test the complete workflow of importing and undoing an import"""
        # Create test file
        test_file = os.path.join(self.test_dir, "test_import.csv")
        with open(test_file, 'w') as f:
            f.write("Date,Description,Amount,Category,Account\n")
            f.write(f"{datetime.now().strftime('%Y-%m-%d')},Test,10.00,Test,Test Account\n")
        
        # Process file
        self.file_handler.process_file(test_file, self.database)
        
        # Verify transaction was added
        transactions = self.database.get_transactions_by_date_range(
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now() + timedelta(days=1)
        )
        self.assertEqual(len(transactions), 1)
        
        # Undo import
        success = self.database.undo_file_import("test_import.csv")
        self.assertTrue(success)
        
        # Verify transaction was removed
        transactions = self.database.get_transactions_by_date_range(
            start_date=datetime.now() - timedelta(days=1),
            end_date=datetime.now() + timedelta(days=1)
        )
        self.assertEqual(len(transactions), 0)

if __name__ == '__main__':
    unittest.main() 