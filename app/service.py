from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
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
    sent = data.model_dump(exclude_none=True)  # null = not sent
    # Keep only real changes, so a same-value PATCH writes no UPDATED event.
    changes = {f: v for f, v in sent.items() if getattr(release, f) != v}
    if not changes:
        session.rollback()  # nothing to save; ends the transaction, frees the row lock
        return release  # no UPDATED event
    for field, value in changes.items():
        setattr(release, field, value)
    _record_event(session, release.id, EventType.UPDATED)
    session.commit()
    session.refresh(release)
    return release


def publish_release(session: Session, release_id: int) -> Release:
    release = _lock_release(session, release_id)
    if release.status != ReleaseStatus.DRAFT:
        raise InvalidTransition(
            f"Release {release_id} is {release.status}; only drafts can be published"
        )
    if not release.description.strip():
        raise PublishValidationError("A release needs a description to be published")
    version = release.version  # read now: after a rollback the object is expired
    release.status = ReleaseStatus.PUBLISHED
    release.published_at = func.now()  # set by the DB clock, not the client or the pod
    _record_event(session, release.id, EventType.PUBLISHED)
    try:
        session.commit()
    except IntegrityError as exc:
        # The row lock covers one release; two drafts with the same version are two
        # rows. The partial unique index is what stops the second publish.
        if exc.orig.diag.constraint_name != "uq_releases_version_published":
            raise
        session.rollback()
        raise DuplicateVersion(
            f"Version {version} is already used by a published or archived release"
        ) from exc
    session.refresh(release)
    return release


def archive_release(session: Session, release_id: int) -> Release:
    release = _lock_release(session, release_id)
    if release.status != ReleaseStatus.PUBLISHED:
        raise InvalidTransition(
            f"Release {release_id} is {release.status}; "
            "only published releases can be archived"
        )
    # published_at is kept: an archived release was published at that time.
    release.status = ReleaseStatus.ARCHIVED
    _record_event(session, release.id, EventType.ARCHIVED)
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
