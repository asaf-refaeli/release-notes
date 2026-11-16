from sqlalchemy.orm import Session

from app.models import Release
from app.schemas import ReleaseCreate


def create_release(session: Session, data: ReleaseCreate) -> Release:
    release = Release(version=data.version, description=data.description)
    session.add(release)
    session.commit()
    session.refresh(release)
    return release
