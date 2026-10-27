from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Any


@dataclass(frozen=True)
class Listing:
    id: int
    seller_id: int
    seller_name: str
    seller_username: str | None
    seller_chat_id: int
    seller_business_connection_id: str
    gift_url: str
    gift_name: str
    gift_number: int
    language: str
    amount: int | float
    currency: str
    created_at: datetime
    active: bool


@dataclass(frozen=True)
class Offer:
    id: int
    business_connection_id: str
    chat_id: int
    source_message_id: int
    buyer_id: int
    buyer_name: str
    buyer_username: str | None
    gift_url: str
    gift_name: str
    gift_number: int
    language: str
    amount: int | float
    currency: str
    status: str
    created_at: datetime
    expires_at: datetime
    offer_message_id: int | None


class OfferDatabase:
    def __init__(self, path: str) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_connection_id TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                source_message_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                buyer_name TEXT NOT NULL,
                buyer_username TEXT,
                gift_url TEXT NOT NULL,
                gift_name TEXT NOT NULL,
                gift_number INTEGER NOT NULL,
                language TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL CHECK(currency IN ('stars', 'gram')),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'accepted', 'declined', 'expired')),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                offer_message_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER NOT NULL,
                seller_name TEXT NOT NULL,
                seller_username TEXT,
                seller_chat_id INTEGER,
                seller_business_connection_id TEXT,
                gift_url TEXT NOT NULL UNIQUE,
                gift_name TEXT NOT NULL,
                gift_number INTEGER NOT NULL,
                language TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL CHECK(currency IN ('stars', 'gram')),
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_offers_expiry
                ON offers(status, expires_at);
            CREATE INDEX IF NOT EXISTS idx_listings_active_url
                ON listings(active, gift_url);
            """
        )
        self._migrate_listings()
        self.connection.commit()

    def _migrate_listings(self) -> None:
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(listings)")
        }
        if "seller_chat_id" not in columns:
            self.connection.execute(
                "ALTER TABLE listings ADD COLUMN seller_chat_id INTEGER"
            )
        if "seller_business_connection_id" not in columns:
            self.connection.execute(
                "ALTER TABLE listings ADD COLUMN seller_business_connection_id TEXT"
            )

    def create_listing(self, **values: Any) -> Listing:
        cursor = self.connection.execute(
            """
            INSERT INTO listings (
                seller_id, seller_name, seller_username, seller_chat_id,
                seller_business_connection_id, gift_url, gift_name,
                gift_number, language, amount, currency, created_at
            ) VALUES (
                :seller_id, :seller_name, :seller_username, :seller_chat_id,
                :seller_business_connection_id, :gift_url, :gift_name,
                :gift_number, :language, :amount, :currency, :created_at
            )
            ON CONFLICT(gift_url) DO UPDATE SET
                seller_id = excluded.seller_id,
                seller_name = excluded.seller_name,
                seller_username = excluded.seller_username,
                seller_chat_id = excluded.seller_chat_id,
                seller_business_connection_id = excluded.seller_business_connection_id,
                gift_name = excluded.gift_name,
                gift_number = excluded.gift_number,
                language = excluded.language,
                amount = excluded.amount,
                currency = excluded.currency,
                created_at = excluded.created_at,
                active = 1
            """,
            values,
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT id FROM listings WHERE gift_url = ?", (values["gift_url"],)
        ).fetchone()
        if row is None:
            raise LookupError("Listing was not created")
        return self.get_listing(row["id"])

    def get_listing(self, listing_id: int) -> Listing:
        row = self.connection.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Listing {listing_id} was not found")
        return self._listing_from_row(row)

    def take_listing(self, gift_url: str, buyer_id: int | None = None) -> Listing | None:
        if buyer_id is None:
            cursor = self.connection.execute(
                "UPDATE listings SET active = 0 WHERE gift_url = ? AND active = 1",
                (gift_url,),
            )
        else:
            cursor = self.connection.execute(
                """
                UPDATE listings SET active = 0
                WHERE gift_url = ? AND active = 1 AND seller_id != ?
                """,
                (gift_url, buyer_id),
            )
        self.connection.commit()
        if cursor.rowcount != 1:
            return None
        row = self.connection.execute(
            "SELECT * FROM listings WHERE gift_url = ?", (gift_url,)
        ).fetchone()
        return self._listing_from_row(row) if row is not None else None

    def find_listing(self, gift_url: str) -> Listing | None:
        row = self.connection.execute(
            "SELECT * FROM listings WHERE gift_url = ?", (gift_url,)
        ).fetchone()
        return self._listing_from_row(row) if row is not None else None

    def create_offer(self, **values: Any) -> Offer:
        cursor = self.connection.execute(
            """
            INSERT INTO offers (
                business_connection_id, chat_id, source_message_id, buyer_id,
                buyer_name, buyer_username, gift_url, gift_name, gift_number,
                language, amount, currency, created_at, expires_at
            ) VALUES (
                :business_connection_id, :chat_id, :source_message_id, :buyer_id,
                :buyer_name, :buyer_username, :gift_url, :gift_name, :gift_number,
                :language, :amount, :currency, :created_at, :expires_at
            )
            """,
            values,
        )
        self.connection.commit()
        return self.get_offer(cursor.lastrowid)

    def set_offer_message_id(self, offer_id: int, message_id: int) -> None:
        self.connection.execute(
            "UPDATE offers SET offer_message_id = ? WHERE id = ?",
            (message_id, offer_id),
        )
        self.connection.commit()

    def get_offer(self, offer_id: int) -> Offer:
        row = self.connection.execute(
            "SELECT * FROM offers WHERE id = ?", (offer_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Offer {offer_id} was not found")
        return self._from_row(row)

    def take_pending_offer(self, offer_id: int, status: str) -> Offer | None:
        now = datetime.now(timezone.utc)
        cursor = self.connection.execute(
            """
            UPDATE offers
            SET status = ?
            WHERE id = ? AND status = 'pending' AND expires_at > ?
            """,
            (status, offer_id, now.isoformat()),
        )
        self.connection.commit()
        if cursor.rowcount != 1:
            return None
        return self.get_offer(offer_id)

    def expire_old_offers(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.connection.execute(
            """
            UPDATE offers SET status = 'expired'
            WHERE status = 'pending' AND expires_at <= ?
            """,
            (now,),
        )
        self.connection.commit()
        return cursor.rowcount

    @staticmethod
    def _listing_from_row(row: sqlite3.Row) -> Listing:
        amount = row["amount"]
        if float(amount).is_integer():
            amount = int(amount)
        return Listing(
            id=row["id"],
            seller_id=row["seller_id"],
            seller_name=row["seller_name"],
            seller_username=row["seller_username"],
            seller_chat_id=row["seller_chat_id"] or row["seller_id"],
            seller_business_connection_id=row["seller_business_connection_id"] or "",
            gift_url=row["gift_url"],
            gift_name=row["gift_name"],
            gift_number=row["gift_number"],
            language=row["language"],
            amount=amount,
            currency=row["currency"],
            created_at=datetime.fromisoformat(row["created_at"]),
            active=bool(row["active"]),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Offer:
        amount = row["amount"]
        if float(amount).is_integer():
            amount = int(amount)
        return Offer(
            id=row["id"],
            business_connection_id=row["business_connection_id"],
            chat_id=row["chat_id"],
            source_message_id=row["source_message_id"],
            buyer_id=row["buyer_id"],
            buyer_name=row["buyer_name"],
            buyer_username=row["buyer_username"],
            gift_url=row["gift_url"],
            gift_name=row["gift_name"],
            gift_number=row["gift_number"],
            language=row["language"],
            amount=amount,
            currency=row["currency"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            offer_message_id=row["offer_message_id"],
        )

    def close(self) -> None:
        self.connection.close()
