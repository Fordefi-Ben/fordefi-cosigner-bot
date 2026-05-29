> **DISCLAIMER: SAMPLE CODE — NOT FOR PRODUCTION USE**
>
> This repository is a reference implementation intended to demonstrate patterns
> for building a Fordefi co-signer bot. It has not been security-audited and is
> not suitable for production deployment without thorough review, testing, and
> hardening by qualified engineers. In particular: signature verification logic,
> secret handling, and validator policy rules must all be independently validated
> before use in any environment holding real assets. **Use at your own risk.**

---

# Fordefi Co-Signer Bot — Sample Implementation

A FastAPI webhook server that receives Fordefi transaction events, routes them
to policy-specific validators by `rule_id`, and calls the Fordefi API to approve
or abort. Routing is policy-based — `rule_id` is the only routing key.

This sample ships with one implemented validator: **`PersonalMessageValidator`**,
which approves EIP-191 personal message signing requests that match configured
patterns. The framework is modular — additional validators can be added by
implementing a single abstract method.

## Architecture

```
POST /webhook
    │
    ├─ ECDSA signature verify + IP whitelist (403 on failure)
    ├─ Parse WebhookEnvelope
    ├─ Filter: enriched_transaction_state_update only
    ├─ State guard: waiting_for_approval only
    ├─ Approver check: bot must be a pending approver
    ├─ ValidatorRegistry.dispatch(tx) → Decision
    └─ FordefiClient.approve / .abort
```

```
cosigner/
├── main.py                        # Entrypoint; validator wiring
├── config.py                      # Settings (pydantic-settings)
├── server/
│   ├── app.py                     # FastAPI factory
│   ├── routes.py                  # POST /webhook, GET /health
│   └── signature_verifier.py      # ECDSA + IP whitelist
├── client/
│   ├── fordefi_client.py          # approve / abort API calls
│   └── auth.py                    # Bearer token header
├── models/
│   ├── transaction.py             # Pydantic models + helpers
│   └── decision.py                # Decision(action, reason)
└── validators/
    ├── base.py                    # BaseValidator ABC
    ├── registry.py                # rule_id → validator routing
    ├── default.py                 # Fail-closed default (always abort)
    └── evm/
        └── personal_message.py    # EIP-191 personal message validator
```

## Setup

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in FORDEFI_API_TOKEN and BOT_USER_ID
```

### 3. Register your validators in main.py

Replace the example rule ID and matchers with your actual Fordefi policy rule
IDs (found under **Settings → Policies** in the Fordefi console):

```python
registry.register(
    rule_id="<your-policy-rule-uuid>",
    validator=PersonalMessageValidator(
        matchers=[
            RegexMatcher(r"^Access MyApp\.\n\nTimestamp: \d+\.$"),
            ExactMatcher({"I agree to the terms of service"}),
        ],
    ),
)
```

### 4. Run the server

```bash
DISABLE_IP_CHECK=true python -m cosigner.main
```

`DISABLE_IP_CHECK=true` is required when running behind a local tunnel (ngrok).
Remove it in any environment where Fordefi's webhook IP (`54.243.103.88`) reaches
the server directly.

### 5. Expose via ngrok for local testing

```bash
ngrok http 8000
```

Register the resulting `https://` URL in the Fordefi console:
**Settings → Webhooks → Configure webhook → Transactions V2**
URL: `https://<your-id>.ngrok-free.app/webhook`

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FORDEFI_API_TOKEN` | yes | — | API token for approve/abort calls |
| `BOT_USER_ID` | yes | — | This bot's Fordefi user UUID |
| `COSIGNER_PORT` | no | `8000` | HTTP listen port |
| `FORDEFI_API_BASE_URL` | no | `https://api.fordefi.com` | API base URL |
| `ALLOWED_IP` | no | `54.243.103.88` | Fordefi webhook egress IP |
| `DISABLE_IP_CHECK` | no | `false` | Bypass IP whitelist (local dev only) |

## PersonalMessageValidator

Approves EIP-191 personal messages that match at least one configured matcher.
Aborts if no matcher matches (fail-closed). Matchers are evaluated in order —
the first match wins.

### Built-in matchers

**`RegexMatcher`** — applies a regular expression to the raw message string.

```python
RegexMatcher(r"^Access MyApp\.\n\nTimestamp: \d+\.$")
```

**`ExactMatcher`** — byte-exact match against a set of known strings.

```python
ExactMatcher({"I agree to the terms of service"})
```

## How to add a validator

1. Create a class in `cosigner/validators/` that extends `BaseValidator`:

```python
from cosigner.models.decision import Decision
from cosigner.models.transaction import Transaction
from cosigner.validators.base import BaseValidator

class MyValidator(BaseValidator):
    """Describe what this validator checks and when it aborts."""

    async def validate(self, tx: Transaction) -> Decision:
        # inspect tx fields, return approve or abort
        return Decision(action="approve", reason="all checks passed")
```

2. Register it in `main.py`:

```python
registry.register(
    rule_id="<policy-rule-uuid>",
    validator=MyValidator(),
)
```

Any transaction whose `rule_id` is not registered is handled by
`DefaultValidator`, which always aborts (fail-closed).

## Running tests

```bash
pytest
```
