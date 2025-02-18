from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

@dataclass
class Transaction:
    date: datetime
    description: str
    amount: Decimal
    category: str
    account: str = None
    balance: Decimal = None
    id: int = None
    account_id: int = None
    file_id: int = None
    
    def __post_init__(self):
        """Validate and clean data after initialization"""
        # Ensure date is datetime
        if isinstance(self.date, str):
            self.date = datetime.strptime(self.date, '%Y-%m-%d')
            
        # Ensure amounts are Decimal
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        if self.balance and not isinstance(self.balance, Decimal):
            self.balance = Decimal(str(self.balance))
            
        # Clean strings
        self.description = str(self.description).strip()
        self.category = str(self.category).strip() if self.category else ''
    
    @property
    def is_debit(self) -> bool:
        """Return True if transaction is a debit (negative amount)"""
        return self.amount < 0

    @property
    def is_credit(self) -> bool:
        """Return True if transaction is a credit (positive amount)"""
        return self.amount > 0 