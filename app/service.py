from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EventType, Release, ReleaseEvent, ReleaseStatus
from app.schemas import ReleaseCreate, ReleaseUpdate


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


def _lock_release(session: Session, release_id: int) -> Release:
    # SELECT ... FOR UPDATE: other writers of this row wait until this transaction ends,
    # so the status checked below cannot change before the commit.
    statement = select(Release).where(Release.id == release_id).with_for_update()
    release = session.scalars(statement).one_or_none()
    if release is None:
        raise ReleaseNotFound(f"Release {release_id} not found")
    return release


def create_release(session: Session, data: ReleaseCreate) -> Release:
    release = Release(version=data.version, description=data.description)
    session.add(release)
    session.flush()  # sends the INSERT so Postgres assigns release.id; not committed
    _record_event(session, release.id, EventType.CREATED)
    session.commit()
    session.refresh(release)
    return release


def update_release(session: Session, release_id: int, data: ReleaseUpdate) -> Release:
    release = _lock_release(session, release_id)
    if release.status != ReleaseStatus.DRAFT:
        raise InvalidTransition(
            f"Release {release_id} is {release.status}; only drafts can be edited"
        )
    changes = data.model_dump(exclude_none=True)  # null = not sent
    if not changes:
        return release  # nothing to change, so no UPDATED event
    for field, value in changes.items():
        setattr(release, field, value)
    _record_event(session, release.id, EventType.UPDATED)
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
