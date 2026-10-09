"""列筛选（facet）聚合：给定查询与列，返回去重值 + 计数。

供设备/物料列表页的表头漏斗筛选展示「相同累加」的值清单使用。
"""
from sqlalchemy import func
from sqlalchemy.orm import Query

FACET_LIMIT = 200  # 每列最多返回的去重值数量，超出部分通过搜索框内前端过滤


def facet_values(query: Query, column) -> list[dict]:
    """按列 group by 计数，剔除 NULL 与空串，按计数倒序返回 {value, count}。"""
    rows = (
        query.with_entities(column, func.count())
        .filter(column.isnot(None), column != "")
        .group_by(column)
        .order_by(func.count().desc(), column)
        .limit(FACET_LIMIT)
        .all()
    )
    return [{"value": v, "count": c} for v, c in rows]
