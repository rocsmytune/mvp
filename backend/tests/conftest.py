import pytest

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User

TEST_EMPLOYEE_NO = "900001"
TEST_PASSWORD = "test-password-123"


@pytest.fixture
def test_user():
    """在开发库中创建一个测试用户，测试结束后清理（幂等）。"""
    db = SessionLocal()
    try:
        db.query(User).filter(User.employee_no == TEST_EMPLOYEE_NO).delete()
        db.commit()
        user = User(
            employee_no=TEST_EMPLOYEE_NO,
            name="测试用户",
            role="admin",
            password_hash=hash_password(TEST_PASSWORD),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        yield user
    finally:
        db.query(User).filter(User.employee_no == TEST_EMPLOYEE_NO).delete()
        db.commit()
        db.close()
