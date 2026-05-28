"""
Webhook endpoint and health check.

Processing pipeline for POST /webhook:
  1. Verify ECDSA signature + source IP → 403 on failure
  2. Parse WebhookEnvelope; log attempt number
  3. Filter: only handle enriched_transaction_state_update events
  4. State guard: only act on waiting_for_approval transactions
  5. Approver check: only act when this bot is a pending approver
  6. Dispatch to policy validator → Decision
  7. Call Fordefi API (approve or abort)
  8. Return 200 (always, after step 1 passes — Fordefi expects fast ACK)
"""
import json
import logging

from fastapi import APIRouter, Request, Response

from cosigner.client.fordefi_client import FordefiClient
from cosigner.config import settings
from cosigner.models.transaction import Transaction, WebhookEnvelope
from cosigner.server.signature_verifier import verify_request
from cosigner.validators.registry import ValidatorRegistry

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness check — no authentication required."""
    return {"status": "ok"}


@router.post("/webhook")
async def webhook(request: Request) -> Response:
    # Read raw body first — signature verification must happen before any parsing
    raw_body = await request.body()

    # Step 1: Authentication gate — hard reject on failure
    if not verify_request(request, raw_body):
        return Response(status_code=403, content="Forbidden")

    # Step 2: Parse envelope
    envelope = WebhookEnvelope.model_validate_json(raw_body)
    logger.info(
        "webhook attempt=%s event_id=%s type=%s",
        envelope.attempt,
        envelope.event_id,
        envelope.event_type,
    )
    logger.debug("webhook payload:\n%s", json.dumps(envelope.event, indent=2))

    # Step 3: Event type filter
    if envelope.event_type != "enriched_transaction_state_update":
        logger.debug("ignoring event_type=%s", envelope.event_type)
        return Response(status_code=200)

    tx = Transaction.model_validate(envelope.event)

    # No managed_transaction_data means we have no policy match or approver info to act on
    if tx.managed_transaction_data is None:
        logger.info("tx %s has no managed_transaction_data, skipping", tx.id)
        return Response(status_code=200)

    # Step 4: State guard — nothing to do unless the tx is awaiting our input
    if tx.state != "waiting_for_approval":
        logger.info("tx %s state=%s, skipping", tx.id, tx.state)
        return Response(status_code=200)

    # Step 5: Approver check — confirm this bot user is a pending approver in a group.
    # We check approval_groups[].approvers[], NOT the flat top-level approvers list,
    # which contains all org users regardless of role.
    approval_req = (
        tx.managed_transaction_data.approval_request
        if tx.managed_transaction_data
        else None
    )
    bot_is_pending_approver = False
    if approval_req:
        for group in approval_req.approval_groups:
            for entry in group.approvers:
                user = entry.user or {}
                if user.get("id") == settings.bot_user_id and entry.state == "pending":
                    bot_is_pending_approver = True
                    break
            if bot_is_pending_approver:
                break

    if not bot_is_pending_approver:
        logger.info("not an approver for tx %s, skipping", tx.id)
        return Response(status_code=200)

    # Step 6: Policy dispatch
    registry: ValidatorRegistry = request.app.state.registry
    decision = await registry.dispatch(tx)
    logger.info(
        "tx %s → action=%s reason=%s",
        tx.id,
        decision.action,
        decision.reason,
    )

    # Step 7: Execute decision
    client: FordefiClient = request.app.state.fordefi_client
    if decision.action == "approve":
        await client.approve(tx.id)
    else:
        await client.abort(tx.id, decision.reason)

    return Response(status_code=200)
