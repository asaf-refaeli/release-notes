from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Release
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


def create_release(session: Session, data: ReleaseCreate) -> Release:
    release = Release(version=data.version, description=data.description)
    session.add(release)
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
