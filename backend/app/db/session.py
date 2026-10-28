from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..core.config import settings

url = settings.resolved_database_url

if url.startswith("sqlite"):
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_pre_ping=True,
    )
else:
    # Hosted Postgres compute may pause while idle; check connections before
    # reuse and recycle older connections to avoid stale pooled sockets.
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
