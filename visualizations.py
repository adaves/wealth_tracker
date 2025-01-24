import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import seaborn as sns
from datetime import datetime, timedelta
import pandas as pd
import tkinter as tk
from tkinter import ttk
from matplotlib.dates import DateFormatter
import mplcursors
import sqlite3

class VisualizationManager:
    def __init__(self, database):
        self.database = database
        self.selected_categories = []
        self.date_range = {'start': None, 'end': None}
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = [10, 6]

    def refresh_charts(self):
        # This method will be called when filters are applied
        # We'll need to update all charts with the new filtered data
        if hasattr(self, 'parent_app') and hasattr(self.parent_app, 'refresh_charts'):
            self.parent_app.refresh_charts()

    def create_filter_frame(self, parent):
        filter_frame = ttk.LabelFrame(parent, text="Filters")
        filter_frame.pack(fill='x', padx=5, pady=5)

        # Date range filters
        date_frame = ttk.Frame(filter_frame)
        date_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(date_frame, text="Date Range:").pack(side='left')
        
        ranges = ["Last 30 Days", "Last 3 Months", "Last 6 Months", "Last Year", "All Time"]
        self.date_var = tk.StringVar(value="Last 3 Months")
        date_combo = ttk.Combobox(date_frame, values=ranges, textvariable=self.date_var)
        date_combo.pack(side='left', padx=5)
        date_combo.bind('<<ComboboxSelected>>', self.update_date_range)

        # Category filter
        cat_frame = ttk.Frame(filter_frame)
        cat_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(cat_frame, text="Categories:").pack(side='left')
        
        # Get unique categories from database
        categories = self.get_unique_categories()
        self.category_vars = {cat: tk.BooleanVar(value=True) for cat in categories}
        
        cat_select_frame = ttk.Frame(cat_frame)
        cat_select_frame.pack(fill='x', padx=5)
        
        # Create scrollable frame for categories
        canvas = tk.Canvas(cat_select_frame, height=100)
        scrollbar = ttk.Scrollbar(cat_select_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Add checkboxes for categories
        for i, cat in enumerate(categories):
            ttk.Checkbutton(
                scrollable_frame, 
                text=cat, 
                variable=self.category_vars[cat],
                command=self.update_selected_categories
            ).grid(row=i//3, column=i%3, sticky='w', padx=5)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Apply filters button
        ttk.Button(
            filter_frame, 
            text="Apply Filters", 
            command=self.refresh_charts
        ).pack(pady=5)

        return filter_frame

    def get_unique_categories(self):
        query = "SELECT DISTINCT category FROM all_transactions WHERE category IS NOT NULL"
        with sqlite3.connect(self.database.db_name) as conn:
            df = pd.read_sql_query(query, conn)
        return sorted(df['category'].tolist())

    def update_date_range(self, event=None):
        today = datetime.now()
        range_map = {
            "Last 30 Days": (today - timedelta(days=30), today),
            "Last 3 Months": (today - timedelta(days=90), today),
            "Last 6 Months": (today - timedelta(days=180), today),
            "Last Year": (today - timedelta(days=365), today),
            "All Time": (None, None)
        }
        self.date_range['start'], self.date_range['end'] = range_map[self.date_var.get()]

    def update_selected_categories(self):
        self.selected_categories = [
            cat for cat, var in self.category_vars.items() 
            if var.get()
        ]

    def apply_filters_to_query(self, query):
        conditions = []
        params = []

        # Date range filter
        if self.date_range['start']:
            conditions.append("transaction_date >= ?")
            params.append(self.date_range['start'].strftime('%Y-%m-%d'))
        if self.date_range['end']:
            conditions.append("transaction_date <= ?")
            params.append(self.date_range['end'].strftime('%Y-%m-%d'))

        # Category filter
        if self.selected_categories:
            conditions.append(f"category IN ({','.join(['?']*len(self.selected_categories))})")
            params.extend(self.selected_categories)

        if conditions:
            if 'WHERE' in query:
                query += f" AND {' AND '.join(conditions)}"
            else:
                query += f" WHERE {' AND '.join(conditions)}"

        return query, params

    def create_monthly_spending_chart(self, frame):
        try:
            # Get last 12 months of spending by category
            data = self.database.get_monthly_spending_by_category()
            if not data:  # Check if data is empty
                return self._create_no_data_message(frame, "No monthly spending data available")
            
            df = pd.DataFrame(data, columns=['month', 'category', 'spending'])
            if df.empty or df['spending'].sum() == 0:
                return self._create_no_data_message(frame, "No spending data to display")
            
            # Create figure
            fig, ax = plt.subplots()
            pivot_table = df.pivot_table(
                values='spending',
                index='month',
                columns='category',
                aggfunc='sum'
            ).fillna(0)
            
            pivot_table.plot(kind='bar', stacked=True, ax=ax)
            plt.title('Monthly Spending by Category')
            plt.xlabel('Month')
            plt.ylabel('Amount ($)')
            plt.xticks(rotation=45)
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            
            # Add tooltips
            cursor = mplcursors.cursor(pivot_table.plot(), hover=True)
            @cursor.connect("add")
            def on_add(sel):
                sel.annotation.set_text(
                    f'Category: {sel.artist.get_label()}\n'
                    f'Month: {pivot_table.index[sel.target.index]}\n'
                    f'Amount: ${sel.target.get_ydata():,.2f}'
                )
            
            return self._embed_chart(fig, frame)
        except Exception as e:
            return self._create_no_data_message(frame, f"Error creating chart: {str(e)}")

    def create_spending_by_account(self, frame):
        try:
            with sqlite3.connect(self.database.db_name) as conn:
                df = pd.read_sql_query('''
                    SELECT 
                        account,
                        SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_spending
                    FROM all_transactions
                    GROUP BY account
                ''', conn)
            
            if df.empty or df['total_spending'].sum() == 0:
                return self._create_no_data_message(frame, "No spending data by account available")
            
            fig, ax = plt.subplots()
            plt.pie(df['total_spending'], labels=df['account'], autopct='%1.1f%%')
            plt.title('Spending Distribution by Account')
            
            return self._embed_chart(fig, frame)
        except Exception as e:
            return self._create_no_data_message(frame, f"Error creating chart: {str(e)}")

    def create_top_categories(self, frame):
        try:
            query = '''
                SELECT 
                    category,
                    SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_spending
                FROM all_transactions
                WHERE amount < 0
                GROUP BY category
                ORDER BY total_spending DESC
                LIMIT 10
            '''
            with sqlite3.connect(self.database.db_name) as conn:
                df = pd.read_sql_query(query, conn)
            
            if df.empty or df['total_spending'].sum() == 0:
                return self._create_no_data_message(frame, "No category spending data available")
            
            fig, ax = plt.subplots()
            sns.barplot(data=df, x='total_spending', y='category', ax=ax)
            plt.title('Top 10 Spending Categories')
            plt.xlabel('Total Spending ($)')
            
            return self._embed_chart(fig, frame)
        except Exception as e:
            return self._create_no_data_message(frame, f"Error creating chart: {str(e)}")

    def create_year_comparison(self, frame):
        try:
            current_year = datetime.now().year
            with sqlite3.connect(self.database.db_name) as conn:
                df = pd.read_sql_query('''
                    SELECT 
                        strftime('%m', transaction_date) as month,
                        strftime('%Y', transaction_date) as year,
                        SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_spending
                    FROM all_transactions
                    WHERE year IN (?, ?)
                    GROUP BY year, month
                    ORDER BY month
                ''', conn, params=[str(current_year), str(current_year-1)])
            
            if df.empty or df['total_spending'].sum() == 0:
                return self._create_no_data_message(frame, "No year comparison data available")
            
            fig, ax = plt.subplots()
            for year in df['year'].unique():
                year_data = df[df['year'] == year]
                plt.plot(year_data['month'], year_data['total_spending'], 
                        label=year, marker='o')
            
            plt.title('Year-over-Year Spending Comparison')
            plt.xlabel('Month')
            plt.ylabel('Total Spending ($)')
            plt.legend()
            
            return self._embed_chart(fig, frame)
        except Exception as e:
            return self._create_no_data_message(frame, f"Error creating chart: {str(e)}")

    def _create_no_data_message(self, frame, message):
        label = ttk.Label(frame, text=message)
        label.pack(expand=True)
        return label

    def _embed_chart(self, fig, frame):
        canvas = FigureCanvasTkAgg(fig, frame)
        canvas.draw()
        
        # Add navigation toolbar
        toolbar = NavigationToolbar2Tk(canvas, frame)
        toolbar.update()
        
        widget = canvas.get_tk_widget()
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        plt.close(fig)
        return widget 