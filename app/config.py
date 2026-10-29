import os
from pathlib import Path

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Database file path, configurable via MINIDASH_DB_PATH environment variable
DATABASE_PATH = os.getenv("MINIDASH_DB_PATH", str(BASE_DIR / "minidash.db"))
