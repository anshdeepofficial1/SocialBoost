from app.core.config import normalize_database_url


def test_normalizes_legacy_postgres_url():
    assert normalize_database_url("postgres://user:secret@db.example.test/app") == (
        "postgresql+psycopg://user:secret@db.example.test/app"
    )


def test_normalizes_standard_postgres_url_and_preserves_options():
    assert normalize_database_url(
        "postgresql://user:secret@db.example.test/app?sslmode=require&channel_binding=require"
    ) == (
        "postgresql+psycopg://user:secret@db.example.test/app?sslmode=require&channel_binding=require"
    )


def test_leaves_sqlite_url_untouched():
    assert normalize_database_url("sqlite:///./backend/socialboost.db") == (
        "sqlite:///./backend/socialboost.db"
    )
