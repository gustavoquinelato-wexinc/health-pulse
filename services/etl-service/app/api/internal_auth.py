from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.auth.centralized_auth_service import get_centralized_auth_service
from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)
router = APIRouter()


class InvalidateTokenRequest(BaseModel):
    token_hash: str
    client_id: Optional[int] = None


def _verify_internal_secret(request: Request):
    settings = get_settings()
    internal_secret = getattr(settings, "ETL_INTERNAL_SECRET", None)
    provided = request.headers.get("X-Internal-Auth")
    if not internal_secret:
        logger.warning("ETL_INTERNAL_SECRET not configured; rejecting internal auth request")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal auth not configured")
    if not provided or provided != internal_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized internal request")


@router.post("/api/v1/internal/auth/invalidate-token")
async def invalidate_token(request: Request, payload: InvalidateTokenRequest):
    """Invalidate a token from ETL's in-memory cache. Protected by shared secret."""
    _verify_internal_secret(request)

    token_hash = payload.token_hash
    if not token_hash or len(token_hash) < 32:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token_hash")

    auth = get_centralized_auth_service()
    await auth.cache.invalidate(token_hash)

    logger.info(f"✅ Invalidated token cache for token_hash={token_hash[:8]}...")
    return {"success": True}


@router.post("/api/v1/internal/auth/invalidate-all")
async def invalidate_all_tokens(request: Request):
    """Clear all auth token cache entries. Protected by shared secret."""
    _verify_internal_secret(request)

    auth = get_centralized_auth_service()
    await auth.clear_all_cached_tokens()
    logger.info("✅ Cleared all token cache entries via internal request")
    return {"success": True, "message": "All tokens invalidated"}

