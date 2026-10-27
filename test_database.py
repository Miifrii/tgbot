import unittest
from datetime import datetime, timezone

from database import OfferDatabase


class ListingDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = OfferDatabase(":memory:")

    def tearDown(self) -> None:
        self.database.close()

    def listing_values(self) -> dict:
        return {
            "seller_id": 10,
            "seller_name": "Seller",
            "seller_username": "seller",
            "seller_chat_id": 1001,
            "seller_business_connection_id": "conn-1",
            "gift_url": "https://t.me/nft/TestGift-1",
            "gift_name": "TestGift",
            "gift_number": 1,
            "language": "ru",
            "amount": 100,
            "currency": "gram",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def test_take_listing_is_one_time(self) -> None:
        created = self.database.create_listing(**self.listing_values())
        taken = self.database.take_listing(created.gift_url)
        self.assertIsNotNone(taken)
        assert taken is not None
        self.assertFalse(taken.active)
        self.assertIsNone(self.database.take_listing(created.gift_url))

    def test_info_replaces_existing_listing(self) -> None:
        self.database.create_listing(**self.listing_values())
        values = self.listing_values()
        values["amount"] = 250
        self.database.create_listing(**values)
        listing = self.database.take_listing(values["gift_url"])
        self.assertIsNotNone(listing)
        assert listing is not None
        self.assertEqual(listing.amount, 250)

    def test_listing_keeps_seller_delivery_context(self) -> None:
        created = self.database.create_listing(**self.listing_values())
        self.assertEqual(created.seller_chat_id, 1001)
        self.assertEqual(created.seller_business_connection_id, "conn-1")


if __name__ == "__main__":
    unittest.main()
