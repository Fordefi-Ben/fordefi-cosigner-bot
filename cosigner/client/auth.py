from cosigner.config import settings


def build_auth_header() -> dict[str, str]:
    """Return the Authorization header dict for Fordefi API requests."""
    return {"Authorization": f"Bearer {settings.fordefi_api_token}"}
