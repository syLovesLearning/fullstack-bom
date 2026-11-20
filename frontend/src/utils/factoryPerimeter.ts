import * as THREE from 'three'

export interface FactoryStats {
  widthM: number
  lengthM: number
  heightM: number
  railHeightM: number
  columnCount: number
}

function addInstancedBoxes(
  group: THREE.Group,
  size: [number, number, number],
  mat: THREE.Material,
  positions: [number, number, number][],
) {
  if (!positions.length) return
  const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(...size), mat, positions.length)
  const d = new THREE.Object3D()
  positions.forEach(([x, y, z], i) => {
    d.position.set(x, y, z)
    d.updateMatrix()
    mesh.setMatrixAt(i, d.matrix)
  })
  group.add(mesh)
}

export function buildFactoryPerimeter(group: THREE.Group): FactoryStats {
  const W = 90, L = 140, H = 14, RAIL_Y = 10.5, BAY = 10
  const hw = W / 2, hl = L / 2

  // 1. 90m x 140m 厂区混凝土地坪（仅铺设基础地面与结构柱网刻度）
  const slab = new THREE.Mesh(
    new THREE.PlaneGeometry(W + 6, L + 6),
    new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.9, metalness: 0.05 }),
  )
  slab.rotation.x = -Math.PI / 2
  group.add(slab)
  const grid = new THREE.GridHelper(140, 14, 0x64748b, 0x334155)
  grid.position.y = 0.02
  group.add(grid)

  // 2. 四周混凝土基础矮墙 (高 1.8m) + 钢结构深蓝灰外墙板 (1.8m ~ 14m)
  const concMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.92, metalness: 0.02 })
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.55, metalness: 0.45, side: THREE.DoubleSide })

  // 左右两侧 140m 墙体
  for (const sx of [-1, 1]) {
    const x = sx * hw
    const plinth = new THREE.Mesh(new THREE.BoxGeometry(0.45, 1.8, L), concMat)
    plinth.position.set(x, 0.9, 0); group.add(plinth)
    const upper = new THREE.Mesh(new THREE.BoxGeometry(0.22, H - 1.8, L), wallMat)
    upper.position.set(x, 1.8 + (H - 1.8) / 2, 0); group.add(upper)
  }

  // 前后两端 90m 山墙（北端 z=-70 预留 12m×6m 厂区大门洞口，南端 z=+70 留通透观察口或矮墙）
  for (const sz of [-1, 1]) {
    const z = sz * hl
    for (const segX of [-25.5, 25.5]) {
      const pEnd = new THREE.Mesh(new THREE.BoxGeometry(39, 1.8, 0.45), concMat)
      pEnd.position.set(segX, 0.9, z); group.add(pEnd)
      const uEnd = new THREE.Mesh(new THREE.BoxGeometry(39, H - 1.8, 0.22), wallMat)
      uEnd.position.set(segX, 1.8 + (H - 1.8) / 2, z); group.add(uEnd)
    }
    const header = new THREE.Mesh(new THREE.BoxGeometry(12, H - 6.5, 0.22), wallMat)
    header.position.set(0, 6.5 + (H - 6.5) / 2, z); group.add(header)
  }

  // 3. 四周钢混立柱 + 采光窗带 + 牛腿托架 (全部 InstancedMesh 合批，零 DrawCall 浪费)
  const colMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.42, metalness: 0.65 })
  const corbelMat = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.5, metalness: 0.6 })
  const winMat = new THREE.MeshStandardMaterial({ color: 0xe0f2fe, emissive: 0x38bdf8, emissiveIntensity: 0.22, roughness: 0.2 })

  const pierPos: [number, number, number][] = []
  const colPos: [number, number, number][] = []
  const corbelPos: [number, number, number][] = []
  const winPos: [number, number, number][] = []

  for (let z = -hl; z <= hl; z += BAY) {
    for (const sx of [-1, 1]) {
      const x = sx * (hw - 0.35)
      pierPos.push([x, 1.0, z])
      colPos.push([x, H / 2, z])
      corbelPos.push([sx * (hw - 0.85), RAIL_Y - 0.55, z])
      if (z < hl) winPos.push([sx * (hw - 0.12), 7.8, z + BAY / 2])
    }
  }
  for (let x = -hw + 15; x <= hw - 15; x += 15) {
    if (Math.abs(x) < 8) continue
    for (const sz of [-1, 1]) {
      pierPos.push([x, 1.0, sz * (hl - 0.35)])
      colPos.push([x, H / 2, sz * (hl - 0.35)])
    }
  }

  addInstancedBoxes(group, [0.95, 2.0, 0.95], concMat, pierPos)
  addInstancedBoxes(group, [0.55, H, 0.55], colMat, colPos)
  addInstancedBoxes(group, [0.9, 0.65, 0.5], corbelMat, corbelPos)
  addInstancedBoxes(group, [0.08, 3.6, 2.4], winMat, winPos)

  // 4. 预留龙门吊 / 行车双侧纵向吊车梁 + 钢轨 (沿 140m 全长贯通，高度 10.5m)
  const girderMat = new THREE.MeshStandardMaterial({ color: 0x1e3a5f, roughness: 0.45, metalness: 0.7 })
  const railMat = new THREE.MeshStandardMaterial({ color: 0xf97316, roughness: 0.32, metalness: 0.82 })
  for (const sx of [-1, 1]) {
    const rx = sx * (hw - 0.95)
    const girder = new THREE.Mesh(new THREE.BoxGeometry(0.65, 0.85, L - 1), girderMat)
    girder.position.set(rx, RAIL_Y - 0.45, 0); group.add(girder)
    const rail = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.22, L - 1), railMat)
    rail.position.set(rx, RAIL_Y + 0.08, 0); group.add(rail)
  }

  return { widthM: W, lengthM: L, heightM: H, railHeightM: RAIL_Y, columnCount: colPos.length }
}
