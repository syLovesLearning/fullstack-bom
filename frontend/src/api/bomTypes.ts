/** BOM 领域类型与默认规则：与后端 schemas/models.py 对齐，供 API 与组件共用。 */

export interface BomItem {
  id: string
  sku_code: string
  name: string
  category: 'PRODUCT' | 'SEMI_FINISHED' | 'BASE_MATERIAL' | 'OUTSOURCED' | 'LABOR' | 'MACHINE'
  sub_type: 'FIXED' | 'NON_FIXED' | 'INTERNAL' | 'EXTERNAL' | 'SPECIAL_PROCESS' | 'STANDARD'
  unit: string
  base_price: number
  created_at: string
}

export interface BomEdge {
  id: string
  parent_item_id: string
  child_item_id: string
  child_sku: string
  child_name: string
  child_category: string
  child_sub_type: string
  child_unit: string
  child_price: number
  qty_mode: 'FIXED' | 'FORMULA_3D'
  base_qty: number
  formula_expr: string
  extra_cost_expr?: string
  remnant_policy?: 'CONTINUOUS' | 'WHOLE_PACK' | 'THRESHOLD_SCRAP'
  unit_pack_size?: number
  min_remnant?: number
  loss_rate?: number
  float_factor: number
  bom_group: '人工' | '材料' | '机械'
  cost_group: '半成品' | '基材' | '人工费'
}

/** 拖拽落地/就地编辑时提交的完整边规则（与后端 BomEdgeCreate/Update 对齐）。 */
export interface BomEdgeRule {
  qty_mode: 'FIXED' | 'FORMULA_3D'
  base_qty: number
  formula_expr: string
  extra_cost_expr: string
  remnant_policy: 'CONTINUOUS' | 'WHOLE_PACK' | 'THRESHOLD_SCRAP'
  unit_pack_size: number
  min_remnant: number
  loss_rate: number
  float_factor: number
  bom_group: '人工' | '材料' | '机械'
  cost_group: '半成品' | '基材' | '人工费'
}

/** 递归 rollup 树节点：children 仍为同型节点，支持任意深度渲染。 */
export interface BomNode {
  id: string
  sku_code: string
  name: string
  category: string
  sub_type?: string
  unit: string
  base_price: number
  qty: number
  subtotal: number
  children: BomNode[]
  edge_id?: string
  qty_mode?: 'FIXED' | 'FORMULA_3D'
  formula_expr?: string
  extra_cost_expr?: string
  remnant_policy?: string
  float_factor?: number
  remnant_note?: string
  scrap_qty?: number
  extra_cost?: number
}

export interface BomRollupResponse {
  root: BomNode
  cost_summary: Record<string, number>
  bom_summary: Record<string, number>
}

/** 从物料库拖入时的默认规则：固定用量 1、连续套裁、按物料类别自动归组。 */
export function makeDefaultRule(childItemId: string, category: string): BomEdgeRule & { child_item_id: string } {
  const isLabor = category === 'LABOR' || category === 'MACHINE'
  return {
    child_item_id: childItemId, qty_mode: 'FIXED', base_qty: 1, formula_expr: '', extra_cost_expr: '',
    remnant_policy: 'CONTINUOUS', unit_pack_size: 1, min_remnant: 0, loss_rate: 0, float_factor: 1,
    bom_group: isLabor ? '人工' : '材料', cost_group: isLabor ? '人工费' : '基材',
  }
}

export interface QuoteSnapshotItem {
  id: string
  quote_no: string
  root_name: string
  direct_cost: number
  final_price: number
  note: string
  created_at: string
}

export interface StockCheckItem {
  sku_code: string
  name: string
  unit: string
  required_qty: number
  stock_qty: number
  warehouse: string
  status: '齐套' | '缺料' | '未建档'
}

export interface FormulaCheckResult {
  ok: boolean
  value: number | null
  error: string
}

export interface WhereUsedItem {
  parent_id: string
  parent_sku: string
  parent_name: string
  parent_category: string
  edge_id: string
  qty_mode: string
  base_qty: number
}
