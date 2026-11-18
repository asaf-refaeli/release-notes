from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EventType, Release, ReleaseEvent
from app.schemas import ReleaseCreate


class DomainError(Exception):
    """A business rule was broken. main.py maps each subclass to an HTTP status."""


class ReleaseNotFound(DomainError):
    pass


class InvalidTransition(DomainError):
    pass


class PublishValidationError(DomainError):
    pass


class DuplicateVersion(DomainError):
    pass


def _record_event(session: Session, release_id: int, event_type: EventType) -> None:
    # No commit here: the caller commits the change and its event together.
    session.add(ReleaseEvent(release_id=release_id, event_type=event_type))


def create_release(session: Session, data: ReleaseCreate) -> Release:
    release = Release(version=data.version, description=data.description)
    session.add(release)
    session.flush()  # sends the INSERT so Postgres assigns release.id; not committed
    _record_event(session, release.id, EventType.CREATED)
    session.commit()
    session.refresh(release)
    return release


def list_releases(session: Session, limit: int, offset: int) -> list[Release]:
    statement = (
        select(Release)
        .order_by(Release.created_at.desc(), Release.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement))


def get_release(session: Session, release_id: int) -> Release:
    release = session.get(Release, release_id)
    if release is None:
        raise ReleaseNotFound(f"Release {release_id} not found")
    return release


def list_events(session: Session, release_id: int) -> list[ReleaseEvent]:
    get_release(session, release_id)  # 404 for an unknown release, not an empty list
    statement = (
        select(ReleaseEvent)
        .where(ReleaseEvent.release_id == release_id)
        .order_by(ReleaseEvent.id)  # ids follow insert order; occurred_at may not
    )
    return list(session.scalars(statement))
