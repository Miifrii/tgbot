import unittest

from parser import parse_info_command, parse_offer_command


class InfoCommandParserTests(unittest.TestCase):
    def test_star_command(self) -> None:
        command = parse_info_command(
            "/info https://t.me/nft/HomemadeCake-166832 ru 100 star"
        )
        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual(command.gift_name, "HomemadeCake")
        self.assertEqual(command.gift_number, 166832)
        self.assertEqual(command.amount, 100)
        self.assertEqual(command.currency, "stars")

    def test_gra_command(self) -> None:
        command = parse_info_command(
            "/info https://t.me/nft/AnotherGift-42 en 2.5 gra"
        )
        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual(command.amount, 2.5)
        self.assertEqual(command.currency, "gram")

    def test_invalid_currency_is_rejected(self) -> None:
        self.assertIsNone(
            parse_info_command(
                "/info https://t.me/nft/HomemadeCake-166832 ru 100 gram"
            )
        )
        self.assertIsNone(
            parse_info_command(
                "/info https://t.me/nft/HomemadeCake-166832 ru 100 stars"
            )
        )

    def test_invalid_gift_slug(self) -> None:
        self.assertIsNone(
            parse_info_command(
                "/info https://t.me/nft/HomemadeCake | ru 100 star"
            )
        )

    def test_missing_field_is_rejected(self) -> None:
        self.assertIsNone(
            parse_info_command(
                "/info https://t.me/nft/HomemadeCake-166832 ru 100"
            )
        )


class OfferCommandParserTests(unittest.TestCase):
    def test_valid_offer_command(self) -> None:
        command = parse_offer_command(
            "/offer https://t.me/nft/HomemadeCake-166832"
        )
        self.assertIsNotNone(command)
        assert command is not None
        self.assertEqual(command.gift_name, "HomemadeCake")
        self.assertEqual(command.gift_number, 166832)

    def test_extra_parameters_are_rejected(self) -> None:
        self.assertIsNone(
            parse_offer_command(
                "/offer https://t.me/nft/HomemadeCake-166832 ru"
            )
        )

    def test_invalid_gift_slug_is_rejected(self) -> None:
        self.assertIsNone(
            parse_offer_command("/offer https://t.me/nft/HomemadeCake")
        )


if __name__ == "__main__":
    unittest.main()
