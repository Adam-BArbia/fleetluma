"""Cloud SQL readiness checks must detect missing FleetLuma privileges."""
from unittest.mock import MagicMock, patch
import os

from fleetluma_backend.postgres_store import PostgresStore, connection


def test_readiness_checks_private_tables_not_only_connection():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"ready": True}
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor

    class Connect:
        def __enter__(self):
            return conn
        def __exit__(self, *_):
            return False

    store = PostgresStore(connect=lambda: Connect())
    assert store.ping() is True
    query = cursor.execute.call_args.args[0]
    assert "has_schema_privilege" in query
    assert "fleetluma.hosts" in query
    assert "fleetluma.service_checks" in query


def test_readiness_refuses_insufficient_permissions():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"ready": False}
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor

    class Connect:
        def __enter__(self):
            return conn
        def __exit__(self, *_):
            return False

    assert PostgresStore(connect=lambda: Connect()).ping() is False


def test_cloud_connection_disables_prepared_statements_for_transaction_pooler():
    conn = MagicMock()
    with patch.dict(os.environ, {"FLEETLUMA_DATABASE_URL": "postgresql://example.invalid/db"}):
        with patch("fleetluma_backend.postgres_store.psycopg.connect", return_value=conn) as patched:
            with connection():
                pass
    kwargs = patched.call_args.kwargs
    assert kwargs["sslmode"] == "require"
    assert kwargs["connect_timeout"] == 5
    assert kwargs["prepare_threshold"] is None
