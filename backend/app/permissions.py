"""权限判断唯一入口。所有写接口与敏感读接口必须经过此模块校验。

规则（PRD 第2节）：
- 总管理员 admin：全权。
- 柜主 cabinet_owner：仅能操作 owner 为自己的机柜及其下设备/部件。
- 普通成员 member：只读。

骨架阶段为占位；后续每个接口接入时在此实现具体校验函数。
"""

ROLE_ADMIN = "admin"
ROLE_CABINET_OWNER = "cabinet_owner"
ROLE_MEMBER = "member"
