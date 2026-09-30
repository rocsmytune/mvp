"""开发用种子数据（构造数据，非真实人员）。幂等，可重复执行。

用法：在 backend/ 目录下执行  .venv/bin/python seed.py
"""

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User

# (工号, 姓名, 角色, 密码) —— 均为构造数据，仅用于开发/测试。
SEED_USERS = [
    ("000001", "管理员", "admin", "admin123"),
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
    finally:
        db.close()


if __name__ == "__main__":
    seed()
