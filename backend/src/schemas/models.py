"""跨层共享 Pydantic v2 契约模型（对标前端 TypeScript Interface）。"""

from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, Field


class AuthContext(BaseModel):
    user_id: UUID
    username: str
    role: Literal["admin", "user", "readonly", "external_guest"] = "user"
    allowed_tools: list[str] = Field(default_factory=lambda: ["rag_search"])
    groups: list[str] = Field(default_factory=lambda: ["public"])


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class AgentState(BaseModel):
    run_id: UUID
    session_id: UUID
    user_id: UUID
    messages: list[ChatMessage] = Field(default_factory=list)
    step_count: int = 0
    max_steps: int = 6
    total_tokens: int = 0


class SSEEvent(BaseModel):
    event: Literal["thought", "tool_start", "tool_result", "citations", "action_cards", "approval_required", "token", "error", "done"]
    data: dict[str, Any] = Field(default_factory=dict)


class DevLoginRequest(BaseModel):
    username: str = "shenyang"
    role: Literal["admin", "user", "readonly", "external_guest"] = "admin"
    groups: list[str] | None = None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=4, max_length=128)
    role: Literal["admin", "user", "readonly", "external_guest"] = "user"
    groups: list[str] = Field(default_factory=lambda: ["public"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class SessionCreate(BaseModel):
    agent_name: str = "default"
    title: str = "新对话"


class SessionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    max_steps: int = Field(default=6, ge=1, le=12)
    top_k: int = Field(default=3, ge=1, le=10)
    min_score: float = Field(default=0.2, ge=0.0, le=1.0)
    enable_rag: bool = True


class MemoryCreate(BaseModel):
    memory_type: Literal["fact", "preference", "summary"] = "fact"
    content: str = Field(min_length=1, max_length=2000)
    importance: int = Field(default=3, ge=1, le=5)

class BomItemCreate(BaseModel):
    sku_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    category: Literal["PRODUCT", "SEMI_FINISHED", "BASE_MATERIAL", "OUTSOURCED", "LABOR", "MACHINE"] = "BASE_MATERIAL"
    sub_type: Literal["FIXED", "NON_FIXED", "INTERNAL", "EXTERNAL", "SPECIAL_PROCESS", "STANDARD"] = "FIXED"
    unit: str = Field(default="个", min_length=1, max_length=16)
    base_price: float = Field(default=0.0, ge=0.0)


class BomEdgeCreate(BaseModel):
    child_item_id: UUID
    qty_mode: Literal["FIXED", "FORMULA_3D"] = "FIXED"
    base_qty: float = Field(default=1.0, gt=0.0)
    formula_expr: str = ""
    extra_cost_expr: str = ""
    remnant_policy: Literal["CONTINUOUS", "WHOLE_PACK", "THRESHOLD_SCRAP"] = "CONTINUOUS"
    unit_pack_size: float = Field(default=1.0, gt=0.0)
    min_remnant: float = Field(default=0.0, ge=0.0)
    loss_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    float_factor: float = Field(default=1.0, ge=0.5, le=2.0)
    bom_group: Literal["人工", "材料", "机械"] = "材料"
    cost_group: Literal["半成品", "基材", "人工费"] = "基材"


class BomEdgeUpdate(BaseModel):
    qty_mode: Literal["FIXED", "FORMULA_3D"] = "FIXED"
    base_qty: float = Field(default=1.0, gt=0.0)
    formula_expr: str = ""
    extra_cost_expr: str = ""
    remnant_policy: Literal["CONTINUOUS", "WHOLE_PACK", "THRESHOLD_SCRAP"] = "CONTINUOUS"
    unit_pack_size: float = Field(default=1.0, gt=0.0)
    min_remnant: float = Field(default=0.0, ge=0.0)
    loss_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    float_factor: float = Field(default=1.0, ge=0.5, le=2.0)
    bom_group: Literal["人工", "材料", "机械"] = "材料"
    cost_group: Literal["半成品", "基材", "人工费"] = "基材"


class BomEdgeMove(BaseModel):
    parent_id: UUID


class BomEdgeBatchCreate(BaseModel):
    rows: list[BomEdgeCreate] = Field(min_length=1, max_length=50)


class BomCloneRequest(BaseModel):
    source_parent_id: UUID
    target_parent_id: UUID


class QuoteSaveRequest(BaseModel):
    root_id: UUID
    h: float = 2200.0
    w: float = 800.0
    d: float = 600.0
    t: float = 2.0
    margin_rate: float = Field(default=0.15, ge=0.0, le=0.8)
    tax_rate: float = Field(default=0.13, ge=0.0, le=0.3)
    note: str = ""


class StockCheckRequest(BaseModel):
    root_id: UUID
    h: float = 2200.0
    w: float = 800.0
    d: float = 600.0
    t: float = 2.0


class BomFormulaCheckRequest(BaseModel):
    expr: str = Field(min_length=1, max_length=512)
    env: dict[str, float] = Field(default_factory=lambda: {"H": 2200.0, "W": 800.0, "D": 600.0, "T": 2.0})


class SysMenuUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    group_name: str = Field(min_length=1, max_length=64)
    icon: str = Field(default="▣", max_length=16)
    sort_order: int = Field(default=10, ge=1, le=999)
    allowed_roles: list[str] = Field(default_factory=lambda: ["admin", "user"])
    is_enabled: bool = True
