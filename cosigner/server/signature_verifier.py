"""
Webhook request verification: ECDSA signature + IP source whitelist.

Fordefi signs every webhook delivery with an ECDSA private key. We verify
against their published public key. Verification is done against the raw
request bytes before any JSON parsing to prevent body-mutation attacks.
"""
import base64
import hashlib
import logging

from ecdsa import BadSignatureError, VerifyingKey
from ecdsa.util import sigdecode_der
from fastapi import Request

from cosigner.config import settings

logger = logging.getLogger(__name__)

# Fordefi's ECDSA P-256 public key — do not modify
_FORDEFI_PUBLIC_KEY_PEM = """\
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEQJ0NeDYQqqeCvgDofFsgtgaxk+dx
ybi63YGJwHz8Ebx7YQrmwNWnW3bG65E8wGHqZECjuaK2GKHbZx1EV2ws9A==
-----END PUBLIC KEY-----
"""

# Parse once at module load — VerifyingKey construction is not cheap
_VERIFYING_KEY: VerifyingKey = VerifyingKey.from_pem(_FORDEFI_PUBLIC_KEY_PEM)


def verify_request(request: Request, raw_body: bytes) -> bool:
    """
    Return True only if the request passes both the IP whitelist and the
    ECDSA signature check.

    Both checks must pass; failure of either is logged at WARNING and returns False.
    """
    # --- IP whitelist ---
    if not settings.disable_ip_check:
        client_ip = request.client.host if request.client else None
        if client_ip != settings.allowed_ip:
            logger.warning(
                "rejected webhook from unauthorized IP: %s (expected %s)",
                client_ip,
                settings.allowed_ip,
            )
            return False

    # --- ECDSA signature ---
    sig_header = request.headers.get("X-Signature")
    if not sig_header:
        logger.warning("rejected webhook: missing X-Signature header")
        return False

    try:
        signature = base64.b64decode(sig_header)
        _VERIFYING_KEY.verify(
            signature=signature,
            data=raw_body,
            hashfunc=hashlib.sha256,
            sigdecode=sigdecode_der,
        )
    except BadSignatureError:
        logger.warning("rejected webhook: invalid ECDSA signature")
        return False
    except Exception as exc:  # noqa: BLE001 — malformed base64 or DER data
        logger.warning("rejected webhook: signature verification error: %s", exc)
        return False

    return True
