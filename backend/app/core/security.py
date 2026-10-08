from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import RevokedSession, Tenant, User
from .settings import get_settings, require_jwt_secret

_passwords = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
ROLES = {"uploader", "reviewer", "admin"}


def hash_password(password):
    if len(password) < 12:
        raise ValueError("Le mot de passe doit contenir au moins 12 caractères")
    return _passwords.hash(password)


def verify_password(password, encoded):
    try:
        return _passwords.verify(encoded, password)
    except (Argon2Error, ValueError):
        return False


def create_access_token(user):
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": user.id,
            "username": user.username,
            "tenant_id": user.tenant_id,
            "role": user.role,
            "jti": str(uuid.uuid4()),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        },
        require_jwt_secret(settings),
        algorithm="HS256",
    )


def decode_access_token(token, settings=None):
    settings = settings or get_settings()
    try:
        return jwt.decode(
            token,
            require_jwt_secret(settings),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iss", "aud", "sub", "tenant_id", "role", "jti"]},
        )
    except (jwt.PyJWTError, RuntimeError):
        raise unauthorized() from None


def session_id(claims):
    return hashlib.sha256(str(claims["jti"]).encode()).hexdigest()


def user_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "tenant_id": user.tenant_id,
        "role": user.role,
    }


def unauthorized(detail="Token invalide"):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user_factory(session_factory):
    def dependency(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
    ):
        settings = get_settings()
        use_cookie = False
        if (
            credentials
            and credentials.scheme.lower() == "bearer"
            and settings.auth_mode != "cookie"
        ):
            token = credentials.credentials
        elif settings.auth_mode != "bearer" and request.cookies.get(settings.session_cookie):
            token = request.cookies[settings.session_cookie]
            use_cookie = True
        else:
            raise unauthorized("Authentification requise")
        if use_cookie and request.method not in {"GET", "HEAD", "OPTIONS"}:
            csrf = request.cookies.get(settings.csrf_cookie, "")
            header = request.headers.get("X-CSRF-Token", "")
            if not csrf or not header or not hmac.compare_digest(csrf, header):
                raise HTTPException(403, "CSRF invalide")
            origin = request.headers.get("Origin")
            allowed = settings.origins or [str(request.base_url).rstrip("/")]
            if origin and origin.rstrip("/") not in [x.rstrip("/") for x in allowed]:
                raise HTTPException(403, "Origine de session refusée")
        claims = decode_access_token(token, settings)
        with session_factory() as db:
            if db.get(RevokedSession, session_id(claims)):
                raise unauthorized("Session révoquée")
            user = db.get(User, str(claims["sub"]))
            tenant = db.get(Tenant, user.tenant_id) if user else None
            if (
                not user
                or not user.enabled
                or not tenant
                or not tenant.enabled
                or user.tenant_id != claims.get("tenant_id")
                or user.role != claims.get("role")
            ):
                raise unauthorized("Utilisateur désactivé ou contexte tenant invalide")
            request.state.auth_claims = claims
            db.expunge(user)
            return user

    return dependency
