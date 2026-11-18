"""公式 AI 录入相关请求模型：口述编译、测试数据行、批量校验。"""

from typing import Literal

from pydantic import BaseModel, Field


class BomFormulaDraftRequest(BaseModel):
    intent: str = Field(min_length=2, max_length=600, description="口述的业务逻辑，如「宽度>=1000时加120元，否则减10元」")
    target: Literal["qty", "extra"] = Field(default="qty", description="qty=3D用量公式, extra=附加成本公式")
    env: dict[str, float] = Field(default_factory=dict, description="沙盒尺寸参数，缺省用 2200x800x600x2.0")
    base_qty: float = 1.0
    qty: float = 1.0


class BomFormulaSheetRow(BaseModel):
    index: int = 0
    env: dict[str, float] = Field(default_factory=dict)
    expected: float | None = None
    note: str = ""


class BomFormulaBatchCheckRequest(BaseModel):
    expr: str = Field(min_length=1, max_length=400)
    rows: list[BomFormulaSheetRow] = Field(min_length=1, max_length=500)
