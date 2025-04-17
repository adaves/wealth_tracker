import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from database import Database
from dotenv import load_dotenv
import os
from utils.logging_config import logger

def main(test_db_path: str = None) -> None:
    """Main application entry point"""
    try:
        logger.info("Starting Wealth Tracker application")
        
        # Load environment variables
        load_dotenv()
        logger.debug("Loaded environment variables")
        
        # Initialize database
        if test_db_path:
            db_path = test_db_path
        else:
            # Use production database path
            db_path: str = os.getenv('DATABASE_NAME', 'spending_tracker.db')
            if not os.path.isabs(db_path):
                # Make path relative to project root
                db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
        
        logger.info(f"Initializing database at: {db_path}")
        database: Database = Database(db_path)
        
        # Start backup scheduler
        database.schedule_weekly_backup()
        
        # Create application
        logger.debug("Creating QApplication instance")
        app: QApplication = QApplication(sys.argv)
        
        # Create and show main window
        logger.debug("Creating main window")
        window: MainWindow = MainWindow(database)
        window.show()
        
        logger.info("Application started successfully")
        
        # Start event loop
        sys.exit(app.exec())
        
    except Exception as e:
        logger.critical(f"Application failed to start: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 