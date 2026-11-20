import * as THREE from 'three'

function makeWoodTexture(): { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } {
  const c = document.createElement('canvas'); c.width = 512; c.height = 512
  const ctx = c.getContext('2d')!; ctx.fillStyle = '#c48f5a'; ctx.fillRect(0, 0, 512, 512)
  for (let i = 0; i < 180; i++) {
    const y = (i * 512) / 180
    ctx.strokeStyle = i % 3 === 0 ? 'rgba(92,52,24,0.16)' : 'rgba(235,190,135,0.12)'; ctx.lineWidth = 1 + (i % 3)
    ctx.beginPath(); ctx.moveTo(0, y); ctx.bezierCurveTo(170, y + Math.sin(i) * 4, 340, y - Math.cos(i) * 4, 512, y); ctx.stroke()
  }
  const map = new THREE.CanvasTexture(c); map.colorSpace = THREE.SRGBColorSpace; map.wrapS = map.wrapT = THREE.RepeatWrapping
  const bump = new THREE.CanvasTexture(c); bump.wrapS = bump.wrapT = THREE.RepeatWrapping
  return { map, bump }
}

function makeBrushedMetalBump(): THREE.CanvasTexture {
  const c = document.createElement('canvas'); c.width = 256; c.height = 256
  const ctx = c.getContext('2d')!; ctx.fillStyle = '#808080'; ctx.fillRect(0, 0, 256, 256)
  for (let i = 0; i < 240; i++) {
    const y = Math.random() * 256, v = 105 + Math.floor(Math.random() * 50)
    ctx.strokeStyle = `rgb(${v},${v},${v})`; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(256, y); ctx.stroke()
  }
  const tex = new THREE.CanvasTexture(c); tex.wrapS = tex.wrapT = THREE.RepeatWrapping; return tex
}

function makeSlottedGalvanized(rx: number, ry: number): { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } {
  const c = document.createElement('canvas'); c.width = 128; c.height = 128
  const ctx = c.getContext('2d')!; ctx.fillStyle = '#b8c0c8'; ctx.fillRect(0, 0, 128, 128)
  for (let i = 0; i < 90; i++) {
    const shade = 155 + Math.floor(Math.random() * 55)
    ctx.fillStyle = `rgb(${shade},${shade + 3},${shade + 6})`
    ctx.fillRect(Math.random() * 128, Math.random() * 128, 10 + Math.random() * 18, 6 + Math.random() * 14)
  }
  ctx.fillStyle = '#181c24'
  for (const x of [24, 80]) { for (const y of [16, 80]) ctx.fillRect(x, y, 24, 34) }
  const map = new THREE.CanvasTexture(c); map.colorSpace = THREE.SRGBColorSpace
  map.wrapS = map.wrapT = THREE.RepeatWrapping; map.repeat.set(rx, ry)
  const bump = new THREE.CanvasTexture(c); bump.wrapS = bump.wrapT = THREE.RepeatWrapping; bump.repeat.set(rx, ry)
  return { map, bump }
}

function makeCardboardTexture(): THREE.CanvasTexture {
  const c = document.createElement('canvas'); c.width = 256; c.height = 256
  const ctx = c.getContext('2d')!; ctx.fillStyle = '#b58d63'; ctx.fillRect(0, 0, 256, 256)
  for (let i = 0; i < 60; i++) {
    ctx.fillStyle = i % 2 ? 'rgba(90,60,30,0.05)' : 'rgba(220,190,150,0.05)'
    ctx.fillRect(0, Math.random() * 256, 256, 3)
  }
  ctx.fillStyle = 'rgba(235, 224, 200, 0.72)'; ctx.fillRect(108, 0, 40, 256)
  ctx.fillStyle = '#f8fafc'; ctx.fillRect(22, 168, 66, 46)
  ctx.fillStyle = '#1e293b'
  for (let x = 28; x < 82; x += 5) ctx.fillRect(x, 176, x % 2 ? 2 : 3, 24)
  ctx.fillRect(28, 204, 52, 4)
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; return tex
}

let cachedWood: { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } | null = null
let cachedMetalBump: THREE.CanvasTexture | null = null
let cachedBoxTex: THREE.Texture | null = null
let cachedBoxNorm: THREE.Texture | null = null

export function getWoodMaterial(highlight: boolean): THREE.MeshPhysicalMaterial {
  cachedWood ||= makeWoodTexture()
  return new THREE.MeshPhysicalMaterial({
    color: highlight ? 0xfbbf24 : 0xffffff, map: highlight ? null : cachedWood.map, bumpMap: cachedWood.bump,
    bumpScale: 0.004, roughness: 0.48, metalness: 0.04, clearcoat: 0.28, clearcoatRoughness: 0.32,
  })
}

export function getBrushedSteelMaterial(color: number, metalness = 0.85, roughness = 0.28): THREE.MeshPhysicalMaterial {
  cachedMetalBump ||= makeBrushedMetalBump()
  return new THREE.MeshPhysicalMaterial({
    color, bumpMap: cachedMetalBump, bumpScale: 0.002, metalness, roughness, clearcoat: 0.12, envMapIntensity: 1.2,
  })
}

export function getGalvanizedSlottedMaterial(rx: number, ry: number, highlight: boolean): THREE.MeshStandardMaterial {
  const { map, bump } = makeSlottedGalvanized(rx, ry)
  return new THREE.MeshStandardMaterial({
    color: highlight ? 0xfde68a : 0xd8dee6, map, bumpMap: bump, bumpScale: 0.007, metalness: 0.56, roughness: 0.48, envMapIntensity: 0.45,
  })
}

export function getMatteDeckMaterial(highlight: boolean): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color: highlight ? 0xfbbf24 : 0x242830, metalness: 0.22, roughness: 0.76, envMapIntensity: 0.3,
  })
}

export function getCardboardBoxMaterial(): THREE.MeshStandardMaterial {
  if (!cachedBoxTex) {
    const ld = new THREE.TextureLoader()
    cachedBoxTex = ld.load('/textures/cardboard_box.jpg'); cachedBoxTex.colorSpace = THREE.SRGBColorSpace
    cachedBoxNorm = ld.load('/textures/cardboard_normal.jpg')
  }
  return new THREE.MeshStandardMaterial({ map: cachedBoxTex, normalMap: cachedBoxNorm, normalScale: new THREE.Vector2(0.22, 0.22), roughness: 0.86, metalness: 0.02, envMapIntensity: 0.25 })
}
