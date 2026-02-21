"""Paper trading account manager."""

from typing import Dict, List, Optional

from loguru import logger

from quantsys.data.database import Database

from .account import PaperAccount


class AccountManager:
    """Manage multiple paper trading accounts."""

    def __init__(self, database: Database) -> None:
        """Initialize account manager.

        Args:
            database: Database instance
        """
        self.db = database
        self._accounts: Dict[str, PaperAccount] = {}

    def create_account(self, name: str, initial_cash: float = 1_000_000.0) -> PaperAccount:
        """Create a new paper trading account.

        Args:
            name: Account name
            initial_cash: Initial cash balance

        Returns:
            Created account
        """
        # Check if name exists
        if self.get_account(name) is not None:
            raise ValueError(f"Account '{name}' already exists")

        # Create in database
        self.db.execute(
            """
            INSERT INTO paper_accounts (name, initial_cash, current_cash, positions)
            VALUES (?, ?, ?, ?)
            """,
            (name, initial_cash, initial_cash, "{}"),
        )

        # Load created account
        account = self._load_account(name)
        logger.info(f"Created paper account: {name} with ${initial_cash:,.2f}")
        return account

    def get_account(self, name: str) -> Optional[PaperAccount]:
        """Get account by name.

        Args:
            name: Account name

        Returns:
            Account or None if not found
        """
        # Check cache first
        if name in self._accounts:
            return self._accounts[name]

        # Load from database
        account = self._load_account(name)
        if account:
            self._accounts[name] = account
        return account

    def list_accounts(self) -> List[Dict]:
        """List all accounts.

        Returns:
            List of account summaries
        """
        rows = self.db.fetchall(
            "SELECT id, name, initial_cash, current_cash, created_at FROM paper_accounts"
        )

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "initial_cash": row["initial_cash"],
                "current_cash": row["current_cash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def delete_account(self, name: str) -> bool:
        """Delete an account.

        Args:
            name: Account name

        Returns:
            True if deleted
        """
        account = self.get_account(name)
        if not account:
            return False

        # Delete from database
        self.db.execute(
            "DELETE FROM paper_accounts WHERE name = ?",
            (name,),
        )

        # Remove from cache
        if name in self._accounts:
            del self._accounts[name]

        logger.info(f"Deleted paper account: {name}")
        return True

    def save_account(self, account: PaperAccount) -> None:
        """Save account state to database.

        Args:
            account: Account to save
        """
        import json

        positions = {
            symbol: {
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
            }
            for symbol, pos in account.positions.items()
        }

        self.db.execute(
            """
            UPDATE paper_accounts
            SET current_cash = ?, positions = ?
            WHERE name = ?
            """,
            (account.cash, json.dumps(positions), account.name),
        )

        logger.debug(f"Saved account state: {account.name}")

    def record_trade(
        self,
        account_id: int,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
    ) -> None:
        """Record a trade in the database.

        Args:
            account_id: Account ID
            symbol: Stock symbol
            side: "BUY" or "SELL"
            quantity: Number of shares
            price: Execution price
        """
        from datetime import datetime

        self.db.execute(
            """
            INSERT INTO paper_trades (account_id, symbol, side, quantity, price, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (account_id, symbol, side, quantity, price, datetime.now().isoformat()),
        )

    def get_trades(self, account_name: str, limit: int = 100) -> List[Dict]:
        """Get trade history for an account.

        Args:
            account_name: Account name
            limit: Maximum number of trades to return

        Returns:
            List of trade records
        """
        account = self.get_account(account_name)
        if not account:
            return []

        rows = self.db.fetchall(
            """
            SELECT symbol, side, quantity, price, timestamp
            FROM paper_trades
            WHERE account_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (account.account_id, limit),
        )

        return [
            {
                "symbol": row["symbol"],
                "side": row["side"],
                "quantity": row["quantity"],
                "price": row["price"],
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def _load_account(self, name: str) -> Optional[PaperAccount]:
        """Load account from database."""
        import json

        row = self.db.fetchone(
            "SELECT id, name, initial_cash, current_cash, positions FROM paper_accounts WHERE name = ?",
            (name,),
        )

        if not row:
            return None

        account = PaperAccount(
            account_id=row["id"],
            name=row["name"],
            initial_cash=row["initial_cash"],
        )
        account.cash = row["current_cash"]

        # Load positions
        try:
            positions_data = json.loads(row["positions"])
            for symbol, data in positions_data.items():
                from .account import Position

                account.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=data.get("quantity", 0),
                    avg_cost=data.get("avg_cost", 0.0),
                )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load positions for {name}: {e}")

        return account
