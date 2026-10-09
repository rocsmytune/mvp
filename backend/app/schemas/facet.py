from pydantic import BaseModel


class FacetValue(BaseModel):
    """列筛选 facet 的单个去重值及其出现次数。"""

    value: str
    count: int
