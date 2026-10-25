import os
from pathlib import Path
from dotenv import load_dotenv
from backend.commons.logger import get_logger

# Load environment variables from root .env if present
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.is_file():
    load_dotenv(dotenv_path=_env_path)

# Central logger alias re-exported for core layer
logger = get_logger
