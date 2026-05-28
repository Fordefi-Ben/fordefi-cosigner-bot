"""
Runtime configuration loaded from environment variables (or a .env file).

All settings are validated at startup via pydantic-settings. The server will
refuse to start if any required variable is missing.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Fordefi API token for authenticating outbound approve/abort calls
    fordefi_api_token: str

    # Not used in the current ECDSA verification flow, reserved for future use
    webhook_secret: str = ""

    # This bot's Fordefi user ID — used to confirm the bot is a pending approver
    bot_user_id: str

    # HTTP port for the uvicorn server
    cosigner_port: int = 8000

    # Base URL for the Fordefi REST API
    fordefi_api_base_url: str = "https://api.fordefi.com"

    # Source IP that Fordefi webhooks originate from
    allowed_ip: str = "54.243.103.88"

    # Set to true in local dev to skip the IP whitelist check (e.g. behind ngrok)
    disable_ip_check: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Module-level singleton — import this everywhere rather than constructing Settings()
settings = Settings()
