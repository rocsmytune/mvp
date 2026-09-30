"""本地认证（骨架阶段为占位实现）。

CLAUDE.md 要求：认证逻辑只放在 auth/，业务代码只依赖 get_current_user。
后续「登录」功能会在此实现真实的工号+密码校验与令牌签发；
本文件当前仅提供 get_current_user 契约，返回一个开发用管理员，方便骨架跑通。
"""

from app.models.user import User


def get_current_user() -> User:
    """TODO: 解析请求令牌并校验；骨架阶段先返回固定开发用户。"""
    return User(employee_no="000000", name="开发管理员", role="admin", dept_id=1)
