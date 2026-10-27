from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..core.security import decode_token
from ..models.user import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    sub = decode_token(creds.credentials)
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == sub).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_workspace_id(user: User, db: Session) -> str:
    ws = user.workspaces[0] if user.workspaces else None
    if not ws:
        # auto-create
        from ..models.user import Workspace
        ws = Workspace(owner_id=user.id, name="My Studio")
        db.add(ws)
        db.commit()
        db.refresh(ws)
    return ws.id