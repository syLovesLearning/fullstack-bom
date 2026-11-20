import * as THREE from 'three'
import type { BomNode } from '../api/bomTypes'
import {
  getBrushedSteelMaterial, getCardboardBoxMaterial, getGalvanizedSlottedMaterial, getMatteDeckMaterial, getWoodMaterial,
} from './pbrMaterials'

export interface CabinetBuildOpts {
  h: number; w: number; d: number; t: number
  exploded: boolean; highlightSku: string; collision: boolean; root?: BomNode; showProps?: boolean
}

function findNode(root: BomNode | undefined, kw: string): BomNode | null {
  if (!root) return null
  if (root.sku_code.toUpperCase().includes(kw)) return root
  for (const c of root.children || []) { const hit = findNode(c, kw); if (hit) return hit }
  return null
}

function makePart(geo: THREE.BufferGeometry, mat: THREE.Material): THREE.Mesh {
  const mesh = new THREE.Mesh(geo, mat)
  mesh.castShadow = true; mesh.receiveShadow = true
  return mesh
}

function addOutline(mesh: THREE.Mesh, color = 0x64748b, opacity = 0.16) {
  mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({ color, transparent: true, opacity })))
}

function tagMesh(mesh: THREE.Mesh, node: BomNode | null, fallbackSku: string, fallbackName: string) {
  mesh.userData = node ? { sku: node.sku_code, name: node.name, qty: node.qty, subtotal: node.subtotal } : { sku: fallbackSku, name: fallbackName, qty: 1, subtotal: 0 }
}

function buildWorkbench(group: THREE.Group, opts: CabinetBuildOpts, s: number): string {
  const h = opts.h * s, w = opts.w * s, d = opts.d * s, topT = Math.max(0.025, opts.t * s)
  const exp = opts.exploded ? 0.28 : 0, hi = opts.highlightSku.toUpperCase(), root = opts.root
  const topBoard = makePart(new THREE.BoxGeometry(w, topT, d), getWoodMaterial(hi.includes('WOOD')))
  topBoard.position.set(0, h - topT / 2 + exp, 0)
  addOutline(topBoard, 0x78350f); tagMesh(topBoard, findNode(root, 'WOOD'), 'MAT-WOOD-25', '25mm实木桌面'); group.add(topBoard)

  const legH = h - topT - 0.024
  const legMat = getBrushedSteelMaterial(hi.includes('TUBE') || hi.includes('FRAME') ? 0x38bdf8 : 0x475569, 0.85, 0.26)
  const padMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.85, metalness: 0.15 })
  for (const sx of [-1, 1]) {
    for (const sz of [-1, 1]) {
      const lx = sx * (w / 2 - 0.06), lz = sz * (d / 2 - 0.06)
      const leg = makePart(new THREE.BoxGeometry(0.045, legH, 0.045), legMat)
      leg.position.set(lx, 0.024 + legH / 2, lz); addOutline(leg); tagMesh(leg, findNode(root, 'TUBE'), 'MAT-TUBE-40', '40×40镀锌方管'); group.add(leg)
      const pad = makePart(new THREE.CylinderGeometry(0.032, 0.038, 0.024, 16), padMat)
      pad.position.set(lx, 0.012 - exp * 0.4, lz); tagMesh(pad, findNode(root, 'FOOT'), 'OUT-FOOT-PAD', '重型防滑调节脚垫'); group.add(pad)
    }
  }
  const beamCnt = opts.w >= 1500 ? 2 : 1
  const beamMat = getBrushedSteelMaterial(hi.includes('BEAM') ? 0x22d3ee : 0x64748b, 0.82, 0.28)
  for (let b = 0; b < beamCnt; b++) {
    const bz = beamCnt === 1 ? 0 : (b === 0 ? -d * 0.22 : d * 0.22)
    const beam = makePart(new THREE.BoxGeometry(w - 0.12, 0.04, 0.03), beamMat)
    beam.position.set(0, 0.22 - exp * 0.2, bz); addOutline(beam); tagMesh(beam, findNode(root, 'BEAM'), 'MAT-BEAM-MID', '桌面防塌腰加强横梁'); group.add(beam)
  }
  return opts.w > 2400 && opts.t < 20 ? '结构预警：桌宽超 2400mm 且板厚 < 20mm，桌面易弯曲！' : ''
}

function buildStorageRack(group: THREE.Group, opts: CabinetBuildOpts, s: number): string {
  const h = opts.h * s, w = opts.w * s, d = opts.d * s, exp = opts.exploded ? 0.28 : 0
  const hi = opts.highlightSku.toUpperCase(), root = opts.root
  const upNode = findNode(root, 'UPRIGHT') || findNode(root, 'C-STEEL')
  const beamNode = findNode(root, 'BEAM-ORANGE'), deckNode = findNode(root, 'DECK'), layerNode = findNode(root, 'LAYER')
  const layers = layerNode ? Math.min(6, Math.max(2, Math.round(layerNode.qty))) : 4

  const upMat = getGalvanizedSlottedMaterial(1, Math.max(4, Math.round(opts.h / 180)), hi.includes('UPRIGHT') || hi.includes('STEEL'))
  for (const sx of [-1, 1]) {
    for (const sz of [-1, 1]) {
      const col = makePart(new THREE.BoxGeometry(0.052, h, 0.045), upMat)
      col.position.set(sx * (w / 2 + exp * 0.4), h / 2, sz * (d / 2))
      tagMesh(col, upNode, 'MAT-C-STEEL', '80×60冲孔镀锌立柱'); group.add(col)
    }
  }

  const bMat = getGalvanizedSlottedMaterial(Math.max(4, Math.round(opts.w / 180)), 1, hi.includes('BEAM'))
  const dMat = getMatteDeckMaterial(hi.includes('DECK'))
  const cols = Math.max(1, Math.min(5, Math.floor((w - 0.1) / 0.36)))
  const boxPositions: THREE.Vector3[] = []
  const boxW = Math.min(0.30, (w - 0.14) / cols - 0.04), boxH = Math.min(0.22, (h / layers) * 0.52), boxD = Math.max(0.22, Math.min(0.42, d - 0.14))

  for (let i = 0; i < layers; i++) {
    const ly = 0.12 + (i / Math.max(1, layers - 1)) * (h - 0.52)
    for (const sz of [-1, 1]) {
      const beam = makePart(new THREE.BoxGeometry(w, 0.05, 0.025), bMat)
      beam.position.set(0, ly, sz * (d / 2 + exp * 0.2)); tagMesh(beam, beamNode, 'MAT-BEAM-ORANGE', '冲孔承载横梁'); group.add(beam)
    }
    const deck = makePart(new THREE.BoxGeometry(w - 0.04, 0.018, d - 0.03), dMat)
    deck.position.set(0, ly + 0.02 + exp * 0.3, 0); tagMesh(deck, deckNode, 'MAT-DECK-STEEL', '哑光黑钢制层板'); group.add(deck)
    for (let c = 0; c < cols; c++) {
      if ((i + c) % 4 === 3 && cols > 2) continue
      const bx = -w / 2 + 0.08 + boxW / 2 + c * ((w - 0.16) / cols)
      boxPositions.push(new THREE.Vector3(bx, ly + 0.03 + boxH / 2 + exp * 0.32, 0))
    }
  }

  if (opts.showProps !== false && boxPositions.length) {
    const boxes = new THREE.InstancedMesh(new THREE.BoxGeometry(boxW, boxH, boxD), getCardboardBoxMaterial(), boxPositions.length)
    boxes.castShadow = true; boxes.receiveShadow = true
    const dummy = new THREE.Object3D()
    boxPositions.forEach((p, idx) => { dummy.position.copy(p); dummy.updateMatrix(); boxes.setMatrixAt(idx, dummy.matrix) })
    group.add(boxes)
  }
  return opts.w > 2600 ? '跨距预警：货架单跨 > 2600mm，建议加厚横梁或增设中立柱！' : ''
}

export function buildIndustrialCabinet(group: THREE.Group, opts: CabinetBuildOpts): string {
  const s = 0.001, h = opts.h * s, w = opts.w * s, d = opts.d * s
  const sku = (opts.root?.sku_code || '').toUpperCase()
  const alert = sku.includes('RACK') ? buildStorageRack(group, opts, s) : buildWorkbench(group, opts, s)
  const lineMat = new THREE.LineBasicMaterial({ color: 0x0284c7, transparent: true, opacity: 0.75 })
  for (const [a, b] of [
    [new THREE.Vector3(-w / 2 - 0.08, 0, d / 2), new THREE.Vector3(-w / 2 - 0.08, h, d / 2)],
    [new THREE.Vector3(-w / 2, 0.01, d / 2 + 0.08), new THREE.Vector3(w / 2, 0.01, d / 2 + 0.08)],
    [new THREE.Vector3(w / 2 + 0.08, 0.01, -d / 2), new THREE.Vector3(w / 2 + 0.08, 0.01, d / 2)],
  ]) {
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), lineMat))
  }
  return alert
}
