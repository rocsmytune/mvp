"""开发用种子数据（构造数据，非真实人员）。幂等，可重复执行。

用法：在 backend/ 目录下执行  .venv/bin/python seed.py
"""

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.cabinet import Cabinet
from app.models.room import Room
from app.models.user import User

# (工号, 姓名, 角色, 密码) —— 均为构造数据，仅用于开发/测试。
SEED_USERS = [
    ("000004", "系统管理员", "system_admin", "sysadmin123"),
    ("000001", "物料管理员", "material_admin", "admin123"),
    ("000002", "柜主甲", "cabinet_owner", "owner123"),
    ("000003", "成员乙", "member", "member123"),
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

        # 演示机房 + 机柜（构造数据）：A01-01 归属柜主甲，A01-02 归属物料管理员
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
