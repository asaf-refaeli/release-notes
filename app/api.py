from typing import Annotated

from fastapi import APIRouter, Query

from app import service
from app.db import SessionDep
from app.models import Release
from app.schemas import ReleaseCreate, ReleaseOut

router = APIRouter(prefix="/api/releases", tags=["releases"])


@router.post("", status_code=201, response_model=ReleaseOut)
def create(data: ReleaseCreate, session: SessionDep) -> Release:
    return service.create_release(session, data)


@router.get("", response_model=list[ReleaseOut])
def list_all(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Release]:
    return service.list_releases(session, limit, offset)


@router.get("/{release_id}", response_model=ReleaseOut)
def get_one(release_id: int, session: SessionDep) -> Release:
    return service.get_release(session, release_id)
