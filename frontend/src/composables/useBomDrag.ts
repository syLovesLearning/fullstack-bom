/** BOM 拖拽共享状态：载荷、树索引、投放合法性与撤销栈（模块级单例，跨组件共享）。 */

import { ref } from 'vue'
import type { BomItem, BomNode } from '../api/bomClient'

export const MAX_DEPTH = 4
const MAX_UNDO = 50

export type DragPayload =
  | { kind: 'new'; items: BomItem[] }
  | { kind: 'move'; node: BomNode; parentId: string; key: string }

export interface NodeMeta {
  node: BomNode
  depth: number
  parentId: string | null
  parentKey: string | null
}

export interface TreeIndex {
  byKey: Map<string, NodeMeta>
  descendants: Map<string, Set<string>>
  height: Map<string, number>
  chainOf: (key: string) => BomNode[]
}

export interface DropVerdict {
  ok: boolean
  reason: string
}

export interface UndoEntry {
  label: string
  run: () => Promise<void>
}

const payload = ref<DragPayload | null>(null)
const hoverKey = ref('')
const undoStack = ref<UndoEntry[]>([])

/** 同物料可挂多行，故以 edge_id 为唯一键；根节点无 edge_id，用 root:id 兜底。 */
export function nodeKey(node: BomNode): string {
  return node.edge_id || `root:${node.id}`
}

/** depth 从根 1 起；descendants 存后代「物料 id」集合用于环检测；height 用于深度限制。 */
export function buildTreeIndex(root: BomNode | null): TreeIndex {
  const byKey = new Map<string, NodeMeta>()
  const descendants = new Map<string, Set<string>>()
  const height = new Map<string, number>()

  function walk(node: BomNode, depth: number, parentId: string | null, parentKey: string | null): number {
    const key = nodeKey(node)
    byKey.set(key, { node, depth, parentId, parentKey })
    const ids = new Set<string>([node.id])
    let childMax = 0
    for (const child of node.children || []) {
      const childKey = nodeKey(child)
      const h = walk(child, depth + 1, node.id, key)
      childMax = Math.max(childMax, h)
      for (const id of descendants.get(childKey) || []) ids.add(id)
    }
    descendants.set(key, ids)
    const h = 1 + childMax
    height.set(key, h)
    return h
  }
  if (root) walk(root, 1, null, null)

  const chainOf = (key: string): BomNode[] => {
    const out: BomNode[] = []
    let cur = byKey.get(key)
    while (cur) {
      out.unshift(cur.node)
      cur = cur.parentKey ? byKey.get(cur.parentKey) : undefined
    }
    return out
  }
  return { byKey, descendants, height, chainOf }
}

export function useBomDrag() {
  function start(p: DragPayload) {
    payload.value = p
  }
  function end() {
    payload.value = null
    hoverKey.value = ''
  }

  /** 拖起瞬间即可判断：环/深度/自身/叶子节点全部本地算，无需请求后端。 */
  function verdict(targetKey: string, index: TreeIndex): DropVerdict {
    const p = payload.value
    if (!p) return { ok: false, reason: '没有拖拽内容' }
    const target = index.byKey.get(targetKey)
    if (!target) return { ok: false, reason: '无效投放目标' }
    if (!['PRODUCT', 'SEMI_FINISHED'].includes(target.node.category)) {
      return { ok: false, reason: '人工/机械为成本叶子，不可再挂子件' }
    }
    if (p.kind === 'move') {
      if (p.node.id === target.node.id) return { ok: false, reason: '不能拖到自己' }
      if (p.parentId === target.node.id) return { ok: false, reason: '位置未变' }
      if (index.descendants.get(p.key)?.has(target.node.id)) {
        return { ok: false, reason: '会形成 BOM 环路' }
      }
      const h = index.height.get(p.key) ?? 1
      if (target.depth + h > MAX_DEPTH) return { ok: false, reason: `超过 ${MAX_DEPTH} 级深度` }
    } else if (target.depth + 1 > MAX_DEPTH) {
      return { ok: false, reason: `超过 ${MAX_DEPTH} 级深度` }
    }
    return { ok: true, reason: '' }
  }

  function pushUndo(entry: UndoEntry) {
    undoStack.value.push(entry)
    if (undoStack.value.length > MAX_UNDO) undoStack.value.shift()
  }

  async function undo(): Promise<string | null> {
    const entry = undoStack.value.pop()
    if (!entry) return null
    await entry.run()
    return entry.label
  }

  return { payload, hoverKey, undoStack, start, end, verdict, pushUndo, undo }
}
