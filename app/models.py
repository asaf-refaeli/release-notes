from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    Text,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ReleaseStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class EventType(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')", name="status_valid"
        ),
        CheckConstraint(
            "(status = 'DRAFT') = (published_at IS NULL)",
            name="published_at_matches_status",
        ),
        # Drafts may share a version; published and archived releases may not.
        Index(
            "uq_releases_version_published",
            "version",
            unique=True,
            postgresql_where=text("status <> 'DRAFT'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    version: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    status: Mapped[str] = mapped_column(Text, server_default="DRAFT")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReleaseEvent(Base):
    __tablename__ = "release_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('CREATED', 'UPDATED', 'PUBLISHED', 'ARCHIVED')",
            name="event_type_valid",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    release_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("releases.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
