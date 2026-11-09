from backend.commons.logger import get_logger

# Central logger alias re-exported for the core layer.
# Environment variables (including the root .env) are loaded by
# backend.core.config.settings, not here.
logger = get_logger
