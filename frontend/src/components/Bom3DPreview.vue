<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { BomRollupResponse } from '../api/bomTypes'
import { buildIndustrialCabinet } from '../utils/cabinetMesh'
import { printBomQuoteWith3D } from '../utils/bomPrintQuote'
import BomRemnantSvg from './BomRemnantSvg.vue'

const props = defineProps<{ params: { h: number; w: number; d: number; t: number }; rollup?: BomRollupResponse | null; highlightSku?: string; marginPct: number; taxPct: number }>()
const emit = defineEmits<{ editSku: [sku: string] }>()
const boxEl = ref<HTMLElement | null>(null)
const exploded = ref(false)
const box3Alert = ref('')
const pickedInfo = ref<{ sku: string; name: string; qty: number; subtotal: number } | null>(null)
const widthAlert = computed(() => '')
const busbarDistMm = computed(() => Math.round(Math.hypot(props.params.w * 0.9, -props.params.h * 0.6, props.params.d * 0.8)))

let scene: THREE.Scene, camera: THREE.PerspectiveCamera, renderer: THREE.WebGLRenderer, ctrl: OrbitControls, group: THREE.Group, ro: ResizeObserver | null = null, rafId = 0
const raycaster = new THREE.Raycaster()

function disposeGroup() {
  if (!group) return
  group.traverse((obj: any) => { obj.geometry?.dispose?.(); if (Array.isArray(obj.material)) obj.material.forEach((m: any) => m.dispose?.()); else obj.material?.dispose?.() })
  group.clear()
}

function rebuildScene() {
  if (!group) return
  disposeGroup()
  box3Alert.value = buildIndustrialCabinet(group, {
    ...props.params, exploded: exploded.value, highlightSku: pickedInfo.value?.sku || props.highlightSku || '',
    collision: !!widthAlert.value, root: props.rollup?.root,
  })
}

function setView(preset: 'iso' | 'front' | 'top') {
  if (!camera || !ctrl) return
  if (preset === 'iso') camera.position.set(2.3, 2.0, 3.2)
  else if (preset === 'front') camera.position.set(0, 1.1, 3.5)
  else camera.position.set(0, 4.1, 0.01)
  ctrl.target.set(0, 1.0, 0); ctrl.update()
}

function onCanvasClick(ev: MouseEvent) {
  if (!boxEl.value || !camera || !group) return
  const rect = renderer.domElement.getBoundingClientRect()
  const mouse = new THREE.Vector2(((ev.clientX - rect.left) / rect.width) * 2 - 1, -((ev.clientY - rect.top) / rect.height) * 2 + 1)
  raycaster.setFromCamera(mouse, camera)
  const hit = raycaster.intersectObjects(group.children, true).find((h) => h.object.userData?.sku)
  pickedInfo.value = hit ? (hit.object.userData as any) : null
}

function handlePrint() {
  const img = renderer?.domElement.toDataURL('image/png')
  printBomQuoteWith3D(props.rollup ?? null, props.marginPct, props.taxPct, img)
}

watch(() => [props.params.h, props.params.w, props.params.d, props.params.t, props.rollup, props.highlightSku, exploded.value, pickedInfo.value?.sku], rebuildScene)

onMounted(() => {
  const el = boxEl.value!
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x0f172a)
  camera = new THREE.PerspectiveCamera(45, (el.clientWidth || 640) / 420, 0.1, 100)
  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  renderer.setSize(el.clientWidth || 640, 420); el.appendChild(renderer.domElement)
  ctrl = new OrbitControls(camera, renderer.domElement); setView('iso')
  scene.add(new THREE.AmbientLight(0xffffff, 0.9))
  const dl1 = new THREE.DirectionalLight(0xffffff, 1.5); dl1.position.set(4, 6, 5); scene.add(dl1)
  scene.add(new THREE.GridHelper(4, 16, 0x334155, 0x1e293b))
  group = new THREE.Group(); scene.add(group); rebuildScene()
  ro = new ResizeObserver(() => { if (el.clientWidth) { camera.aspect = el.clientWidth / 420; camera.updateProjectionMatrix(); renderer.setSize(el.clientWidth, 420) } })
  ro.observe(el)
  const tick = () => { rafId = requestAnimationFrame(tick); renderer.render(scene, camera) }
  tick()
})

onBeforeUnmount(() => { cancelAnimationFrame(rafId); ro?.disconnect(); disposeGroup(); renderer?.dispose() })
</script>

<template>
  <div class="wrap-3d">
    <div class="view-3d">
      <div class="bar-3d">
        <span>3D 参数化装配 · 外廓: <strong>{{ params.w }}×{{ params.d }}×{{ params.h }} mm</strong></span>
        <span v-if="widthAlert || box3Alert" class="warn-pill">{{ box3Alert || widthAlert }}</span>
        <span v-if="pickedInfo" class="pick-pill">
          {{ pickedInfo.name }} ({{ pickedInfo.qty }} · ¥{{ pickedInfo.subtotal }})
          <button class="mini-edit" @click="emit('editSku', pickedInfo.sku)">编辑规则</button>
        </span>
        <div class="btns-3d">
          <button class="btn" @click="setView('iso')">等轴测</button>
          <button class="btn" @click="setView('front')">正视</button>
          <button class="btn" @click="setView('top')">俯视</button>
          <button class="btn" @click="exploded = !exploded">{{ exploded ? '合拢' : '爆炸图' }}</button>
          <button class="btn btn-primary" @click="handlePrint">打印带图报价单</button>
        </div>
      </div>
      <div ref="boxEl" class="canvas-box" @click="onCanvasClick"></div>
    </div>
    <BomRemnantSvg :root="rollup?.root" />
  </div>
</template>

<style scoped>
.wrap-3d { display: flex; flex-direction: column; gap: 10px; }
.view-3d { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
.bar-3d { display: flex; gap: 8px; align-items: center; padding: 8px 12px; background: #f8fafc; border-bottom: 1px solid var(--border); font-size: 12px; flex-wrap: wrap; }
.btns-3d { display: flex; gap: 4px; margin-left: auto; flex-wrap: wrap; }
.warn-pill { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; padding: 2px 8px; border-radius: 999px; font-size: 11px; }
.pick-pill { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; padding: 2px 8px; border-radius: 999px; font-size: 11px; display: flex; align-items: center; gap: 6px; }
.mini-edit { border: none; background: #2563eb; color: #fff; border-radius: 999px; padding: 1px 7px; font-size: 10px; cursor: pointer; }
.canvas-box { width: 100%; height: 420px; cursor: pointer; }
</style>
