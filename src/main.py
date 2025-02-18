import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from database import Database
from dotenv import load_dotenv
import os

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize database in project root
    db_path = os.getenv('DATABASE_NAME', 'spending_tracker.db')
    if not os.path.isabs(db_path):
        # Make path relative to project root
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
    
    database = Database(db_path)
    
    # Create application
    app = QApplication(sys.argv)
    
    # Create and show main window
    window = MainWindow(database)
    window.show()
    
    # Start event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 