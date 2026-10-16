"""python -m app.core.bootstrap — crée explicitement un tenant et un utilisateur."""

from __future__ import annotations

import getpass
import os

from .db import init_db, make_engine, make_session_factory
from .models import Tenant, User
from .security import ROLES, hash_password
from .settings import get_settings, require_jwt_secret


def main() -> int:
    settings = get_settings()
    require_jwt_secret(settings)
    username = os.getenv("TRANSLATOR_BOOTSTRAP_USERNAME")
    password = os.getenv("TRANSLATOR_BOOTSTRAP_PASSWORD")
    tenant_name = os.getenv("TRANSLATOR_BOOTSTRAP_TENANT", "default")
    role = os.getenv("TRANSLATOR_BOOTSTRAP_ROLE", "admin")
    if not username:
        raise SystemExit("TRANSLATOR_BOOTSTRAP_USERNAME est requis")
    if not password:
        password = getpass.getpass("Mot de passe bootstrap (12 caractères minimum): ")
    if role not in ROLES:
        raise SystemExit(f"TRANSLATOR_BOOTSTRAP_ROLE doit être l'un de {sorted(ROLES)}")
    engine = make_engine(settings)
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as db:
        tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if tenant is None:
            tenant = Tenant(name=tenant_name)
            db.add(tenant)
            db.flush()
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise SystemExit("Cet utilisateur existe déjà")
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                tenant_id=tenant.id,
                role=role,
            )
        )
        db.commit()
        print(f"Utilisateur créé: {username} tenant={tenant.id} role={role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
