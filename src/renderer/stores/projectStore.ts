import { create } from 'zustand'
import type { Node, Edge, Viewport } from '@xyflow/react'
import { BASE, getProject, updateProject } from '../api'
import type { CharacterData } from '../CharacterCard'
import type { SceneData, ShotData } from '../ShootingScriptCard'
import type { PipelineStatus, PipelineEvent } from '../usePipelineSSE'

interface SSERetryState {
  retryCount: number
  maxRetries: number
  baseDelay: number
  maxDelay: number
}

interface ProjectState {
  projectId: number | null
  projectName: string
  loading: boolean

  idea: string
  style: string
  output: string | null
  characters: CharacterData[]
  scenes: SceneData[]
  stepStatuses: Record<string, number> | null
  finalVideo: string
  finalPreview: string

  canvasNodes: Node[]
  canvasEdges: Edge[]
  canvasViewport: Viewport | null
  canvasLayoutLoaded: boolean

  pipelineStatus: PipelineStatus | null
  sseConnected: boolean
  sseRetry: SSERetryState
  sseRetryTimer: ReturnType<typeof setTimeout> | null

  loadProject: (id: number) => Promise<void>
  setIdea: (idea: string) => void
  setStyle: (style: string) => void
  setOutput: (text: string | null) => void
  setCharacters: (chars: CharacterData[]) => void
  updateCharacter: (idx: number, data: Partial<CharacterData>) => void
  setScenes: (scenes: SceneData[]) => void
  updateScene: (idx: number, data: Partial<SceneData>) => void
  updateShot: (sceneIdx: number, shotIdx: number, data: Partial<ShotData>) => void
  setStepStatuses: (sts: Record<string, number>) => void
  setPipelineStatus: (st: PipelineStatus) => void
  setFinalVideo: (url: string) => void
  setFinalPreview: (url: string) => void

  setCanvasLayout: (nodes: Node[], edges: Edge[], viewport: Viewport | null) => void
  loadCanvasLayout: () => Promise<void>
  saveCanvasLayout: () => Promise<void>

  selectedNodeId: string | null

  setSelectedNodeId: (id: string | null) => void

  saveToBackend: () => Promise<void>

  connectSSE: (id: number) => void
  disconnectSSE: () => void
}

let _eventSource: EventSource | null = null
let _sseTimer: ReturnType<typeof setTimeout> | null = null

export const useProjectStore = create<ProjectState>((set, get) => ({
  projectId: null,
  projectName: '',
  loading: false,

  idea: '',
  style: 'realistic',
  output: null,
  characters: [],
  scenes: [],
  stepStatuses: null,
  finalVideo: '',
  finalPreview: '',

  canvasNodes: [],
  canvasEdges: [],
  canvasViewport: null,
  canvasLayoutLoaded: false,

  pipelineStatus: null,
  sseConnected: false,
  sseRetry: { retryCount: 0, maxRetries: 10, baseDelay: 1000, maxDelay: 30000 },
  sseRetryTimer: null,

  selectedNodeId: null,

  setSelectedNodeId: (id: string | null) => set({ selectedNodeId: id }),

  loadProject: async (id: number) => {
    set({ loading: true })
    try {
      const p = await getProject(id)
      set({
        projectId: id,
        projectName: p.name || '',
        idea: p.idea || '',
        style: p.style || 'realistic',
        output: p.story || null,
        stepStatuses: p.step_statuses || null,
        finalVideo: p.final_video || '',
        finalPreview: p.final_preview || '',
        loading: false,
      })
    } catch {
      set({ loading: false })
    }
  },

  setIdea: (idea) => set({ idea }),
  setStyle: (style) => set({ style }),
  setOutput: (output) => set({ output }),
  setCharacters: (characters) => set({ characters }),
  setScenes: (scenes) => set({ scenes }),
  setStepStatuses: (stepStatuses) => set({ stepStatuses }),
  setPipelineStatus: (pipelineStatus) => set({ pipelineStatus }),
  setFinalVideo: (finalVideo) => set({ finalVideo }),
  setFinalPreview: (finalPreview) => set({ finalPreview }),

  updateCharacter: (idx, data) => {
    set(state => {
      const next = state.characters.map((c, i) => i === idx ? { ...c, ...data } as CharacterData : c)
      return { characters: next }
    })
  },

  updateScene: (idx, data) => {
    set(state => {
      const next = state.scenes.map((s, i) => i === idx ? { ...s, ...data } as SceneData : s)
      return { scenes: next }
    })
  },

  updateShot: (sceneIdx, shotIdx, data) => {
    set(state => {
      const scenes = state.scenes.map((s, i) => {
        if (i !== sceneIdx) return s
        const shots = s.shots.map((sh, j) => j === shotIdx ? { ...sh, ...data } as ShotData : sh)
        return { ...s, shots }
      })
      return { scenes }
    })
  },

  setCanvasLayout: (canvasNodes, canvasEdges, canvasViewport) => {
    set({ canvasNodes, canvasEdges, canvasViewport })
  },

  loadCanvasLayout: async () => {
    const { projectId } = get()
    if (!projectId) return
    try {
      const res = await fetch(`${BASE}/api/projects/${projectId}/canvas-layout`)
      if (res.ok) {
        const data = await res.json()
        set({
          canvasNodes: data.nodes || [],
          canvasEdges: data.edges || [],
          canvasViewport: data.viewport || null,
          canvasLayoutLoaded: true,
        })
      }
    } catch { /* ignore */ }
  },

  saveCanvasLayout: async () => {
    const { projectId, canvasNodes, canvasEdges, canvasViewport } = get()
    if (!projectId) return
    try {
      await fetch(`${BASE}/api/projects/${projectId}/canvas-layout`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes: canvasNodes, edges: canvasEdges, viewport: canvasViewport }),
      })
    } catch { /* ignore */ }
  },

  saveToBackend: async () => {
    const { projectId, idea, style, output, characters, scenes, finalVideo, finalPreview, stepStatuses } = get()
    if (!projectId) return
    const stage = stepStatuses ? 'storyboard' : (characters.length ? 'characters' : (output ? 'story' : 'new'))
    try {
      await updateProject(projectId, {
        idea,
        style,
        story: output,
        stage,
        characters: characters.map(c => ({
          name: c.name,
          staticFeatures: c.staticFeatures,
          dynamicFeatures: c.dynamicFeatures,
          source: 'script',
          portraits: c.portraits || {},
          sourceUrl: c.sourceUrl || '',
        })),
        scenes: scenes.map(s => ({
          title: s.title,
          content: s.content,
          slugline: '',
          environmentDesc: '',
          script: '',
          compositedVideo: s.compositedVideo || '',
          compositedPreview: s.compositedPreview || '',
          shots: s.shots.map(sh => ({
            title: sh.title,
            visualDescription: sh.visualDescription,
            voiceDescription: sh.voiceDescription,
            motionDescription: sh.motionDescription || '',
            variationType: sh.variationType || 'small',
            firstFrame: sh.firstFrame,
            lastFrame: sh.lastFrame,
            video: sh.video,
            videoPreview: sh.videoPreview || '',
          })),
        })),
      } as any)
    } catch { /* ignore */ }
  },

  connectSSE: (id: number) => {
    const { sseRetry } = get()
    _eventSource?.close()
    if (_sseTimer) { clearTimeout(_sseTimer); _sseTimer = null }

    const es = new EventSource(`${BASE}/api/projects/${id}/pipeline/events`)
    _eventSource = es
    set({ sseConnected: true })

    const handleEvent = (event: PipelineEvent) => {
      const state = get()
      const { fetchStatus } = state as any
      switch (event.type) {
        case 'pipeline_started':
          set((s) => ({ pipelineStatus: s.pipelineStatus ? { ...s.pipelineStatus, pipeline_status: 'running' } : s.pipelineStatus }))
          break
        case 'pipeline_completed':
          set((s) => s.pipelineStatus ? { pipelineStatus: { ...s.pipelineStatus, pipeline_status: 'completed', pipeline_progress: 1 } } : s)
          break
        case 'pipeline_failed':
          set((s) => s.pipelineStatus ? { pipelineStatus: { ...s.pipelineStatus, pipeline_status: 'failed', pipeline_error: event.error } } : s)
          break
        case 'pipeline_paused':
          set((s) => s.pipelineStatus ? { pipelineStatus: { ...s.pipelineStatus, pipeline_status: 'paused' } } : s)
          break
        case 'pipeline_resumed':
          set((s) => s.pipelineStatus ? { pipelineStatus: { ...s.pipelineStatus, pipeline_status: 'running' } } : s)
          break
        case 'pipeline_cancelled':
          set((s) => s.pipelineStatus ? { pipelineStatus: { ...s.pipelineStatus, pipeline_status: 'cancelled' } } : s)
          break
        case 'step_start':
        case 'step_complete':
        case 'step_failed':
          set((s) => {
            if (!s.pipelineStatus) return s
            const step = (event as any).step as string
            const terminal = event.type === 'step_complete' ? 'completed'
              : event.type === 'step_failed' ? 'failed' : 'running'
            const prevStepState = s.pipelineStatus.steps?.[step]
            return {
              pipelineStatus: {
                ...s.pipelineStatus,
                pipeline_step: step,
                steps: {
                  ...s.pipelineStatus.steps,
                  [step]: { ...prevStepState, status: terminal, ...(terminal === 'completed' ? { progress: 1 } : {}) },
                },
              },
            }
          })
          break
        case 'step_skipped':
          set((s) => {
            if (!s.pipelineStatus) return s
            return {
              pipelineStatus: {
                ...s.pipelineStatus,
                steps: {
                  ...s.pipelineStatus.steps,
                  [event.step]: { ...(s.pipelineStatus.steps?.[event.step] || {}), status: 'skipped' },
                },
              },
            }
          })
          break
        case 'emit_progress':
          set((s) => {
            if (!s.pipelineStatus) return s
            return {
              pipelineStatus: {
                ...s.pipelineStatus,
                pipeline_step: event.step,
                pipeline_progress: event.progress,
                pipeline_message: event.message || '',
                steps: {
                  ...s.pipelineStatus.steps,
                  [event.step]: {
                    ...(s.pipelineStatus.steps?.[event.step] || {}),
                    progress: event.progress,
                    status: 'running',
                  },
                },
              },
            }
          })
          break
        case 'project_data_changed':
        case 'task_status':
          break
      }
    }

    es.onmessage = (e) => {
      try {
        const event: PipelineEvent = JSON.parse(e.data)
        handleEvent(event)
      } catch { /* ignore parse errors */ }
    }

    es.onerror = () => {
      set({ sseConnected: false })
      es.close()
      _eventSource = null

      const { sseRetry } = get()
      if (sseRetry.retryCount >= sseRetry.maxRetries) return

      const delay = Math.min(sseRetry.baseDelay * Math.pow(2, sseRetry.retryCount), sseRetry.maxDelay)
      const jitter = delay * (0.5 + Math.random() * 0.5)

      set((s) => ({ sseRetry: { ...s.sseRetry, retryCount: s.sseRetry.retryCount + 1 } }))

      _sseTimer = setTimeout(() => {
        const pid = get().projectId
        if (pid) {
          set((s) => ({ sseRetry: { ...s.sseRetry, retryCount: 0 } }))
          get().connectSSE(pid)
          fetch(`${BASE}/api/projects/${pid}/pipeline/status`)
            .then(r => r.json())
            .then(status => set({ pipelineStatus: status }))
            .catch(() => {})
        }
      }, jitter)
    }
  },

  disconnectSSE: () => {
    _eventSource?.close()
    _eventSource = null
    if (_sseTimer) { clearTimeout(_sseTimer); _sseTimer = null }
    set({ sseConnected: false, sseRetry: { ...get().sseRetry, retryCount: 0 } })
  },
}))

declare global {
  interface Window {
    __pipelineApiKeys?: Record<string, string>
  }
}
