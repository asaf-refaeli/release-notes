from fastapi import APIRouter

from app import service
from app.db import SessionDep
from app.models import Release
from app.schemas import ReleaseCreate, ReleaseOut

router = APIRouter(prefix="/api/releases", tags=["releases"])


@router.post("", status_code=201, response_model=ReleaseOut)
def create(data: ReleaseCreate, session: SessionDep) -> Release:
    return service.create_release(session, data)
