from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://de_user:de_password@localhost:5432/ecommerce",
    )
    api_url: str = os.getenv("MOCK_API_URL", "http://localhost:8000")
    api_key: str = os.getenv("MOCK_API_KEY", "training-key")
    raw_dir: Path = ROOT / "data" / "raw"
    staging_dir: Path = ROOT / "data" / "staging"
    reject_dir: Path = ROOT / "data" / "reject"
    metadata_dir: Path = ROOT / "metadata"
    report_dir: Path = ROOT / "reports"


SETTINGS = Settings()
