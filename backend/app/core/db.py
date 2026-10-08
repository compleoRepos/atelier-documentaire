from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import Settings


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings):
    kwargs = {"pool_pre_ping": True}
    if settings.database_url.startswith("sqlite"):
        kwargs.update(connect_args={"check_same_thread": False})
    return create_engine(settings.database_url, **kwargs)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def init_db(engine, settings: Settings | None = None) -> None:
    from . import models  # noqa: F401

    if settings is not None and not settings.auto_create_schema:
        from alembic.migration import MigrationContext
        from alembic.script import ScriptDirectory

        scripts = ScriptDirectory(str(Path(__file__).resolve().parents[2] / "migrations"))
        with engine.connect() as connection:
            current = set(MigrationContext.configure(connection).get_current_heads())
        if current != set(scripts.get_heads()):
            raise RuntimeError("DATABASE_MIGRATION_REQUIRED: exécuter alembic upgrade head")
        return
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(factory):
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
