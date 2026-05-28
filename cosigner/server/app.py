from fastapi import FastAPI

from cosigner.client.fordefi_client import FordefiClient
from cosigner.server.routes import router
from cosigner.validators.registry import ValidatorRegistry


def create_app(registry: ValidatorRegistry) -> FastAPI:
    """
    Build the FastAPI application.

    The registry and Fordefi client are stored on app.state so route handlers
    can access them without global state or dependency-injection decorators.
    """
    app = FastAPI(
        title="Fordefi Co-Signer Bot",
        description="Policy-based co-signer for Fordefi transaction approvals",
    )
    app.state.registry = registry
    app.state.fordefi_client = FordefiClient()
    app.include_router(router)
    return app
