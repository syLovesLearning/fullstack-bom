import * as THREE from 'three'
import type { BomNode } from '../api/bomTypes'

export interface CabinetBuildOpts {
  h: number; w: number; d: number; t: number
  exploded: boolean; highlightSku: string; collision: boolean; root?: BomNode
}

function findNode(root: BomNode | undefined, kw: string): BomNode | null {
  if (!root) return null
  if (root.sku_code.toUpperCase().includes(kw)) return root
  for (const c of root.children || []) { const hit = findNode(c, kw); if (hit) return hit }
  return null
}

function makeBox(w: number, h: number, d: number, color: number, metal = 0.45, rough = 0.42, opacity = 1): THREE.Mesh {
  return new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshStandardMaterial({ color, metalness: metal, roughness: rough, transparent: opacity < 1, opacity }),
  )
}

function addOutline(mesh: THREE.Mesh, color = 0x94a3b8) {
  mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.4 })))
}

function tagMesh(mesh: THREE.Mesh, node: BomNode | null, fallbackSku: string, fallbackName: string) {
  mesh.userData = node ? { sku: node.sku_code, name: node.name, qty: node.qty, subtotal: node.subtotal } : { sku: fallbackSku, name: fallbackName, qty: 1, subtotal: 0 }
}

function buildWorkbench(group: THREE.Group, opts: CabinetBuildOpts, s: number): string {
  const h = opts.h * s, w = opts.w * s, d = opts.d * s, topT = Math.max(0.025, opts.t * s)
  const exp = opts.exploded ? 0.28 : 0, hi = opts.highlightSku.toUpperCase(), root = opts.root

  // 1. 实木橡木桌面
  const woodNode = findNode(root, 'WOOD')
  const topCol = hi.includes('WOOD') ? 0xfbbf24 : 0xc28e5c
  const topBoard = makeBox(w, topT, d, topCol, 0.1, 0.65)
  topBoard.position.set(0, h - topT / 2 + exp, 0)
  addOutline(topBoard, 0x78350f); tagMesh(topBoard, woodNode, 'MAT-WOOD-25', '25mm实木桌面'); group.add(topBoard)

  // 2. 四根镀锌方管桌腿 + 调节脚垫
  const tubeNode = findNode(root, 'TUBE')
  const padNode = findNode(root, 'FOOT')
  const legH = h - topT - 0.02
  const legCol = hi.includes('TUBE') || hi.includes('FRAME') ? 0x38bdf8 : 0x334155
  for (const sx of [-1, 1]) {
    for (const sz of [-1, 1]) {
      const lx = sx * (w / 2 - 0.06), lz = sz * (d / 2 - 0.06)
      const leg = makeBox(0.045, legH, 0.045, legCol, 0.7, 0.3)
      leg.position.set(lx, 0.02 + legH / 2, lz); addOutline(leg); tagMesh(leg, tubeNode, 'MAT-TUBE-40', '40×40镀锌方管'); group.add(leg)
      const pad = makeBox(0.065, 0.02, 0.065, 0x0f172a, 0.2, 0.8)
      pad.position.set(lx, 0.01 - exp * 0.4, lz); tagMesh(pad, padNode, 'OUT-FOOT-PAD', '重型防滑调节脚垫'); group.add(pad)
    }
  }

  // 3. 底部加强横梁（iif(W >= 1500, 2, 1) 视觉联动）
  const beamNode = findNode(root, 'BEAM')
  const beamCnt = opts.w >= 1500 ? 2 : 1
  const beamCol = hi.includes('BEAM') ? 0x22d3ee : 0x475569
  for (let b = 0; b < beamCnt; b++) {
    const bz = beamCnt === 1 ? 0 : (b === 0 ? -d * 0.22 : d * 0.22)
    const beam = makeBox(w - 0.12, 0.04, 0.03, beamCol, 0.7, 0.3)
    beam.position.set(0, 0.22 - exp * 0.2, bz); addOutline(beam); tagMesh(beam, beamNode, 'MAT-BEAM-MID', '桌面防塌腰加强横梁'); group.add(beam)
  }
  return opts.w > 2400 && opts.t < 20 ? '结构预警：桌宽超 2400mm 且板厚 < 20mm，桌面易弯曲！' : ''
}

function buildStorageRack(group: THREE.Group, opts: CabinetBuildOpts, s: number): string {
  const h = opts.h * s, w = opts.w * s, d = opts.d * s, exp = opts.exploded ? 0.28 : 0
  const hi = opts.highlightSku.toUpperCase(), root = opts.root
  const upNode = findNode(root, 'UPRIGHT') || findNode(root, 'C-STEEL')
  const beamNode = findNode(root, 'BEAM-ORANGE')
  const deckNode = findNode(root, 'DECK')
  const layerNode = findNode(root, 'LAYER')
  const layers = layerNode ? Math.min(6, Math.max(2, Math.round(layerNode.qty))) : 4

  // 1. 4 根工业蓝 C 型钢立柱 + 地脚螺栓
  const upCol = hi.includes('UPRIGHT') || hi.includes('STEEL') ? 0x38bdf8 : 0x1d4ed8
  for (const sx of [-1, 1]) {
    for (const sz of [-1, 1]) {
      const col = makeBox(0.06, h, 0.05, upCol, 0.65, 0.35)
      col.position.set(sx * (w / 2 + exp * 0.4), h / 2, sz * (d / 2))
      addOutline(col, 0x93c5fd); tagMesh(col, upNode, 'MAT-C-STEEL', '80×60C型钢立柱'); group.add(col)
    }
  }

  // 2. 多层工业橙横梁 + 镀锌钢层板
  const bCol = hi.includes('BEAM') ? 0xfacc15 : 0xf97316
  const dCol = hi.includes('DECK') ? 0x38bdf8 : 0x94a3b8
  for (let i = 0; i < layers; i++) {
    const ly = 0.22 + ((i + 0.2) / layers) * (h - 0.35)
    for (const sz of [-1, 1]) {
      const beam = makeBox(w, 0.06, 0.035, bCol, 0.4, 0.4)
      beam.position.set(0, ly, sz * (d / 2 + exp * 0.2)); addOutline(beam, 0xfdba74)
      tagMesh(beam, beamNode, 'MAT-BEAM-ORANGE', '重型抱焊橙色横梁'); group.add(beam)
    }
    const deck = makeBox(w - 0.08, 0.02, d - 0.04, dCol, 0.7, 0.35)
    deck.position.set(0, ly + 0.03 + exp * 0.35, 0); addOutline(deck)
    tagMesh(deck, deckNode, 'MAT-DECK-STEEL', '镀锌钢制层板'); group.add(deck)
  }
  return opts.w > 2600 ? '跨距预警：货架单跨 > 2600mm，建议加厚横梁或增设中立柱！' : ''
}

export function buildIndustrialCabinet(group: THREE.Group, opts: CabinetBuildOpts): string {
  const s = 0.001, h = opts.h * s, w = opts.w * s, d = opts.d * s
  const sku = (opts.root?.sku_code || '').toUpperCase()
  const alert = sku.includes('RACK') ? buildStorageRack(group, opts, s) : buildWorkbench(group, opts, s)

  const lineMat = new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.7 })
  for (const [a, b] of [
    [new THREE.Vector3(-w / 2 - 0.08, 0, d / 2), new THREE.Vector3(-w / 2 - 0.08, h, d / 2)],
    [new THREE.Vector3(-w / 2, 0.01, d / 2 + 0.08), new THREE.Vector3(w / 2, 0.01, d / 2 + 0.08)],
    [new THREE.Vector3(w / 2 + 0.08, 0.01, -d / 2), new THREE.Vector3(w / 2 + 0.08, 0.01, d / 2)],
  ]) {
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), lineMat))
  }
  return alert
}
