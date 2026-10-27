from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    nft_image_url: str
    database_path: str = "offers.sqlite3"
    offer_ttl_hours: int = 8

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("BOT_TOKEN", "8665110891:AAFaYCQM6-3N9mlRrCTSo7Tw83UMXYvAGTA").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN is not set")

        image_url = os.getenv("NFT_IMAGE_URL", "https://example.com/nft-image.jpg").strip()
        if not image_url:
            raise RuntimeError("NFT_IMAGE_URL is not set")

        database_path = os.getenv("DATABASE_PATH", "offers.sqlite3").strip()
        ttl = int(os.getenv("OFFER_TTL_HOURS", "8"))
        if ttl <= 0:
            raise RuntimeError("OFFER_TTL_HOURS must be positive")

        return cls(
            bot_token=token,
            nft_image_url=image_url,
            database_path=database_path or "offers.sqlite3",
            offer_ttl_hours=ttl,
        )
