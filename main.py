import tkinter as tk
from tkinter import ttk, messagebox
import os
from dotenv import load_dotenv
from database import Database
from csv_handler import CSVHandler, load_csv_files
from visualizations import VisualizationManager

class SpendingTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Spending Tracker")
        self.root.geometry("1200x800")

        # Load environment variables
        load_dotenv()
        
        # Initialize database and handlers
        self.db = Database(os.getenv('DATABASE_NAME'))
        self.csv_handler = CSVHandler(self.db)
        self.viz_manager = VisualizationManager(self.db)
        self.viz_manager.parent_app = self
        
        self.setup_ui()
        self.load_transactions()

    def setup_ui(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Transactions tab
        self.transactions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.transactions_frame, text='Transactions')
        self.setup_transactions_tab()

        # Analytics tab
        self.analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analytics_frame, text='Analytics')
        self.setup_analytics_tab()

    def setup_transactions_tab(self):
        # Create button frame
        button_frame = ttk.Frame(self.transactions_frame)
        button_frame.pack(pady=10)

        # Add Check for New Files button
        check_button = ttk.Button(
            button_frame, 
            text="Check for New Files",
            command=self.check_for_new_files
        )
        check_button.pack(side='left', padx=5)

        # Add Clear Data button
        clear_button = ttk.Button(
            button_frame,
            text="Clear All Data",
            command=self.clear_data
        )
        clear_button.pack(side='left', padx=5)

        # Create transaction table
        columns = ('Date', 'Description', 'Amount', 'Category', 'Account')
        self.tree = ttk.Treeview(self.transactions_frame, columns=columns, show='headings')
        
        # Set column headings
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.transactions_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Pack everything
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_analytics_tab(self):
        # Add filter frame at the top
        filter_frame = self.viz_manager.create_filter_frame(self.analytics_frame)
        
        # Create frames for each chart
        charts_frame = ttk.Frame(self.analytics_frame)
        charts_frame.pack(fill='both', expand=True)

        # Create 2x2 grid for charts
        for i in range(2):
            charts_frame.grid_columnconfigure(i, weight=1)
            charts_frame.grid_rowconfigure(i, weight=1)

        # Monthly spending chart
        monthly_frame = ttk.LabelFrame(charts_frame, text="Monthly Spending")
        monthly_frame.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        monthly_chart = self.viz_manager.create_monthly_spending_chart(monthly_frame)
        monthly_chart.pack(fill='both', expand=True)

        # Account distribution chart
        account_frame = ttk.LabelFrame(charts_frame, text="Spending by Account")
        account_frame.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
        account_chart = self.viz_manager.create_spending_by_account(account_frame)
        account_chart.pack(fill='both', expand=True)

        # Top categories chart
        categories_frame = ttk.LabelFrame(charts_frame, text="Top Spending Categories")
        categories_frame.grid(row=1, column=0, padx=5, pady=5, sticky='nsew')
        categories_chart = self.viz_manager.create_top_categories(categories_frame)
        categories_chart.pack(fill='both', expand=True)

        # Year comparison chart
        yearly_frame = ttk.LabelFrame(charts_frame, text="Year-over-Year Comparison")
        yearly_frame.grid(row=1, column=1, padx=5, pady=5, sticky='nsew')
        yearly_chart = self.viz_manager.create_year_comparison(yearly_frame)
        yearly_chart.pack(fill='both', expand=True)

        # Add refresh button
        refresh_button = ttk.Button(
            self.analytics_frame,
            text="Refresh Charts",
            command=self.refresh_charts
        )
        refresh_button.pack(pady=5)

    def refresh_charts(self):
        self.notebook.forget(1)  # Remove analytics tab
        self.analytics_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.analytics_frame, text='Analytics')
        self.setup_analytics_tab()

    def load_transactions(self):
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Load transactions from database
        transactions = self.db.get_all_transactions()
        for transaction in transactions:
            self.tree.insert('', 'end', values=transaction[1:6])  # Exclude ID and created_at

    def check_for_new_files(self):
        csv_directory = os.getenv('CSV_WATCH_DIRECTORY', 'csv_files')  # Default to 'csv_files' if not set
        
        # Ensure the directory exists
        if not os.path.exists(csv_directory):
            os.makedirs(csv_directory)
        
        # Process both direct files and files in subdirectories
        processed_files = []
        for root, dirs, files in os.walk(csv_directory):
            for file in files:
                if file.endswith('.CSV') or file.endswith('.csv'):
                    file_path = os.path.join(root, file)
                    if self.csv_handler.process_csv(file_path):
                        processed_files.append(file)
        
        if processed_files:
            messagebox.showinfo(
                "Success", 
                f"Processed {len(processed_files)} files: \n{', '.join(processed_files)}"
            )
            self.load_transactions()
        else:
            messagebox.showinfo("Info", "No new CSV files found")

    def clear_data(self):
        """Clear all data from database with confirmation"""
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all transaction data?"):
            self.db.clear_all_data()
            self.load_transactions()  # Refresh the transaction list
            self.refresh_charts()     # Refresh the charts
            messagebox.showinfo("Success", "All data has been cleared")

def main():
    try:
        root = tk.Tk()
        app = SpendingTrackerApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Error: {str(e)}")
        return

if __name__ == "__main__":
    main() 