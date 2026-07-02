from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from . import models  # noqa: F401  - register tables on the metadata

    Base.metadata.create_all(engine)
    _run_light_migrations()


def _run_light_migrations() -> None:
    """create_all never alters existing tables - add new columns by hand
    so an existing SQLite database keeps working after an upgrade."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.connect() as conn:
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(alerts)")]
        if columns and "zone" not in columns:
            conn.exec_driver_sql("ALTER TABLE alerts ADD COLUMN zone VARCHAR(20) NOT NULL DEFAULT 'fr'")
            conn.commit()
