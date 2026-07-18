export const BASE = 'http://localhost:8765'

async function withRetry<T>(fn: () => Promise<T>, maxRetries = 3): Promise<T> {
  let lastError: Error | undefined
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (err) {
      lastError = err as Error
      if (i < maxRetries - 1) {
        // 简单的指数退避，每次等待时间递增
        await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)))
      }
    }
  }
  throw lastError
}

export interface Project {
  id: number
  name: string
  language: string
  idea: string
  style: string
  size: string
  size_tier: string
  resolution: string
  frame_rate: number
  duration: number
  chat_model: string
  image_model: string
  video_model: string
  stage: string
  clicks: number
  final_video: string
  final_preview: string
  created_at: string
  updated_at: string
}

export interface ProjectFull extends Project {
  story: string | null
  storyTitle: string
  characters: any[]
  scenes: any[]
  final_video: string
  final_preview: string
  step_statuses: Record<string, number>
  story_fresh: number
  characters_fresh: number
  script_fresh: number
  storyboard_fresh: number
}

export interface ProjectUpdate {
  name?: string
  language?: string
  idea?: string
  style?: string
  size?: string
  size_tier?: string
  resolution?: string
  frame_rate?: number
  duration?: number
  chat_model?: string
  image_model?: string
  video_model?: string
  stage?: string
  story?: string | null
  storyTitle?: string
  characters?: any[]
  scenes?: any[]
  story_fresh?: number
  characters_fresh?: number
  script_fresh?: number
  storyboard_fresh?: number
}

export interface GenerateRequest {
  prompt: string
  model: string
  api_key: string
  base_url: string
  system_prompt?: string
}

export async function getHealth(): Promise<{ status: string }> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/health`)
    return res.json()
  })
}

export async function listProjects(): Promise<Project[]> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/projects`)
    return res.json()
  })
}

export async function listTopCompletedProjects(): Promise<Project[]> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/projects/top-completed`)
    return res.json()
  })
}

export async function incrementProjectClick(id: number): Promise<void> {
  await fetch(`${BASE}/api/projects/${id}/click`, { method: 'POST' })
}

export async function createProject(name: string): Promise<Project> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    })
    return res.json()
  })
}

export async function generateContent(req: GenerateRequest): Promise<{ result: any }> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json()
  })
}

export interface StoryRequest {
  idea: string
  model: string
  api_key: string
  base_url: string
  user_requirement?: string
}

export async function generateStory(req: StoryRequest): Promise<{ result: any }> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/story`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json()
  })
}

export interface ExtractCharactersRequest {
  script: string
  model: string
  api_key: string
  base_url: string
}

export async function extractCharacters(req: ExtractCharactersRequest): Promise<{ characters: any[] }> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/extract-characters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json()
  })
}

export interface ScriptRequest {
  story: string
  characters_text?: string
  model: string
  api_key: string
  base_url: string
  user_requirement?: string
}

export async function generateScript(req: ScriptRequest): Promise<{ text: string; scenes: Array<{ title: string; content: string }> }> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/scene-scripts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json()
  })
}

export interface GeneratePortraitsRequest {
  characters: Array<{
    role_name: string
    appearance?: string
    attire?: string
    front_image?: string
  }>
  view?: 'front' | 'side' | 'back'
  style: string
  model: string
  api_key: string
  base_url: string
  size?: string
  project_id: number
}

export interface SceneStoryboardRequest {
  scene_content: string
  characters: Array<Record<string, any>>
  user_requirement?: string
  style?: string
  model: string
  api_key: string
  base_url: string
}

export async function sceneStoryboard(req: SceneStoryboardRequest): Promise<{
  storyboard: Array<{ title: string; visual_desc: string }>
  shot_descriptions: Array<{
    visual_desc: string
    audio_desc: string
    ff_desc: string
    lf_desc: string
    motion_desc: string
    variation_type: string
    cam_idx: number
    idx: number
  }>
  camera_tree: Array<Record<string, any>>
}> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/scene-storyboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json()
  })
}

export interface GenerateFrameRequest {
  prompt: string
  size: string
  model: string
  api_key: string
  base_url: string
  reference_images?: string[]
}

export async function generateFrame(req: GenerateFrameRequest): Promise<{ url: string }> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/generate-frame`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json()
  })
}

export interface GenerateShotFramesRequest {
  camera_tree: Array<Record<string, any>>
  shot_descriptions: Array<Record<string, any>>
  characters: Array<Record<string, any>>
  character_portraits_registry: Record<string, any>
  model: string
  chat_model?: string
  api_key: string
  base_url: string
  project_id: number
  size?: string
  scene_idx?: number
}

export async function generateShotFrames(req: GenerateShotFramesRequest): Promise<{ frames: Array<{ shot_idx: number, frame_type: string, url: string }> }> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/generate-shot-frames`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json()
  })
}

export async function generatePortraits(req: GeneratePortraitsRequest): Promise<{ url: string; source_url: string }> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/generate-portraits`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req)
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error || `HTTP ${res.status}`)
    }
    return res.json()
  })
}

export interface StepData {
  step: string
  step_statuses: Record<string, number>
  story?: string | null
  storyTitle?: string
  characters?: any[]
  scenes?: any[]
  final_video?: string
  final_preview?: string
}

export async function fetchStepData(projectId: number, step: string): Promise<StepData> {
  const res = await fetch(`${BASE}/api/projects/${projectId}/step-data?step=${step}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function regenerateSceneScripts(projectId: number): Promise<void> {
  const res = await fetch(`${BASE}/api/projects/${projectId}/scene-scripts/generate`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
}

export async function compositeProjectVideo(projectId: number): Promise<void> {
  const res = await fetch(`${BASE}/api/projects/${projectId}/composite-video`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
}

export async function getProject(id: number): Promise<ProjectFull> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/projects/${id}`)
    return res.json()
  })
}

export async function updateProject(id: number, data: ProjectUpdate): Promise<ProjectFull> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/projects/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    })
    return res.json()
  })
}

export async function updateCharacterFeatures(projectId: number, identifier: string, appearance: string, attire: string): Promise<void> {
  await fetch(`${BASE}/api/projects/${projectId}/characters/${encodeURIComponent(identifier)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ appearance, attire }),
  })
}

export async function duplicateProject(id: number): Promise<ProjectFull> {
  return withRetry(async () => {
    const res = await fetch(`${BASE}/api/projects/${id}/duplicate`, {
      method: 'POST'
    })
    return res.json()
  })
}

export async function checkPipelineRunning(): Promise<{ running: boolean; project_id?: number }> {
  try {
    const res = await fetch(`${BASE}/api/pipeline/running`)
    if (!res.ok) return { running: false }
    return await res.json()
  } catch {
    return { running: false }
  }
}

// ── Single-shot frame / video regeneration ─────────────────────────────

export async function regenerateStartFrame(
  projectId: number, sceneIdx: number, shotIdx: number,
): Promise<{ url: string }> {
  const res = await fetch(
    `${BASE}/api/projects/${projectId}/scenes/${sceneIdx}/shots/${shotIdx}/regenerate-start-frame`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function regenerateEndFrame(
  projectId: number, sceneIdx: number, shotIdx: number,
): Promise<{ url: string }> {
  const res = await fetch(
    `${BASE}/api/projects/${projectId}/scenes/${sceneIdx}/shots/${shotIdx}/regenerate-end-frame`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function regenerateShotVideo(
  projectId: number, sceneIdx: number, shotIdx: number,
): Promise<{ video_url: string; video_preview_url: string }> {
  const res = await fetch(
    `${BASE}/api/projects/${projectId}/scenes/${sceneIdx}/shots/${shotIdx}/regenerate-video`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || `HTTP ${res.status}`)
  }
  return res.json()
}
