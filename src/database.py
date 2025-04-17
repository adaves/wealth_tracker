import sqlite3
from datetime import datetime
from decimal import Decimal
from models.transaction import Transaction
from typing import List, Dict, Optional, Any
from sqlite3 import Connection
from utils.logging_config import logger
import shutil
import os
from pathlib import Path

class Database:
    def __init__(self, db_path: str) -> None:
        """Initialize database with path to SQLite file"""
        self.db_path = db_path
        self.backup_dir = os.path.join(os.path.dirname(os.path.dirname(db_path)), 'data', 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)
        logger.info(f"Initializing database at {db_path}")
        
        # Initialize database if needed
        self._init_db()
    
    def get_connection(self) -> Connection:
        """Get a database connection"""
        logger.debug("Creating new database connection")
        return sqlite3.connect(self.db_path)
    
    def _init_db(self) -> None:
        """Initialize database tables if they don't exist"""
        logger.info("Initializing database tables")
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY,
                    filename TEXT NOT NULL,
                    account_id INTEGER NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES accounts (id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    file_id INTEGER,
                    date DATE NOT NULL,
                    description TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    category TEXT,
                    balance DECIMAL(10,2),
                    FOREIGN KEY (account_id) REFERENCES accounts (id),
                    FOREIGN KEY (file_id) REFERENCES processed_files (id)
                )
            ''')
            
            # Insert default accounts if they don't exist
            accounts: List[str] = [
                'PNC Checking',
                'Chase SW',
                'Chase Star Wars',
                'Capital One'
            ]
            
            for account in accounts:
                conn.execute('''
                    INSERT OR IGNORE INTO accounts (name) VALUES (?)
                ''', (account,))
            
            conn.commit()
            logger.info("Database tables initialized successfully")

    def get_account_transactions(self, account_name: str) -> List[Transaction]:
        """Get all transactions for a specific account"""
        logger.debug(f"Fetching transactions for account: {account_name}")
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    t.id,
                    t.date,
                    t.description,
                    t.amount,
                    t.category,
                    t.balance,
                    t.account_id,
                    t.file_id,
                    a.name as account
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE a.name = ?
                ORDER BY t.date DESC, t.id DESC
            ''', (account_name,))
            
            transactions: List[Transaction] = []
            for row in cursor.fetchall():
                transactions.append(Transaction(
                    id=row[0],
                    date=datetime.strptime(row[1], '%Y-%m-%d'),
                    description=row[2],
                    amount=Decimal(str(row[3])),
                    category=row[4],
                    balance=Decimal(str(row[5])) if row[5] is not None else None,
                    account_id=row[6],
                    file_id=row[7],
                    account=row[8]
                ))
            
            logger.info(f"Retrieved {len(transactions)} transactions for {account_name}")
            return transactions

    def get_pnc_ytd_average(self) -> Decimal:
        """Get the year-to-date average balance for PNC account"""
        logger.debug("Calculating PNC YTD average balance")
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT AVG(balance)
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE a.name = 'PNC Checking'
                AND date >= date('now', 'start of year')
                AND date <= date('now')
            ''')
            
            result: Optional[float] = cursor.fetchone()[0]
            average = Decimal(str(result)) if result is not None else Decimal('0')
            logger.info(f"PNC YTD average balance: ${average:,.2f}")
            return average

    def add_transactions_with_file(self, conn: Connection, transactions: List[Transaction], file_id: int) -> None:
        """Add transactions with file_id to database"""
        logger.debug(f"Adding {len(transactions)} transactions for file_id: {file_id}")
        account_map: Dict[str, int] = {
            name: id_ for id_, name in 
            conn.execute('SELECT id, name FROM accounts').fetchall()
        }
        
        conn.executemany('''
            INSERT INTO transactions 
            (account_id, file_id, date, description, amount, category, balance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [
            (
                account_map[t.account],
                file_id,
                t.date.strftime('%Y-%m-%d'),
                t.description,
                float(t.amount),
                t.category,
                float(t.balance) if t.balance else None
            )
            for t in transactions
        ])
        logger.info(f"Successfully added {len(transactions)} transactions")

    def undo_file_import(self, filename: str) -> bool:
        """Remove all transactions associated with a specific file"""
        logger.info(f"Attempting to undo import for file: {filename}")
        try:
            with self.get_connection() as conn:
                # Get file_id
                cursor = conn.execute(
                    'SELECT id FROM processed_files WHERE filename = ?',
                    (filename,)
                )
                result: Optional[tuple[int]] = cursor.fetchone()
                if not result:
                    logger.warning(f"File not found in processed_files: {filename}")
                    return False
                
                file_id: int = result[0]
                
                # Delete transactions
                conn.execute(
                    'DELETE FROM transactions WHERE file_id = ?',
                    (file_id,)
                )
                
                # Delete file record
                conn.execute(
                    'DELETE FROM processed_files WHERE id = ?',
                    (file_id,)
                )
                
                conn.commit()
                logger.info(f"Successfully undid import for file: {filename}")
                return True
                
        except Exception as e:
            logger.error(f"Error undoing file import: {str(e)}", exc_info=True)
            return False

    def get_processed_files(self) -> List[tuple[str, str, str, int]]:
        """Get list of processed files with their details"""
        logger.debug("Fetching processed files list")
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT 
                    f.filename,
                    a.name as account,
                    f.processed_at,
                    COUNT(t.id) as transaction_count
                FROM processed_files f
                JOIN accounts a ON f.account_id = a.id
                LEFT JOIN transactions t ON t.file_id = f.id
                GROUP BY f.id
                ORDER BY f.processed_at DESC
            ''')
            files = cursor.fetchall()
            logger.info(f"Retrieved {len(files)} processed files")
            return files

    def get_account_balance(self, account_name: str) -> Decimal:
        """Get current balance for an account"""
        logger.debug(f"Fetching current balance for account: {account_name}")
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT balance
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                WHERE a.name = ?
                ORDER BY date DESC, id DESC
                LIMIT 1
            ''', (account_name,))
            
            result: Optional[tuple[Optional[float]]] = cursor.fetchone()
            balance = Decimal(str(result[0])) if result and result[0] is not None else Decimal('0')
            logger.info(f"Current balance for {account_name}: ${balance:,.2f}")
            return balance

    def get_all_account_balances(self) -> Dict[str, Decimal]:
        """Get current balances for all accounts"""
        logger.debug("Fetching balances for all accounts")
        balances: Dict[str, Decimal] = {}
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT a.name, t.balance
                FROM accounts a
                LEFT JOIN (
                    SELECT account_id, balance
                    FROM transactions
                    WHERE (account_id, date) IN (
                        SELECT account_id, MAX(date)
                        FROM transactions
                        GROUP BY account_id
                    )
                ) t ON a.id = t.account_id
            ''')
            
            for name, balance in cursor.fetchall():
                balances[name] = Decimal(str(balance)) if balance is not None else Decimal('0')
            
            logger.info("Retrieved balances for all accounts")
            return balances

    def debug_print_transactions(self) -> None:
        """Debug method to print all transactions in database"""
        logger.debug("Printing database contents for debugging")
        with self.get_connection() as conn:
            print("\n=== Database Contents ===")
            
            # Print accounts with transaction counts
            cursor = conn.execute('''
                SELECT 
                    a.id, 
                    a.name, 
                    COUNT(t.id) as transaction_count
                FROM accounts a
                LEFT JOIN transactions t ON a.id = t.account_id
                GROUP BY a.id, a.name
                ORDER BY a.id
            ''')
            accounts: List[tuple[int, str, int]] = cursor.fetchall()
            print("\nAccounts and Transaction Counts:")
            for id, name, count in accounts:
                print(f"  {id}: {name} - {count} transactions")
            
            # Print transactions
            cursor = conn.execute('''
                SELECT t.id, a.name, t.date, t.description, t.amount, t.balance
                FROM transactions t
                JOIN accounts a ON t.account_id = a.id
                ORDER BY a.name, t.date DESC
            ''')
            transactions: List[tuple[int, str, str, str, float, Optional[float]]] = cursor.fetchall()
            print("\nTransactions:")
            for t in transactions:
                print(f"  {t[1]} - {t[2]}: {t[3]} (${t[4]}) Balance: ${t[5] or 'N/A'}")
            
            print("\n======================")
            logger.debug("Finished printing database contents")

    def check_database_integrity(self) -> None:
        """Check database tables and data integrity"""
        logger.info("Starting database integrity check")
        with self.get_connection() as conn:
            print("\n=== Database Integrity Check ===")
            
            # Check tables exist
            tables: List[tuple[str]] = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """).fetchall()
            
            print("\nDatabase Tables:")
            for table in tables:
                table_name: str = table[0]
                row_count: int = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                print(f"  {table_name}: {row_count} rows")
            
            # Check processed files
            print("\nProcessed Files:")
            cursor = conn.execute("""
                SELECT 
                    f.filename,
                    a.name as account,
                    f.processed_at,
                    COUNT(t.id) as transaction_count
                FROM processed_files f
                JOIN accounts a ON f.account_id = a.id
                LEFT JOIN transactions t ON t.file_id = f.id
                GROUP BY f.id
                ORDER BY f.processed_at DESC
            """)
            
            for row in cursor.fetchall():
                print(f"  {row[0]} ({row[1]}) - {row[3]} transactions")
            
            print("\n=============================")
            logger.info("Completed database integrity check")

    def create_backup(self) -> str:
        """
        Create a backup of the database file with timestamp.
        Returns the path to the backup file.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"spending_tracker_{timestamp}.db"
        backup_path = os.path.join(self.backup_dir, backup_filename)
        
        try:
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Created database backup at: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}", exc_info=True)
            raise

    def restore_from_backup(self, backup_path: str) -> bool:
        """
        Restore the database from a backup file.
        Returns True if successful, False otherwise.
        """
        if not os.path.exists(backup_path):
            logger.error(f"Backup file not found: {backup_path}")
            return False
            
        try:
            # Create a backup of current database before restoring
            current_backup = self.create_backup()
            logger.info(f"Created backup of current database before restore: {current_backup}")
            
            # Close any existing connections
            if hasattr(self, '_connection') and self._connection:
                self._connection.close()
            
            # Copy backup file to current database location
            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Successfully restored database from backup: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore from backup: {str(e)}", exc_info=True)
            return False

    def get_available_backups(self) -> List[Dict[str, Any]]:
        """
        Get a list of available backups with their metadata.
        Returns a list of dictionaries containing:
        - path: full path to backup file
        - filename: name of backup file
        - timestamp: datetime object of when backup was created
        - size: size of backup file in bytes
        """
        backups = []
        try:
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('spending_tracker_') and filename.endswith('.db'):
                    filepath = os.path.join(self.backup_dir, filename)
                    # Extract timestamp from filename
                    timestamp_str = filename.replace('spending_tracker_', '').replace('.db', '')
                    try:
                        timestamp = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        backups.append({
                            'path': filepath,
                            'filename': filename,
                            'timestamp': timestamp,
                            'size': os.path.getsize(filepath)
                        })
                    except ValueError:
                        logger.warning(f"Could not parse timestamp from backup filename: {filename}")
                        continue
            
            # Sort backups by timestamp (newest first)
            backups.sort(key=lambda x: x['timestamp'], reverse=True)
            return backups
            
        except Exception as e:
            logger.error(f"Error listing backups: {str(e)}", exc_info=True)
            return []

    def cleanup_old_backups(self) -> None:
        """
        Remove old backups, keeping only the 2 most recent ones.
        """
        try:
            backups = self.get_available_backups()
            if len(backups) <= 2:
                logger.info("No backups to clean up - keeping all backups")
                return

            # Keep the 2 most recent backups
            backups_to_keep = backups[:2]
            backups_to_delete = backups[2:]

            for backup in backups_to_delete:
                try:
                    os.remove(backup['path'])
                    logger.info(f"Deleted old backup: {backup['filename']}")
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup['filename']}: {str(e)}", exc_info=True)

            logger.info(f"Cleanup complete. Kept {len(backups_to_keep)} most recent backups.")
        except Exception as e:
            logger.error(f"Error during backup cleanup: {str(e)}", exc_info=True)

    def schedule_weekly_backup(self) -> None:
        """
        Schedule weekly backups for Monday at 5:30 AM.
        The backup will run when the computer is next available if it misses the scheduled time.
        """
        try:
            import schedule
            import time
            from threading import Thread

            def backup_job():
                """Job to run backup and cleanup"""
                try:
                    logger.info("Running scheduled weekly backup")
                    self.create_backup()
                    self.cleanup_old_backups()
                except Exception as e:
                    logger.error(f"Error in scheduled backup job: {str(e)}", exc_info=True)

            # Schedule backup for Monday at 5:30 AM
            schedule.every().monday.at("05:30").do(backup_job)

            def run_scheduler():
                """Run the scheduler in a separate thread"""
                while True:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute

            # Start scheduler in a daemon thread
            scheduler_thread = Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            logger.info("Weekly backup scheduler started (Mondays at 5:30 AM)")

        except ImportError:
            logger.error("schedule package not installed. Please install it with: pip install schedule")
        except Exception as e:
            logger.error(f"Error setting up backup scheduler: {str(e)}", exc_info=True) 