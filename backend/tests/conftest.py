import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 独立测试库：测试不得污染开发库（docker 里的 mvp）。
# 在导入任何 app 模块之前，先把 DATABASE_URL 指向测试库，让 app.core.db 的
# engine 与后续 alembic 都连测试库。默认 mvp_test（与开发库同服务器），
# 可用环境变量 TEST_DATABASE_URL 覆盖。
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://mvp:mvp@localhost:5432/mvp_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # 必须早于任何 app 导入

import pytest
from sqlalchemy import create_engine, or_, text
from sqlalchemy.engine import make_url

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.change_log import ChangeLog
from app.models.component import Component
from app.models.import_batch import ImportBatch
from app.models.room import Room
from app.models.user import User

TEST_EMPLOYEE_NO = "900001"
TEST_PASSWORD = "test-password-123"


def _maintenance_url(db_url: str) -> str:
    """连维护库 postgres，用于建/删测试库（不能在被删库自身内操作）。"""
    return make_url(db_url).set(database="postgres").render_as_string(hide_password=False)


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    """会话级：重建独立测试库并跑迁移，本次运行全程使用该库。

    表结构只用 `alembic upgrade head`（遵守 CLAUDE.md，禁止 create_all）；
    每次运行先 DROP + CREATE，保证干净起点，不残留上次数据。
    """
    db_name = make_url(TEST_DATABASE_URL).database
    admin = create_engine(_maintenance_url(TEST_DATABASE_URL), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin.dispose()

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
    )
    yield


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
    # 按外键依赖逆序删除，避免 FK 违规。测试产生的 change_logs 均以测试用户为 operator，
    # 故先按 operator 清掉全部 change_logs，再删部件/设备/机柜/机房/用户。
    user_ids = [
        r[0]
        for r in db.query(User.id)
        .filter(User.employee_no.in_(["910001", "910002", "910003"]))
        .all()
    ]
    room_ids = [
        r[0]
        for r in db.query(Room.id)
        .filter(or_(Room.code == "T-ROOM-1", Room.code.like("T-RM-%")))
        .all()
    ]
    cab_filters = [
        Cabinet.name.in_(["T-A01-01", "T-A01-02"]),
        Cabinet.name.like("T-CAB-%"),
    ]
    if room_ids:
        cab_filters.append(Cabinet.room_id.in_(room_ids))
    cab_ids = [
        r[0] for r in db.query(Cabinet.id).filter(or_(*cab_filters)).all()
    ]
    asset_ids = (
        [r[0] for r in db.query(Asset.id).filter(Asset.cabinet_id.in_(cab_ids)).all()]
        if cab_ids
        else []
    )
    if user_ids:
        db.query(ChangeLog).filter(ChangeLog.operator_id.in_(user_ids)).delete(
            synchronize_session=False
        )
        db.query(ImportBatch).filter(ImportBatch.operator_id.in_(user_ids)).delete(
            synchronize_session=False
        )
    # 待整理池设备（cabinet_id 为空）无法按机柜定位，按测试标记 sn 删除。
    db.query(Asset).filter(Asset.sn.like("T-POOL-%")).delete(synchronize_session=False)
    if asset_ids:
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
    if room_ids:
        db.query(Room).filter(Room.id.in_(room_ids)).delete(
            synchronize_session=False
        )
    if user_ids:
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
