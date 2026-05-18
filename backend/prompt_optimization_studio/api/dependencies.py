from fastapi import Depends
from sqlalchemy.orm import Session

from prompt_optimization_studio.db.session import get_db_session


DbSession = Session


def get_db(session: DbSession = Depends(get_db_session)) -> DbSession:
    return session
