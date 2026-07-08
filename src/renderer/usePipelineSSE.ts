import { useState, useEffect, useRef, useCallback } from 'react'
import { BASE } from './api'

export interface StepState {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  progress: number
  error: string
  result: string
  started_at?: string
  completed_at?: string
}

export interface PipelineStatus {
  pipeline_status: string
  pipeline_step: string
  pipeline_error: string
  pipeline_progress: number
  pipeline_message: string
  steps: Record<string, StepState>
  is_running: boolean
}

export type PipelineEvent =
  | { type: 'pipeline_started' }
  | { type: 'pipeline_completed' }
  | { type: 'pipeline_failed'; error: string }
  | { type: 'pipeline_paused' }
  | { type: 'pipeline_resumed' }
  | { type: 'pipeline_cancelled' }
  | { type: 'step_start'; step: string }
  | { type: 'step_complete'; step: string; result: object }
  | { type: 'step_failed'; step: string; error: string }
  | { type: 'emit_progress'; step: string; progress: number; message?: string }
  | { type: 'step_skipped'; step: string }
  | { type: 'portrait_image_status'; identifier: string; view: string; status: string; image_url?: string }
  | { type: 'storyboard_scene_ready'; scene_idx: number; scene: { idx: number; title: string; content: string; shots: Array<any> } }
  | { type: 'shot_frame_ready'; scene_idx: number; shot_idx: number; frame_type: string; image_url: string }
  | { type: 'shot_video_ready'; scene_idx: number; shot_idx: number; video_url: string; video_preview_url?: string }
  | { type: 'scene_composite_ready'; scene_idx: number; composited_video: string; composited_preview: string }
  | { type: 'final_video_ready'; final_video_url: string; final_preview_url?: string }
  | { type: 'task_status'; task_id: string; status: string; message: string; model: string; attempt?: number; max_retries?: number; result?: any }

interface UsePipelineSSEReturn {
  status: PipelineStatus | null
  connected: boolean
  start: () => Promise<void>
  startFromStep: (step: string) => Promise<void>
  pause: () => Promise<void>
  resume: () => Promise<void>
  cancel: () => Promise<void>
  regenerateStep: (step: string) => Promise<void>
  fetchStatus: () => Promise<void>
}

const BASE_URL = BASE

export function usePipelineSSE(
  projectId: number | null,
  onEvent?: (event: PipelineEvent) => void,
): UsePipelineSSEReturn {
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [connected, setConnected] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const projectIdRef = useRef(projectId)
  projectIdRef.current = projectId

  const fetchStatus = useCallback(async () => {
    const pid = projectIdRef.current
    if (!pid) return
    try {
      console.log('[usePipelineSSE] fetchStatus ->', `${BASE_URL}/api/projects/${pid}/pipeline/status`)
      const res = await fetch(`${BASE_URL}/api/projects/${pid}/pipeline/status`)
      if (res.ok) {
        const data = await res.json()
        console.log('[usePipelineSSE] fetchStatus <=', data)
        // Backend response does NOT include `steps` — preserve optimistic state
        setStatus(prev => prev ? { ...prev, ...data, steps: prev.steps } : data)
      } else {
        console.warn('[usePipelineSSE] fetchStatus http=', res.status)
      }
    } catch (err) {
      console.warn('[usePipelineSSE] fetchStatus failed', err)
    }
  }, [])

  // Connect SSE
  useEffect(() => {
    if (!projectId) {
      setConnected(false)
      eventSourceRef.current?.close()
      eventSourceRef.current = null
      return
    }

    function connect() {
      eventSourceRef.current?.close()
      const es = new EventSource(`${BASE_URL}/api/projects/${projectId}/pipeline/events`)
      eventSourceRef.current = es
      setConnected(true)

      es.onmessage = (e) => {
        try {
          const event: PipelineEvent = JSON.parse(e.data)
          console.log('[usePipelineSSE] event:', event)
          handleEvent(event)
        } catch (err) {
          console.warn('[usePipelineSSE] failed to parse event', e.data, err)
        }
      }

      es.onerror = (err) => {
        console.warn('[usePipelineSSE] SSE connection error, will retry in 3s', err)
        setConnected(false)
        es.close()
        reconnectTimerRef.current = setTimeout(() => {
          console.log('[usePipelineSSE] reconnecting...')
          connect()
        }, 3000)
      }
    }

    connect()
    fetchStatus()

    return () => {
      eventSourceRef.current?.close()
      clearTimeout(reconnectTimerRef.current)
    }
  }, [projectId])

  function handleEvent(event: PipelineEvent) {
    switch (event.type) {
      case 'pipeline_started':
        setStatus(prev => prev ? { ...prev, pipeline_status: 'running' } : prev)
        fetchStatus()
        break
      case 'pipeline_paused':
        setStatus(prev => prev ? { ...prev, pipeline_status: 'paused' } : prev)
        break
      case 'pipeline_resumed':
        setStatus(prev => prev ? { ...prev, pipeline_status: 'running' } : prev)
        break
      case 'pipeline_cancelled':
        setStatus(prev => prev ? { ...prev, pipeline_status: 'cancelled' } : prev)
        fetchStatus()
        break
      case 'step_start':
      case 'step_complete':
      case 'step_failed':
        console.log('[usePipelineSSE] step event:', event.type, (event as any).step, (event as any).result ?? (event as any).error)
        // Optimistic local update so the UI responds immediately
        setStatus(prev => {
          if (!prev) return prev
          const ev = event as any
          const step = ev.step
          const terminal = event.type === 'step_complete' ? 'completed'
            : event.type === 'step_failed' ? 'failed'
            : 'running'
          const prevStepState = prev.steps?.[step]
          return {
            ...prev,
            pipeline_step: step,
            steps: {
              ...prev.steps,
              [step]: {
                ...prevStepState,
                status: terminal,
                ...(terminal === 'completed' ? { progress: 1 } : {}),
              },
            },
          }
        })
        // Refresh full authoritative state from server in background
        fetchStatus()
        break
      case 'step_skipped':
        setStatus(prev => {
          if (!prev) return prev
          const step = event.step
          return {
            ...prev,
            steps: {
              ...prev.steps,
              [step]: {
                ...(prev.steps?.[step] as any),
                status: 'skipped',
              },
            },
          }
        })
        break
      case 'emit_progress':
        setStatus(prev => {
          if (!prev) return prev
          const step = event.step
          const prevStepState = prev.steps?.[step]
          return {
            ...prev,
            pipeline_step: step,
            pipeline_progress: event.progress,
            pipeline_message: event.message || '',
            steps: {
              ...prev.steps,
              [step]: {
                ...prevStepState,
                progress: event.progress,
                status: 'running',
              },
            },
          }
        })
        break
      case 'pipeline_failed':
        console.error('[usePipelineSSE] pipeline_failed:', event.error)
        setStatus(prev => prev ? { ...prev, pipeline_status: 'failed', pipeline_error: event.error } : prev)
        break
      case 'pipeline_completed':
        setStatus(prev => prev ? { ...prev, pipeline_status: 'completed', pipeline_progress: 1 } : prev)
        break
      case 'task_status':
        onEvent?.(event)
        break
      case 'portrait_image_status':
      case 'storyboard_scene_ready':
      case 'shot_frame_ready':
      case 'shot_video_ready':
      case 'scene_composite_ready':
      case 'final_video_ready':
        onEvent?.(event)
        break
    }
  }

  const post = useCallback(async (path: string, body?: object) => {
    const pid = projectIdRef.current
    if (!pid) return
    const res = await fetch(`${BASE_URL}/api/projects/${pid}/pipeline/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Request failed' }))
      throw new Error(err.error || err.detail || `HTTP ${res.status}`)
    }
    return res.json()
  }, [])

  const put = useCallback(async (path: string, body?: object) => {
    const pid = projectIdRef.current
    if (!pid) return
    const res = await fetch(`${BASE_URL}/api/projects/${pid}/pipeline/${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  }, [])

  function apiKeys() {
    const k = (window as any).__pipelineApiKeys || {}
    return {
      chat_api_key: k.chatApiKey || '',
      chat_base_url: k.chatBaseUrl || '',
      image_api_key: k.imageApiKey || '',
      image_base_url: k.imageBaseUrl || '',
      video_api_key: k.videoApiKey || '',
      video_base_url: k.videoBaseUrl || '',
      chat_rate_limit_min: parseInt(k.chatRateLimitMin, 10) || 50,
      chat_rate_limit_day: parseInt(k.chatRateLimitDay, 10) || 2000,
      image_rate_limit_min: parseInt(k.imageRateLimitMin, 10) || 10,
      image_rate_limit_day: parseInt(k.imageRateLimitDay, 10) || 500,
      video_rate_limit_min: parseInt(k.videoRateLimitMin, 10) || 50,
      video_rate_limit_day: parseInt(k.videoRateLimitDay, 10) || 1000,
    }
  }

  const start = useCallback(async () => {
    await post('start', apiKeys())
    fetchStatus()
  }, [post, fetchStatus])

  const startFromStep = useCallback(async (step: string) => {
    await post('start', {
      start_step: step,
      ...apiKeys(),
    })
    fetchStatus()
  }, [post, fetchStatus])

  const pause = useCallback(async () => { await post('pause'); fetchStatus() }, [post, fetchStatus])
  const resume = useCallback(async () => { await post('resume'); fetchStatus() }, [post, fetchStatus])
  const cancel = useCallback(async () => { await post('cancel'); fetchStatus() }, [post, fetchStatus])

  const regenerateStep = useCallback(async (step: string) => {
    await post('regenerate-step', { step })
    fetchStatus()
  }, [post, fetchStatus])

  return { status, connected, start, startFromStep, pause, resume, cancel, regenerateStep, fetchStatus }
}
