"""
Discharge+ — Dependencies
JWT verification, user caching, and singleton Supabase client pooling.
"""

import time
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from config import get_settings
from supabase import create_client, Client, ClientOptions

settings = get_settings()
security = HTTPBearer()

# Singleton Supabase client instances (connection pooling & keep-alive)
_supabase_admin_instance: Optional[Client] = None
_supabase_anon_instance: Optional[Client] = None

# In-memory user cache: {user_id: {"data": user_dict, "expires_at": float}}
_USER_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def get_supabase_admin() -> Client:
    """Returns a cached singleton Supabase client with persistent connection pool (service role)."""
    global _supabase_admin_instance
    if _supabase_admin_instance is None:
        _supabase_admin_instance = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
            options=ClientOptions(persist_session=False)
        )
    return _supabase_admin_instance


def get_supabase() -> Client:
    """Returns a cached singleton Supabase client with persistent connection pool (anon key)."""
    global _supabase_anon_instance
    if _supabase_anon_instance is None:
        _supabase_anon_instance = create_client(
            settings.supabase_url,
            settings.supabase_anon_key,
            options=ClientOptions(persist_session=False)
        )
    return _supabase_anon_instance


class CurrentUser:
    """Represents the authenticated user extracted from JWT."""

    def __init__(self, id: str, email: str, role: str, hospital_id: str):
        self.id = id
        self.email = email
        self.role = role
        self.hospital_id = hospital_id

    def __repr__(self):
        return f"<CurrentUser {self.email} role={self.role} hospital={self.hospital_id}>"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase_admin),
) -> CurrentUser:
    """
    Verify Supabase JWT and return current user.
    Fast path: local cryptographic JWT decode + in-memory user cache (<1ms).
    Slow fallback: network auth check via Supabase if token signature fails.
    """
    token = credentials.credentials
    user_id = None
    email_from_token = None

    # 1. Fast path: local cryptographic verification
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        user_id = payload.get("sub")
        email_from_token = payload.get("email")
    except Exception:
        # Fallback to Supabase cloud auth endpoint if local secret differs
        try:
            auth_res = supabase.auth.get_user(token)
            if auth_res and auth_res.user:
                user_id = auth_res.user.id
                email_from_token = auth_res.user.email
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {str(e)}",
            )

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )

    # 2. Check local in-memory TTL cache
    now = time.time()
    cached = _USER_CACHE.get(user_id)
    if cached and cached["expires_at"] > now:
        cached_data = cached["data"]
        return CurrentUser(
            id=cached_data["id"],
            email=cached_data["email"],
            role=cached_data["role"],
            hospital_id=cached_data["hospital_id"],
        )

    # 3. Cache miss: Fetch user record from database
    result = supabase.table("users").select("id, email, role, hospital_id").eq("id", user_id).single().execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User record not found in database",
        )

    user_data = result.data
    # Cache user profile for 5 minutes
    _USER_CACHE[user_id] = {
        "data": user_data,
        "expires_at": now + CACHE_TTL_SECONDS,
    }

    return CurrentUser(
        id=user_data["id"],
        email=user_data["email"],
        role=user_data["role"],
        hospital_id=user_data["hospital_id"],
    )


def require_role(*roles: str):
    """Dependency factory: ensures current user has one of the given roles."""

    def role_checker(current_user: CurrentUser = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(roles)}",
            )
        return current_user

    return role_checker
