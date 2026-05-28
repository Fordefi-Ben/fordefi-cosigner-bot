"""
Fordefi Co-Signer Bot — entrypoint and validator wiring.

To run:
    python -m cosigner.main
    uvicorn cosigner.main:app --host 0.0.0.0 --port 8000

To add a validator for a new policy, call registry.register() below with
the policy's rule_id UUID (found in Settings → Policies in the Fordefi console)
and a validator instance. Any transaction whose rule_id is NOT registered here
will be aborted by the DefaultValidator.
"""
import logging

import uvicorn

from cosigner.config import settings
from cosigner.server.app import create_app
from cosigner.validators.evm.personal_message import PersonalMessageValidator, RegexMatcher
from cosigner.validators.registry import ValidatorRegistry

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

registry = ValidatorRegistry()

# Approve EIP-191 personal messages that parse as valid SIWE.
# TODO: tighten SiweMatcher with domains={"your-app.xyz"} and chain_ids={1}
#       once you know which domains and chains should be permitted.
registry.register(
    rule_id="3a5c9e62-4759-43d1-a885-fe2b444a72e0",
    validator=PersonalMessageValidator(
        matchers=[
            # Lighter: session sign-in
            RegexMatcher(
                r"^Access Lighter account\.\n\nOnly sign this message for a trusted client!\nChain ID: \d+\n\nTimestamp: \d+\.$"
            ),
            # Lighter: account registration (pubkey/nonce/indices vary per user)
            RegexMatcher(
                r"^Register Lighter Account\n\npubkey: 0x[0-9a-f]+\nnonce: 0x[0-9a-f]+\naccount index: 0x[0-9a-f]+\napi key index: 0x[0-9a-f]+\nOnly sign this message for a trusted client!$"
            ),
        ],
    ),
)

app = create_app(registry)

if __name__ == "__main__":
    uvicorn.run(
        "cosigner.main:app",
        host="0.0.0.0",
        port=settings.cosigner_port,
        log_level="info",
    )
