<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { buildFactoryPerimeter, type FactoryStats } from '../utils/factoryPerimeter'

const labTab = ref<'factory' | 'bench'>('factory')
const count = ref(1000)
const mode = ref<'naive' | 'instanced'>('instanced')
const fps = ref(0); const drawCalls = ref(0); const triangles = ref(0); const geoCount = ref(0)
const stats = ref<FactoryStats | null>(null)
const boxEl = ref<HTMLElement | null>(null)

let scene: THREE.Scene, camera: THREE.PerspectiveCamera, renderer: THREE.WebGLRenderer, ctrl: OrbitControls
let group: THREE.Group, rafId = 0, frames = 0, lastT = performance.now()

function clearGroup() {
  if (!group) return
  group.traverse((o: any) => { o.geometry?.dispose?.(); o.material?.dispose?.() })
  group.clear()
}

function setCam(view: 'bird' | 'aisle' | 'rail') {
  if (!camera || !ctrl) return
  if (view === 'bird') { camera.position.set(-78, 56, 98); ctrl.target.set(0, 4, 0) }
  else if (view === 'aisle') { camera.position.set(0, 4.5, 64); ctrl.target.set(0, 6, -40) }
  else { camera.position.set(-34, 13.5, 22); ctrl.target.set(-44, 10.5, -10) }
  ctrl.update()
}

function rebuild() {
  if (!group) return
  clearGroup()
  if (labTab.value === 'factory') {
    scene.background = new THREE.Color(0x0f172a)
    stats.value = buildFactoryPerimeter(group)
    setCam('aisle')
    return
  }
  stats.value = null
  const n = count.value, cols = Math.ceil(Math.cbrt(n))
  const geo = new THREE.BoxGeometry(0.42, 0.32, 0.42)
  const mat = new THREE.MeshStandardMaterial({ color: 0xc28e5c, roughness: 0.75, metalness: 0.05 })
  if (mode.value === 'instanced') {
    const inst = new THREE.InstancedMesh(geo, mat, n), d = new THREE.Object3D()
    for (let i = 0; i < n; i++) {
      const ix = i % cols, iy = Math.floor(i / cols) % cols, iz = Math.floor(i / (cols * cols))
      d.position.set((ix - cols / 2) * 0.7, iy * 0.55 + 0.2, (iz - cols / 2) * 0.7); d.updateMatrix(); inst.setMatrixAt(i, d.matrix)
    }
    group.add(inst)
  } else {
    for (let i = 0; i < n; i++) {
      const ix = i % cols, iy = Math.floor(i / cols) % cols, iz = Math.floor(i / (cols * cols))
      const m = new THREE.Mesh(geo.clone(), mat.clone())
      m.position.set((ix - cols / 2) * 0.7, iy * 0.55 + 0.2, (iz - cols / 2) * 0.7); group.add(m)
    }
    geo.dispose(); mat.dispose()
  }
  camera.position.set(8, 7, 10); ctrl.target.set(0, 1, 0); ctrl.update()
}

watch([labTab, count, mode], rebuild)

onMounted(() => {
  const el = boxEl.value!
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x0f172a)
  camera = new THREE.PerspectiveCamera(50, (el.clientWidth || 720) / 460, 0.5, 500)
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(el.clientWidth || 720, 460); el.appendChild(renderer.domElement)
  ctrl = new OrbitControls(camera, renderer.domElement); ctrl.enableDamping = true
  scene.add(new THREE.HemisphereLight(0xe0f2fe, 0x334155, 0.9))
  const dl = new THREE.DirectionalLight(0xfffbeb, 1.8); dl.position.set(45, 70, 55); scene.add(dl)
  group = new THREE.Group(); scene.add(group); rebuild()

  const tick = () => {
    rafId = requestAnimationFrame(tick)
    ctrl.update(); renderer.render(scene, camera)
    frames++
    const now = performance.now()
    if (now - lastT >= 400) {
      fps.value = Math.round((frames * 1000) / (now - lastT))
      drawCalls.value = renderer.info.render.calls
      triangles.value = renderer.info.render.triangles
      geoCount.value = renderer.info.memory.geometries
      frames = 0; lastT = now
    }
  }
  tick()
})

onBeforeUnmount(() => { cancelAnimationFrame(rafId); clearGroup(); renderer?.dispose() })
</script>

<template>
  <section class="lab-3d">
    <header class="head">
      <div>
        <h2>3D 渲染提效实验室 · 90m×140m 钢混厂区构建</h2>
        <p class="sub">采用 InstancedMesh 柱网合批构建 90m×140m×14m 钢混厂房四周与 10.5m 预留龙门/行车轨道，DrawCall 稳定在极低水平。</p>
      </div>
      <div class="controls">
        <button class="btn" :class="{ 'btn-primary': labTab === 'factory' }" @click="labTab = 'factory'">🏭 90×140m 厂区 (Step 1)</button>
        <button class="btn" :class="{ 'btn-primary': labTab === 'bench' }" @click="labTab = 'bench'">⚡ 千级货物合批压测</button>
      </div>
    </header>

    <div v-if="labTab === 'factory'" class="bar">
      <span v-if="stats" class="spec">厂区规格：<b>{{ stats.widthM }}m × {{ stats.lengthM }}m × {{ stats.heightM }}m</b> · 预留轨道标高：<b>{{ stats.railHeightM }}m</b> · 钢混立柱：<b>{{ stats.columnCount }} 根</b>（合批渲染）</span>
      <div class="controls">
        <button class="btn" @click="setCam('aisle')">通道内视角</button>
        <button class="btn" @click="setCam('bird')">厂区全景俯瞰</button>
        <button class="btn" @click="setCam('rail')">预留轨道特写</button>
      </div>
    </div>
    <div v-else class="bar">
      <select v-model.number="count" class="sel"><option :value="200">200 个</option><option :value="1000">1,000 个</option><option :value="3000">3,000 个</option><option :value="6000">6,000 个</option></select>
      <button class="btn" :class="{ 'btn-primary': mode === 'naive' }" @click="mode = 'naive'">普通 Mesh</button>
      <button class="btn" :class="{ 'btn-primary': mode === 'instanced' }" @click="mode = 'instanced'">InstancedMesh 合批</button>
    </div>

    <div class="hud">
      <div class="kpi"><span>实时帧率</span><strong :class="fps < 35 ? 'bad' : 'ok'">{{ fps }} FPS</strong></div>
      <div class="kpi"><span>DrawCalls</span><strong :class="drawCalls > 100 ? 'bad' : 'ok'">{{ drawCalls }}</strong></div>
      <div class="kpi"><span>三角形面数</span><strong>{{ triangles.toLocaleString() }}</strong></div>
      <div class="kpi"><span>显存 Geometry 数</span><strong>{{ geoCount }}</strong></div>
    </div>

    <div ref="boxEl" class="canvas-box"></div>
  </section>
</template>

<style scoped>
.lab-3d { display: flex; flex-direction: column; gap: 10px; }
.head, .bar { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; }
.head h2 { margin: 0 0 4px; font-size: 18px; }
.sub, .spec { margin: 0; font-size: 13px; color: var(--muted); }
.bar { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; }
.controls { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.sel { padding: 6px 10px; border: 1px solid var(--border); border-radius: 8px; font-size: 13px; background: #fff; }
.hud { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.kpi { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--muted); }
.kpi strong { font-size: 18px; color: var(--text); }
.kpi strong.ok { color: #059669; }
.kpi strong.bad { color: #dc2626; }
.canvas-box { width: 100%; height: 460px; border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }
</style>
