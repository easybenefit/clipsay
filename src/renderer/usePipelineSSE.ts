import { useState, useEffect, useRef, useCallback } from 'react'
import { BASE } from './api'
import { useSettingsStore } from './stores/settingsStore'

export const EVENT_PROJECT_UPDATED = 'project_data_changed'

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
  | { type: 'step_data_ready'; step: string }
  | { type: typeof EVENT_PROJECT_UPDATED }
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
      const res = await fetch(`${BASE}/api/projects/${pid}/pipeline/status`)
      if (res.ok) {
        const data = await res.json()
        setStatus(prev => prev ? { ...prev, ...data, steps: prev.steps } : data)
      }
    } catch {
      // ignore
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
      const es = new EventSource(`${BASE}/api/projects/${projectId}/pipeline/events`)
      eventSourceRef.current = es
      setConnected(true)

      es.onmessage = (e) => {
        try {
          const event: PipelineEvent = JSON.parse(e.data)
          handleEvent(event)
        } catch {
          // ignore parse errors
        }
      }

      es.onerror = () => {
        setConnected(false)
        es.close()
        reconnectTimerRef.current = setTimeout(connect, 3000)
      }
    }

    connect()
    fetchStatus()

    return () => {
      eventSourceRef.current?.close()
      clearTimeout(reconnectTimerRef.current)
    }
  }, [projectId, fetchStatus])

  const handleEvent = useCallback((event: PipelineEvent) => {
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
        setStatus(prev => {
          if (!prev) return prev
          const { step } = event as { step: string }
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
                ...(prev.steps?.[step] || {}),
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
        setStatus(prev => prev ? { ...prev, pipeline_status: 'failed', pipeline_error: event.error } : prev)
        break
      case 'pipeline_completed':
        setStatus(prev => prev ? { ...prev, pipeline_status: 'completed', pipeline_progress: 1 } : prev)
        break
      case 'step_data_ready':
      case EVENT_PROJECT_UPDATED:
      case 'task_status':
        onEvent?.(event)
        break
    }
  }, [fetchStatus, onEvent])

  const post = useCallback(async (path: string, body?: object) => {
    const pid = projectIdRef.current
    if (!pid) return
    const res = await fetch(`${BASE}/api/projects/${pid}/pipeline/${path}`, {
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

  const apiKeys = useCallback(() => {
    const s = useSettingsStore.getState().settings
    return {
      chat_api_key: s.chat.apiKey || '',
      chat_base_url: s.chat.baseUrl || '',
      image_api_key: s.image.apiKey || '',
      image_base_url: s.image.baseUrl || '',
      video_api_key: s.video.apiKey || '',
      video_base_url: s.video.baseUrl || '',
      chat_rate_limit_min: parseInt(s.chat.rateLimitMin, 10) || 50,
      chat_rate_limit_day: parseInt(s.chat.rateLimitDay, 10) || 2000,
      image_rate_limit_min: parseInt(s.image.rateLimitMin, 10) || 10,
      image_rate_limit_day: parseInt(s.image.rateLimitDay, 10) || 500,
      video_rate_limit_min: parseInt(s.video.rateLimitMin, 10) || 50,
      video_rate_limit_day: parseInt(s.video.rateLimitDay, 10) || 1000,
    }
  }, [])

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
