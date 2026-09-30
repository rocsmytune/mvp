"""本地认证实现。业务代码只依赖 get_current_user，替换为 SSO 时无需改动业务代码。"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token, verify_password
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


def authenticate_user(db: Session, employee_no: str, password: str) -> User | None:
    """校验工号+密码，成功返回用户，失败返回 None。"""
    user = (
        db.query(User)
        .filter(User.employee_no == employee_no, User.active.is_(True))
        .first()
    )
    if user is None or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization: Bearer <token> 解析当前用户，并校验其仍有效。"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    employee_no = decode_access_token(credentials.credentials)
    if employee_no is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期"
        )
    user = (
        db.query(User)
        .filter(User.employee_no == employee_no, User.active.is_(True))
        .first()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用"
        )
    return user
