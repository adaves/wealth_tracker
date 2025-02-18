from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QListWidget, QFrame, QMessageBox,
    QInputDialog
)
from PyQt6.QtCore import Qt
from file_handler import FileHandler
from database import Database
from .account_window import AccountWindow
import os
import shutil

class MainWindow(QMainWindow):
    def __init__(self, database: Database):
        super().__init__()
        self.database = database
        self.file_handler = FileHandler()
        self.account_windows = {}  # Store references to account windows
        
        self.setWindowTitle("Spending Tracker")
        self.setMinimumSize(800, 600)
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Top section with PNC balance
        self.setup_balance_section(layout)
        
        # Middle section with file handling
        self.setup_file_section(layout)
        
        # Account navigation section
        self.setup_account_navigation(layout)
        
        # Initial refresh
        self.refresh_pending_files()
        self.update_pnc_balance()

    def setup_balance_section(self, parent_layout):
        """Setup PNC balance display section"""
        balance_frame = QFrame()
        balance_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        balance_layout = QHBoxLayout(balance_frame)
        
        self.balance_label = QLabel("PNC Average Balance (YTD): $0.00")
        self.balance_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                padding: 20px;
            }
        """)
        balance_layout.addWidget(self.balance_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        parent_layout.addWidget(balance_frame)

    def setup_file_section(self, parent_layout):
        """Setup file handling section"""
        file_frame = QFrame()
        file_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        file_layout = QHBoxLayout(file_frame)
        
        # Pending files list
        self.pending_files = QListWidget()
        self.pending_files.setMaximumHeight(150)
        file_layout.addWidget(self.pending_files, stretch=2)
        
        # Buttons
        button_layout = QVBoxLayout()
        load_button = QPushButton("Load Selected File")
        load_button.clicked.connect(self.load_selected_file)
        refresh_button = QPushButton("Refresh File List")
        refresh_button.clicked.connect(self.refresh_pending_files)
        undo_button = QPushButton("Undo Last Import")
        undo_button.clicked.connect(self.undo_last_import)
        history_button = QPushButton("View History")
        history_button.clicked.connect(self.show_history)
        restore_button = QPushButton("Restore Processed File")
        restore_button.clicked.connect(self.restore_processed_file)
        
        button_layout.addWidget(load_button)
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(undo_button)
        button_layout.addWidget(history_button)
        button_layout.addWidget(restore_button)
        button_layout.addStretch()
        
        file_layout.addLayout(button_layout, stretch=1)
        parent_layout.addWidget(file_frame)

    def setup_account_navigation(self, parent_layout):
        """Setup account navigation buttons"""
        nav_frame = QFrame()
        nav_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        nav_layout = QVBoxLayout(nav_frame)
        
        # Title
        title = QLabel("Account Navigation")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        nav_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Account buttons
        accounts = [
            ("PNC Checking", "background-color: #e3f2fd;"),
            ("Chase SW", "background-color: #fff3e0;"),
            ("Chase Star Wars", "background-color: #fce4ec;"),
            ("Capital One", "background-color: #e8f5e9;")
        ]
        
        for account, style in accounts:
            btn = QPushButton(account)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: %s;
                    padding: 20px;
                    font-size: 14px;
                    color: #000000;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                }
            """ % style)
            btn.clicked.connect(lambda checked, a=account: self.open_account_view(a))
            nav_layout.addWidget(btn)
        
        parent_layout.addWidget(nav_frame)

    def refresh_pending_files(self):
        """Update the list of pending files"""
        self.pending_files.clear()
        for file in self.file_handler.get_pending_files():
            self.pending_files.addItem(f"{file['filename']} ({file['account_type']})")

    def load_selected_file(self):
        """Process the selected file"""
        current_item = self.pending_files.currentItem()
        if not current_item:
            return
            
        # Find file info from selection
        filename = current_item.text().split(" (")[0]
        file_info = None
        for file in self.file_handler.get_pending_files():
            if file['filename'] == filename:
                file_info = file
                break
        
        if file_info:
            try:
                if self.file_handler.process_file(file_info, self.database):
                    self.refresh_pending_files()
                    self.update_pnc_balance()
                    
                    # Refresh any open account windows
                    for account, window in self.account_windows.items():
                        window.load_transactions()
                    
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Successfully processed {filename}"
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Failed to process {filename}\n\n"
                        "Check the console for detailed error information."
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Error processing {filename}:\n\n{str(e)}"
                )

    def open_account_view(self, account):
        """Open the account-specific window"""
        # Create new window if not exists, or bring existing to front
        if account not in self.account_windows:
            self.account_windows[account] = AccountWindow(self.database, account)
        
        window = self.account_windows[account]
        window.show()
        window.activateWindow()  # Bring to front

    def update_pnc_balance(self):
        """Update the displayed PNC balance"""
        balance = self.database.get_pnc_ytd_average()
        if balance:
            self.balance_label.setText(f"PNC Average Balance (YTD): ${balance:,.2f}")

    def undo_last_import(self):
        """Undo the last file import"""
        # Show file selection dialog
        files = []
        with self.database.get_connection() as conn:
            cursor = conn.execute('''
                SELECT filename FROM processed_files 
                ORDER BY processed_at DESC
            ''')
            files = [row[0] for row in cursor.fetchall()]
        
        if not files:
            QMessageBox.information(
                self,
                "No Files",
                "No processed files found to undo."
            )
            return
        
        # Let user select file to undo
        file_to_undo, ok = QInputDialog.getItem(
            self,
            "Select File to Undo",
            "Choose file import to undo:",
            files,
            0,  # Current item
            False  # Not editable
        )
        
        if ok and file_to_undo:
            # Try to undo the import
            if self.database.undo_file_import(file_to_undo):
                # Move file back from processed directory
                processed_path = os.path.join(
                    self.file_handler.processed_dir,
                    file_to_undo
                )
                if os.path.exists(processed_path):
                    shutil.move(
                        processed_path,
                        os.path.join(self.file_handler.watch_dir, file_to_undo)
                    )
                
                self.refresh_pending_files()
                self.update_pnc_balance()
                QMessageBox.information(
                    self,
                    "Success",
                    f"Successfully undid import of {file_to_undo}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to undo import of {file_to_undo}"
                )

    def show_history(self):
        """Show the processing history window"""
        from .processing_history import ProcessingHistory
        history_window = ProcessingHistory(self.database, self)
        history_window.show()

    def restore_processed_file(self):
        """Restore a processed file for reimport"""
        # Get list of processed files
        files = []
        processed_dir = os.path.join(self.file_handler.watch_dir, 'csv_files_added')
        if os.path.exists(processed_dir):
            files = [f for f in os.listdir(processed_dir) 
                    if f.lower().endswith(('.csv', '.xlsx'))]
        
        if not files:
            QMessageBox.information(
                self,
                "No Files",
                "No processed files found to restore."
            )
            return
        
        # Let user select file to restore
        file_to_restore, ok = QInputDialog.getItem(
            self,
            "Select File to Restore",
            "Choose file to move back to watch directory:",
            files,
            0,  # Current item
            False  # Not editable
        )
        
        if ok and file_to_restore:
            if self.file_handler.restore_csv_file(file_to_restore):
                self.refresh_pending_files()
                QMessageBox.information(
                    self,
                    "Success",
                    f"Restored {file_to_restore} for reimport"
                ) 