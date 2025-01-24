import pandas as pd
import os
from datetime import datetime
import shutil

class CSVHandler:
    def __init__(self, database):
        self.database = database
        self.processed_files_dir = 'csv_files_added'
        self.processed_files = set()
        self.initialize_processed_files_tracking()

    def initialize_processed_files_tracking(self):
        # Create processed files directory if it doesn't exist
        csv_dir = os.getenv('CSV_WATCH_DIRECTORY')
        self.processed_files_dir = os.path.join(csv_dir, 'csv_files_added')
        if not os.path.exists(self.processed_files_dir):
            os.makedirs(self.processed_files_dir)

    def clean_currency(self, value):
        """Convert currency string to float."""
        if pd.isna(value) or value == '':
            return None
        if isinstance(value, (int, float)):
            return float(value)
        # Remove currency symbols, spaces, and commas
        cleaned = str(value).replace('$', '').replace(',', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            print(f"Could not convert value '{value}' to float")
            return None

    def process_pnc_csv(self, df):
        for _, row in df.iterrows():
            # Remove $ and , from currency strings
            withdrawal = self.clean_currency(row['Withdrawals'])
            deposit = self.clean_currency(row['Deposits'])
            
            # Convert withdrawal to negative number if it exists
            amount = -withdrawal if withdrawal else deposit
            
            self.database.add_transaction(
                date=datetime.strptime(row['Date'], '%m/%d/%Y').strftime('%Y-%m-%d'),
                description=row['Description'],
                amount=amount,
                category=row['Category'],
                account="PNC"
            )

    def process_capital_one_csv(self, df):
        for _, row in df.iterrows():
            # Handle debit (negative) and credit (positive) amounts
            debit = self.clean_currency(row['Debit'])
            credit = self.clean_currency(row['Credit'])
            
            # Use debit (as negative) or credit
            amount = -debit if debit else credit
            
            self.database.add_transaction(
                date=datetime.strptime(row['Transaction Date'], '%m/%d/%Y').strftime('%Y-%m-%d'),
                description=row['Description'],
                amount=amount,
                category=row['Category'],
                account="Capital One"
            )

    def process_chase_csv(self, df):
        for _, row in df.iterrows():
            self.database.add_chase_transaction(
                date=datetime.strptime(row['Transaction Date'], '%m/%d/%Y'),
                description=row['Description'],
                category=row['Category'],
                type_=row['Type'],
                amount=self.clean_currency(row['Amount'])
            )

    def detect_csv_type(self, df):
        """Detect the type of CSV file based on columns"""
        # Print columns for debugging
        print(f"Found columns: {df.columns.tolist()}")
        
        # Chase format
        chase_cols = ['Transaction Date', 'Post Date', 'Description', 'Category', 'Type', 'Amount']
        if all(col in df.columns for col in chase_cols):
            return 'chase'
        
        # PNC format
        pnc_cols = ['Date', 'Description', 'Withdrawals', 'Deposits', 'Category', 'Balance']
        if all(col in df.columns for col in pnc_cols):
            return 'pnc'
        
        # Capital One format
        cap_one_cols = ['Transaction Date', 'Posted Date', 'Card No.', 'Description', 'Category', 'Debit', 'Credit']
        if all(col in df.columns for col in cap_one_cols):
            return 'capital_one'
        
        # If no match, raise error with helpful message
        raise ValueError(f"Unknown CSV format. Expected one of:\n"
                        f"Chase columns: {chase_cols}\n"
                        f"PNC columns: {pnc_cols}\n"
                        f"Capital One columns: {cap_one_cols}\n"
                        f"Found columns: {df.columns.tolist()}")

    def is_file_processed(self, file_path):
        """Check if a file has already been processed by looking in the processed files directory."""
        file_name = os.path.basename(file_path)
        processed_path = os.path.join(self.processed_files_dir, file_name)
        return os.path.exists(processed_path)

    def move_to_processed(self, file_path):
        """Move a processed file to the processed files directory."""
        file_name = os.path.basename(file_path)
        processed_path = os.path.join(self.processed_files_dir, file_name)
        
        # If file already exists in processed directory, add timestamp to filename
        if os.path.exists(processed_path):
            base, ext = os.path.splitext(file_name)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_name = f"{base}_{timestamp}{ext}"
            processed_path = os.path.join(self.processed_files_dir, new_name)
        
        shutil.move(file_path, processed_path)

    def process_file(self, file_path):
        """Alias for process_csv to maintain compatibility"""
        return self.process_csv(file_path)

    def process_csv(self, file_path):
        try:
            # Check if file has already been processed
            if self.is_file_processed(file_path):
                print(f"File {os.path.basename(file_path)} has already been processed")
                return False

            df = pd.read_csv(file_path)
            csv_type = self.detect_csv_type(df)
            
            if csv_type == 'pnc':
                self.process_pnc_csv(df)
            elif csv_type == 'capital_one':
                self.process_capital_one_csv(df)
            elif csv_type == 'chase':
                self.process_chase_csv(df)
            else:
                print(f"Unsupported file format: {file_path}")
                return False
            
            # Move file to processed directory
            self.move_to_processed(file_path)
            return True
            
        except Exception as e:
            print(f"Error processing CSV file: {str(e)}")
            return False

    def check_directory_for_new_files(self, directory):
        processed_files = []
        for filename in os.listdir(directory):
            if filename.endswith('.csv'):
                file_path = os.path.join(directory, filename)
                if self.process_csv(file_path):
                    processed_files.append(filename)
        return processed_files

def load_csv_files(csv_dir='csv_files'):
    """
    Load and validate Chase CSV statement files from the specified directory
    
    Args:
        csv_dir (str): Directory containing the CSV files
        
    Returns:
        pd.DataFrame: Combined dataframe of all valid statement data
    """
    # Create list to hold valid dataframes
    dfs = []
    
    # Get all CSV files in directory
    csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.CSV')]
    
    for filename in csv_files:
        try:
            # Load CSV file
            filepath = os.path.join(csv_dir, filename)
            df = pd.read_csv(filepath)
            
            # Validate required columns exist
            required_cols = ['Transaction Date', 'Post Date', 'Description', 
                           'Category', 'Type', 'Amount']
            if not all(col in df.columns for col in required_cols):
                print(f"Warning: {filename} missing required columns - skipping")
                continue
                
            # Convert date columns to datetime
            df['Transaction Date'] = pd.to_datetime(df['Transaction Date'])
            df['Post Date'] = pd.to_datetime(df['Post Date'])
            
            # Only include transactions up to current date
            today = datetime.now()
            df = df[df['Transaction Date'] <= today]
            
            # Add source filename column
            df['Source'] = filename
            
            dfs.append(df)
            
        except Exception as e:
            print(f"Error loading {filename}: {str(e)}")
            continue
            
    if not dfs:
        raise ValueError("No valid CSV files found")
        
    # Combine all dataframes
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Sort by transaction date
    combined_df = combined_df.sort_values('Transaction Date')
    
    return combined_df 