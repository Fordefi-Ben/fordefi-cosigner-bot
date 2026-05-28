"""
Async Fordefi API client for approve/abort operations.

Non-2xx responses are logged and swallowed rather than raised because the
transaction may have already been decided by the time we call — idempotency
is the right behaviour for a co-signer.
"""
import logging

import httpx

from cosigner.client.auth import build_auth_header
from cosigner.config import settings

logger = logging.getLogger(__name__)


class FordefiClient:
    """Thin async wrapper around the Fordefi transaction decision endpoints."""

    def __init__(self) -> None:
        self._base = settings.fordefi_api_base_url

    async def approve(self, tx_id: str) -> None:
        """
        POST /transactions/{tx_id}/approve

        TODO: Add exponential-backoff retry for transient 5xx responses.
        """
        url = f"{self._base}/api/v1/transactions/{tx_id}/approve"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=build_auth_header())

        if not resp.is_success:
            logger.warning(
                "approve tx=%s failed status=%s body=%s",
                tx_id,
                resp.status_code,
                resp.text,
            )

    async def abort(self, tx_id: str, reason: str) -> None:
        """
        POST /transactions/{tx_id}/abort

        The API takes no request body; `reason` is for local logging only.

        TODO: Add exponential-backoff retry for transient 5xx responses.
        """
        url = f"{self._base}/api/v1/transactions/{tx_id}/abort"
        logger.info("aborting tx=%s reason=%s", tx_id, reason)
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=build_auth_header())

        if not resp.is_success:
            logger.warning(
                "abort tx=%s failed status=%s body=%s",
                tx_id,
                resp.status_code,
                resp.text,
            )
