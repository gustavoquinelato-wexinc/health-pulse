from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.auth.centralized_auth_middleware import require_web_authentication, UserData

router = APIRouter()

@router.get("/api/v1/auth/validate-web")
async def validate_web(user: UserData = Depends(require_web_authentication)):
    """Cookie-based validation for web. Avoids Authorization header and preflight."""
    return JSONResponse({
        "valid": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_admin": user.is_admin,
            "active": user.active
        }
    })

