import pytest

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.change_log import ChangeLog
from app.models.component import Component
from app.models.room import Room
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


def _add_user(db, employee_no, name, role, password):
    db.query(User).filter(User.employee_no == employee_no).delete(synchronize_session=False)
    u = User(
        employee_no=employee_no,
        name=name,
        role=role,
        password_hash=hash_password(password),
    )
    db.add(u)
    return u


def _cleanup_crud(db):
    # 按外键依赖逆序删除：change_logs(operator_id)/components(asset_id)/assets(cabinet_id)
    # /cabinets(owner_id,room_id)/rooms/users，避免 FK 违规。
    user_ids = [
        r[0]
        for r in db.query(User.id)
        .filter(User.employee_no.in_(["910001", "910002", "910003"]))
        .all()
    ]
    cab_ids = [
        r[0]
        for r in db.query(Cabinet.id)
        .filter(Cabinet.name.in_(["T-A01-01", "T-A01-02"]))
        .all()
    ]
    asset_ids = (
        [r[0] for r in db.query(Asset.id).filter(Asset.cabinet_id.in_(cab_ids)).all()]
        if cab_ids
        else []
    )
    if asset_ids:
        db.query(ChangeLog).filter(
            ChangeLog.target_type == "asset", ChangeLog.target_id.in_(asset_ids)
        ).delete(synchronize_session=False)
        db.query(Component).filter(Component.asset_id.in_(asset_ids)).delete(
            synchronize_session=False
        )
        db.query(Asset).filter(Asset.id.in_(asset_ids)).delete(
            synchronize_session=False
        )
    if cab_ids:
        db.query(Cabinet).filter(Cabinet.id.in_(cab_ids)).delete(
            synchronize_session=False
        )
    db.query(Room).filter(Room.code == "T-ROOM-1").delete(synchronize_session=False)
    if user_ids:
        db.query(ChangeLog).filter(ChangeLog.operator_id.in_(user_ids)).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.id.in_(user_ids)).delete(
            synchronize_session=False
        )
    db.commit()


@pytest.fixture
def crud_users():
    """三种角色用户 + 一个机房 + 两个机柜（分别归属 admin 与 owner），供 CRUD/权限测试。"""
    db = SessionLocal()
    try:
        admin = _add_user(db, "910001", "测试管理员", "admin", "admin-pass")
        owner = _add_user(db, "910002", "测试柜主", "cabinet_owner", "owner-pass")
        member = _add_user(db, "910003", "测试成员", "member", "member-pass")
        db.flush()
        room = Room(city="测试市", code="T-ROOM-1", zone="测试区")
        db.add(room)
        db.flush()
        cab_owner = Cabinet(
            room_id=room.id, name="T-A01-01", total_u=45, owner_id=owner.id
        )
        cab_admin = Cabinet(
            room_id=room.id, name="T-A01-02", total_u=45, owner_id=admin.id
        )
        db.add_all([cab_owner, cab_admin])
        db.commit()
        db.refresh(admin)
        db.refresh(owner)
        db.refresh(member)
        db.refresh(cab_owner)
        db.refresh(cab_admin)
        yield {
            "admin": admin,
            "owner": owner,
            "member": member,
            "cab_owner": cab_owner,
            "cab_admin": cab_admin,
        }
    finally:
        _cleanup_crud(db)
        db.close()
