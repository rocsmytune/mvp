"""开发用种子数据（构造数据，非真实人员）。幂等，可重复执行。

用法：在 backend/ 目录下执行  .venv/bin/python seed.py
演示数据（机房/机柜）默认不建，需显式设置环境变量 SEED_DEMO=1 才会创建。
"""

import os

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.cabinet import Cabinet
from app.models.dictionary import Dictionary
from app.models.room import Room
from app.models.user import User

# (工号, 姓名, 角色, 密码) —— 均为构造数据，仅用于开发/测试。
SEED_USERS = [
    ("000004", "系统管理员", "system_admin", "sysadmin123"),
    ("000001", "物料管理员", "material_admin", "admin123"),
    ("000002", "柜主甲", "cabinet_owner", "owner123"),
    ("000003", "成员乙", "member", "member123"),
]

# (kind, code, label, sort_no) —— 字典基础值，可在页面编辑/新增，禁止删除。
SEED_DICTIONARIES = [
    ("asset_status", "in_use", "在用", 0),
    ("component_category", "硬盘", "硬盘", 1),
    ("component_category", "内存", "内存", 2),
    ("component_category", "主板", "主板", 3),
    ("component_category", "光模块", "光模块", 4),
    ("component_category", "RAID", "RAID", 5),
    ("component_category", "网卡", "网卡", 6),
    ("component_category", "BMC插卡", "BMC插卡", 7),
    ("component_category", "CPU", "CPU", 8),
    ("component_category", "线缆", "线缆", 9),
    ("component_category", "风扇板", "风扇板", 10),
]


def seed() -> None:
    db = SessionLocal()
    try:
        for employee_no, name, role, password in SEED_USERS:
            user = db.query(User).filter(User.employee_no == employee_no).first()
            if user is None:
                db.add(
                    User(
                        employee_no=employee_no,
                        name=name,
                        role=role,
                        password_hash=hash_password(password),
                    )
                )
                print(f"创建用户 {employee_no} {name} ({role})")
            else:
                print(f"已存在 {employee_no} {name}，跳过")
        db.commit()

        # 字典基础值（幂等，按 kind/code 判断，已存在则跳过）。
        for kind, code, label, sort_no in SEED_DICTIONARIES:
            exists = (
                db.query(Dictionary)
                .filter(Dictionary.kind == kind, Dictionary.code == code)
                .first()
            )
            if exists is None:
                db.add(Dictionary(kind=kind, code=code, label=label, sort_no=sort_no))
                print(f"创建字典 {kind}/{code} = {label}")
        db.commit()

        # 演示机房 + 机柜（构造数据）：A01-01 归属柜主甲，A01-02 归属物料管理员。
        # 仅开发/演示用，生产默认不建（SEED_DEMO=1 时才会创建）。
        if os.environ.get("SEED_DEMO") != "1":
            print("跳过演示数据（设置 SEED_DEMO=1 可创建演示机房/机柜）")
            return
        owner = db.query(User).filter(User.employee_no == "000002").first()
        admin = db.query(User).filter(User.employee_no == "000001").first()
        room = db.query(Room).filter(Room.code == "TEST-01").first()
        if room is None:
            room = Room(city="演示市", code="TEST-01", zone="绿区")
            db.add(room)
            db.flush()
            print(f"创建机房 {room.code}（{room.zone}）")
        for name, owner_id in [("A01-01", owner.id if owner else None), ("A01-02", admin.id if admin else None)]:
            if db.query(Cabinet).filter(Cabinet.room_id == room.id, Cabinet.name == name).first() is None:
                db.add(Cabinet(room_id=room.id, name=name, total_u=45, owner_id=owner_id))
                print(f"创建机柜 {name}（owner={owner_id}）")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
