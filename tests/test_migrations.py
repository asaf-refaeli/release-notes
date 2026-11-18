from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.models import Base


def test_migrations_match_models(migrated_url):
    engine = create_engine(migrated_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)
    engine.dispose()

    assert diff == []


# Alembic's drift check does not compare CHECK constraints, so pin their names here.
def test_migration_creates_named_constraints(migrated_url):
    engine = create_engine(migrated_url)
    inspector = inspect(engine)
    releases_checks = {c["name"] for c in inspector.get_check_constraints("releases")}
    events_checks = {
        c["name"] for c in inspector.get_check_constraints("release_events")
    }
    engine.dispose()

    assert releases_checks == {
        "ck_releases_status_valid",
        "ck_releases_published_at_matches_status",
    }
    assert events_checks == {"ck_release_events_event_type_valid"}
