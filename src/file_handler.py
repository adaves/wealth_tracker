import pandas as pd
from datetime import datetime
from decimal import Decimal
import os
from models.transaction import Transaction
import shutil
from typing import List

class FileHandler:
    def __init__(self, watch_dir='csv_files'):
        self.watch_dir = watch_dir
        self.processed_dir = os.path.join(watch_dir, 'csv_files_added')
        
        # Create directories if they don't exist
        os.makedirs(self.watch_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        
        self.account_handlers = {
            'pnc': self._process_pnc,
            'chase_sw': self._process_chase,
            'chase_star_wars': self._process_chase,
            'capital_one': self._process_capital_one
        }

    def get_pending_files(self):
        """Return list of unprocessed CSV/Excel files"""
        pending = []
        try:
            for file in os.listdir(self.watch_dir):
                # Skip the processed files directory
                if file == 'csv_files_added':
                    continue
                    
                if file.lower().endswith(('.csv', '.xlsx')):
                    file_path = os.path.join(self.watch_dir, file)
                    # Check if file is already processed
                    processed_path = os.path.join(self.processed_dir, file)
                    if not os.path.exists(processed_path):
                        account_type = self._detect_account_type(file_path)
                        if account_type:
                            pending.append({
                                'filename': file,
                                'path': file_path,
                                'account_type': account_type
                            })
        except Exception as e:
            print(f"Error getting pending files: {str(e)}")
            
        return pending

    def _detect_account_type(self, filepath):
        """Detect account type from file contents"""
        try:
            df = pd.read_csv(filepath, nrows=1)
            columns = set(df.columns)
            
            # PNC format
            if all(col in columns for col in ['Date', 'Description', 'Withdrawals', 'Deposits', 'Category', 'Balance']):
                return 'pnc'
            
            # Chase format (both SW and Star Wars)
            elif all(col in columns for col in ['Transaction Date', 'Post Date', 'Description', 'Category', 'Type', 'Amount', 'Memo']):
                if 'star_wars' in filepath.lower():
                    return 'chase_star_wars'
                return 'chase_sw'
            
            # Capital One format
            elif all(col in columns for col in ['Transaction Date', 'Posted Date', 'Card No.', 'Description', 'Category', 'Debit', 'Credit']):
                return 'capital_one'
            
            return None
        except Exception as e:
            print(f"Error detecting account type for {filepath}: {str(e)}")
            return None

    def _process_pnc(self, df):
        """Convert PNC format to standard format"""
        transactions = []
        for _, row in df.iterrows():
            try:
                # Clean currency values
                withdrawals = str(row['Withdrawals']).replace('$', '').replace(',', '') if pd.notnull(row['Withdrawals']) else '0'
                deposits = str(row['Deposits']).replace('$', '').replace(',', '') if pd.notnull(row['Deposits']) else '0'
                balance = str(row['Balance']).replace('$', '').replace(',', '')
                
                # Convert to Decimal
                amount = Decimal('0')
                if withdrawals != '0':
                    amount = -Decimal(withdrawals)
                elif deposits != '0':
                    amount = Decimal(deposits)
                
                transactions.append(Transaction(
                    date=self._parse_date(str(row['Date'])),
                    description=str(row['Description']).strip(),
                    amount=amount,
                    category=str(row['Category']).strip(),
                    account='PNC Checking',
                    balance=Decimal(balance)
                ))
            except Exception as e:
                print(f"Error processing PNC row: {str(e)}")
                print(f"Row data: {row.to_dict()}")
                continue
        return transactions

    def _process_chase(self, df, account_name):
        """Convert Chase format to standard format"""
        transactions = []
        for _, row in df.iterrows():
            try:
                # Clean amount
                amount_str = str(row['Amount']).replace('$', '').replace(',', '')
                amount = Decimal(amount_str)
                
                # Determine if debit based on Type
                # Chase marks purchases/payments as 'Sale' or 'Payment'
                if str(row['Type']).lower() in ['sale', 'payment']:
                    amount = -amount
                
                # Get description and memo
                description = str(row['Description']).strip()
                memo = str(row['Memo']).strip()
                
                # Combine description and memo if both exist
                if memo and memo != description:
                    description = f"{description} - {memo}"
                
                transactions.append(Transaction(
                    date=self._parse_date(str(row['Transaction Date'])),
                    description=description,
                    amount=amount,
                    category=str(row['Category']).strip(),
                    account=account_name
                ))
            except Exception as e:
                print(f"Error processing Chase row: {str(e)}")
                print(f"Row data: {row.to_dict()}")
                continue
        return transactions

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string in either MM/DD/YYYY or YYYY-MM-DD format"""
        try:
            # Try MM/DD/YYYY format first
            return datetime.strptime(date_str, '%m/%d/%Y')
        except ValueError:
            try:
                # Try YYYY-MM-DD format
                return datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                raise ValueError(f"Unable to parse date: {date_str}. Expected format: MM/DD/YYYY or YYYY-MM-DD")

    def _process_capital_one(self, df):
        """Convert Capital One format to standard format"""
        transactions = []
        for _, row in df.iterrows():
            try:
                # Use flexible date parser
                date = self._parse_date(row['Transaction Date'])
                
                amount = Decimal('0')
                if pd.notnull(row['Debit']):
                    amount = -Decimal(str(row['Debit']))
                elif pd.notnull(row['Credit']):
                    amount = Decimal(str(row['Credit']))
                
                transactions.append(Transaction(
                    date=date,
                    description=str(row['Description']).strip(),
                    amount=amount,
                    category=str(row['Category']).strip(),
                    account='Capital One'
                ))
            except Exception as e:
                print(f"Error processing Capital One row: {str(e)}")
                print(f"Row data: {row.to_dict()}")
                continue
            
        return transactions

    def process_file(self, file_info: dict, database) -> bool:
        """Process a file and move it to processed directory"""
        try:
            print(f"Starting to process file: {file_info['filename']}")
            
            # Begin database transaction
            with database.get_connection() as conn:
                # Process file first to validate
                df = pd.read_csv(file_info['path'])
                print(f"Read CSV file with {len(df)} rows")
                
                transactions = self._process_transactions(df, file_info['account_type'])
                print(f"Processed {len(transactions)} transactions")
                
                # Validate all transactions
                invalid_transactions = []
                for trans in transactions:
                    valid, error = self.validate_transaction(trans)
                    if not valid:
                        invalid_transactions.append((trans, error))
                
                if invalid_transactions:
                    error_msg = "\n".join([
                        f"Row {idx+1}: {error} (Amount: {t.amount}, Date: {t.date})"
                        for idx, (t, error) in enumerate(invalid_transactions)
                    ])
                    raise ValueError(f"Invalid transactions found:\n{error_msg}")
                
                # Create processed file record
                cursor = conn.execute('''
                    INSERT INTO processed_files (filename, account_id)
                    VALUES (?, (SELECT id FROM accounts WHERE name = ?))
                    RETURNING id
                ''', (file_info['filename'], self._get_account_name(file_info['account_type'])))
                
                file_id = cursor.fetchone()[0]
                print(f"Created processed_files record with ID: {file_id}")
                
                # Add transactions with file_id
                database.add_transactions_with_file(conn, transactions, file_id)
                print(f"Added {len(transactions)} transactions with file_id: {file_id}")
                
                # Move file to processed directory
                self._move_to_processed(file_info['path'])
                print(f"Moved file to processed directory")
                
                conn.commit()
                return True
                
        except Exception as e:
            print(f"Error processing file {file_info['filename']}: {str(e)}")
            if 'conn' in locals():
                conn.rollback()
            return False

    def _move_to_processed(self, file_path: str):
        """Move processed file to the processed directory"""
        filename = os.path.basename(file_path)
        processed_path = os.path.join(self.processed_dir, filename)
        
        # If file already exists in processed dir, add timestamp
        if os.path.exists(processed_path):
            base, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            processed_path = os.path.join(
                self.processed_dir, 
                f"{base}_{timestamp}{ext}"
            )
        
        shutil.move(file_path, processed_path)

    def _get_account_name(self, account_type: str) -> str:
        """Convert account type to account name"""
        account_map = {
            'pnc': 'PNC Checking',
            'chase_sw': 'Chase SW',
            'chase_star_wars': 'Chase Star Wars',
            'capital_one': 'Capital One'
        }
        return account_map.get(account_type)

    def _process_transactions(self, df: pd.DataFrame, account_type: str) -> List[Transaction]:
        """Process transactions based on account type"""
        if account_type == 'pnc':
            return self._process_pnc(df)
        elif account_type == 'chase_sw':
            return self._process_chase(df, 'Chase SW')
        elif account_type == 'chase_star_wars':
            return self._process_chase(df, 'Chase Star Wars')
        elif account_type == 'capital_one':
            return self._process_capital_one(df)
        else:
            raise ValueError(f"Unknown account type: {account_type}")

    def validate_transaction(self, trans: Transaction) -> tuple[bool, str]:
        """Validate a transaction before adding to database"""
        try:
            # Basic validation
            if not trans.description or len(trans.description.strip()) == 0:
                return False, "Description cannot be empty"
            
            if not trans.category or len(trans.category.strip()) == 0:
                return False, "Category cannot be empty"
            
            if not trans.amount:
                return False, "Amount cannot be zero"
            
            if not trans.date:
                return False, "Date is required"
            
            # Account-specific validation
            if trans.account == 'PNC Checking' and trans.balance is None:
                return False, "Balance is required for PNC transactions"
            
            # Date validation
            if trans.date > datetime.now():
                return False, "Transaction date cannot be in the future"
            
            # Amount validation (reasonable limits)
            if abs(trans.amount) > Decimal('50000'):
                return False, "Transaction amount exceeds reasonable limit"
            
            return True, ""
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def _add_transactions_with_file(self, conn, transactions: List[Transaction], file_id: int):
        """Add transactions with file_id to database"""
        account_map = {
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
                t.date,
                t.description,
                float(t.amount),
                t.category,
                float(t.balance) if t.balance else None
            )
            for t in transactions
        ])

    def restore_csv_file(self, filename: str) -> bool:
        """Move a file from processed directory back to watch directory"""
        try:
            source = os.path.join(self.processed_dir, filename)
            destination = os.path.join(self.watch_dir, filename)
            
            if os.path.exists(source):
                shutil.move(source, destination)
                print(f"Restored {filename} to watch directory")
                return True
            else:
                print(f"File not found: {source}")
                return False
            
        except Exception as e:
            print(f"Error restoring file {filename}: {str(e)}")
            return False

    def list_processed_files(self):
        """List all files in the processed directory"""
        print("\nFiles in processed directory:")
        try:
            for file in os.listdir(self.processed_dir):
                if file.lower().endswith(('.csv', '.xlsx')):
                    print(f"  {file}")
        except Exception as e:
            print(f"Error listing processed files: {str(e)}") 