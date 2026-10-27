import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from aiogram.enums import ChatType

from bot import accepted_keyboard, nft_preview_options, offer_sender
from database import Offer


class AcceptedKeyboardTests(unittest.TestCase):
    def make_offer(self, buyer_username: str | None) -> Offer:
        now = datetime.now(timezone.utc)
        return Offer(
            id=1,
            business_connection_id="business-connection",
            chat_id=10,
            source_message_id=20,
            buyer_id=12345,
            buyer_name="Buyer",
            buyer_username=buyer_username,
            gift_url="https://t.me/nft/TestGift-1",
            gift_name="TestGift",
            gift_number=1,
            language="ru",
            amount=100,
            currency="stars",
            status="accepted",
            created_at=now,
            expires_at=now,
            offer_message_id=30,
        )

    def test_transfer_button_uses_username_link(self) -> None:
        keyboard = accepted_keyboard(self.make_offer("buyer"))
        transfer_button = keyboard.inline_keyboard[0][0]

        self.assertEqual(transfer_button.url, "https://t.me/buyer")
        self.assertIsNone(transfer_button.callback_data)

    def test_transfer_button_uses_user_id_link_without_username(self) -> None:
        keyboard = accepted_keyboard(self.make_offer(None))
        transfer_button = keyboard.inline_keyboard[0][0]

        self.assertEqual(transfer_button.url, "tg://user?id=12345")
        self.assertIsNone(transfer_button.callback_data)


class PreviewOptionsTests(unittest.TestCase):
    def test_nft_preview_is_enabled_large_and_above_text(self) -> None:
        options = nft_preview_options("https://t.me/nft/TestGift-1")

        self.assertEqual(options.url, "https://t.me/nft/TestGift-1")
        self.assertFalse(options.is_disabled)
        self.assertTrue(options.show_above_text)
        self.assertTrue(options.prefer_large_media)


class OfferSenderTests(unittest.TestCase):
    def test_business_message_uses_from_user_sender(self) -> None:
        chat = Mock()
        chat.type = ChatType.PRIVATE
        chat.id = 777
        chat.first_name = "Buyer"
        chat.last_name = None
        chat.username = "buyer_user"

        user = Mock()
        user.id = 168642419
        user.first_name = "Sosalse"
        user.full_name = "Sosalse"
        user.username = "sosalse"

        message = Mock()
        message.business_connection_id = "conn"
        message.chat = chat
        message.from_user = user

        self.assertEqual(offer_sender(message), (168642419, "Sosalse", "sosalse"))

    def test_regular_message_uses_from_user(self) -> None:
        chat = Mock()
        chat.type = ChatType.PRIVATE
        chat.id = 777
        chat.first_name = "Chat"
        chat.last_name = None
        chat.username = "chat_name"

        user = Mock()
        user.id = 888
        user.first_name = "Sender"
        user.full_name = "Sender Name"
        user.username = "sender_user"

        message = Mock()
        message.business_connection_id = None
        message.chat = chat
        message.from_user = user

        self.assertEqual(offer_sender(message), (888, "Sender", "sender_user"))


if __name__ == "__main__":
    unittest.main()
