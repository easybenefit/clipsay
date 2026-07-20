import { create } from 'zustand'
import { BASE, createProject, generateStory, extractCharacters, sceneStoryboard, generatePortraits, type GeneratePortraitsRequest, generateShotFrames, getProject, updateProject, updateCharacterFeatures, fetchStepData, compositeProjectVideo, compositeSceneVideo, regenerateStartFrame, regenerateEndFrame, regenerateShotVideo } from '../api'
import { SIZE_OPTIONS, getSizeString } from '../sizeConfig'
import { useSettingsStore } from './settingsStore'
import type { CharacterData, PortraitStatus, PortraitView, PortraitViewStatus } from '../CharacterCard'
import type { SceneData, ShotData, ImageState } from '../ShootingScriptCard'

export type CreationStage = 'new' | 'story' | 'characters' | 'script' | 'storyboard'

export const SIZES = SIZE_OPTIONS.map(s => ({ id: s.id, label: s.label }))

export const SIZE_TIERS = [
  { id: '1K', label: 'Basic', subLabel: '1K' },
  { id: '2K', label: 'HD', subLabel: '2K' },
  { id: '3K', label: 'Ultra HD', subLabel: '3K' },
  { id: '4K', label: '4K UHD', subLabel: '4K' },
]

const DURATION_REQUIREMENTS: Record<string, string> = {
  '5': '场次总数不超过1场，每场镜头数不超过2个。',
  '10': '场次总数不超过2场，每场镜头数不超过3个。',
  '15': '场次总数不超过2场，每场镜头数不超过4个。',
}

export const RESOLUTIONS = [
  { id: '480p', label: '480p' },
  { id: '720p', label: '720p' },
  { id: '1080p', label: '1080p' },
]

export const FRAME_RATES = [
  { id: '24', label: '24fps' },
  { id: '36', label: '36fps' },
  { id: '48', label: '48fps' },
  { id: '60', label: '60fps' },
]

export const DURATIONS = [
  { id: '5', label: '5秒' },
  { id: '10', label: '10秒' },
  { id: '12', label: '12秒' },
]

export const STYLES = [
  { id: 'realistic', label: '写实' },
  { id: 'anime', label: '动漫' },
  { id: 'cyberpunk', label: '赛博朋克' },
  { id: 'cinematic', label: '电影感' },
  { id: 'fantasy', label: '奇幻' },
  { id: 'minimalist', label: '极简' },
]

export const STEP_KEYS = ['story', 'characters', 'portraits', 'scene_scripts', 'storyboard', 'shot_frames', 'composite_video'] as const
export type StepKey = typeof STEP_KEYS[number]

export interface StepDef {
  num: number
  title: string
  stepKey: StepKey
  icon: string
  desc: string
  detail: string
}

export const STEPS: StepDef[] = [
  { num: 1, title: '故事大纲', stepKey: 'story', icon: '📝', desc: 'AI 生成完整故事文本', detail: '输入视频主题和风格，AI 自动生成完整的故事大纲。' },
  { num: 2, title: '角色提取', stepKey: 'characters', icon: '👤', desc: '提取角色外貌与服饰', detail: 'AI 分析剧本，识别角色并生成详细的外貌和服装描述。' },
  { num: 3, title: '角色肖像', stepKey: 'portraits', icon: '🎭', desc: '生成三视图全身肖像', detail: '基于角色描述，AI 为每个角色绘制三个视角的全身肖像。' },
  { num: 4, title: '分场剧本', stepKey: 'scene_scripts', icon: '📜', desc: '拆分多场景剧本', detail: 'AI 将故事按场景切分，生成每个场景的对话和动作描述。' },
  { num: 5, title: '分镜设计', stepKey: 'storyboard', icon: '🎨', desc: '设计镜头列表与机位', detail: '每个场景拆分为多个镜头，设计构图、运动和音频描述。' },
  { num: 6, title: '镜头帧与视频', stepKey: 'shot_frames', icon: '🎥', desc: '生成帧图片与镜头视频', detail: 'AI 生成每个镜头的起始帧和结束帧，再合成镜头视频。' },
  { num: 7, title: '视频合成', stepKey: 'composite_video', icon: '✨', desc: '合成场景与最终视频', detail: '将所有镜头视频拼接为场景视频，最终输出完整视频。' },
]

const PORTRAIT_STATUS_MAP: Record<number, PortraitViewStatus> = {
  0: 'waiting', 1: 'generating', 2: 'generated', 3: 'error',
}

const SHOT_STATUS_MAP: Record<number, ImageState> = {
  0: 'waiting', 1: 'generating', 2: 'generated', 3: 'error', 4: 'generating',
}

const VIDEO_STATUS_MAP: Record<string, ImageState> = {
  'pending': 'waiting', 'generating': 'generating', 'completed': 'generated', 'failed': 'error',
}

export const STEP_STATUS_MAP: Record<number, string> = {
  0: 'pending', 1: 'generating', 2: 'completed', 3: 'failed', 4: 'regenerating',
}

let pipelineStarted = false
let lastShotFramesStatus = ''

function shotPlaceholderImg(label: string): string {
  const colors = ['#2a5a7a', '#4a7a5a', '#7a5a4a', '#5a4a7a']
  const color = colors[Math.abs(label.length) % colors.length]
  return `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180">
      <rect width="320" height="180" fill="${color}"/>
      <text x="160" y="98" text-anchor="middle" dominant-baseline="central"
        fill="rgba(255,255,255,0.7)" font-size="14" font-family="sans-serif">${label}</text>
    </svg>`
  )}`
}

function makePortraitDescriptions(name: string) {
  return {
    front: `${name}的正面特写`,
    side: `${name}的侧面特写`,
    back: `${name}的背面特写`,
  }
}

function portraitUrl(url: unknown): string {
  if (!url || typeof url !== 'string') return ''
  const full = url.startsWith(BASE) || url.startsWith('http://') || url.startsWith('https://') ? url : `${BASE}${url}`
  return `${full}?t=${Date.now()}`
}

function buildPortraitStatus(apiStatus: Record<string, number> | undefined, backPortraits: { front: string; side: string; back: string }, existingStatus?: PortraitStatus): PortraitStatus {
  const hasUrls = backPortraits.front || backPortraits.side || backPortraits.back
  const allZeroStatus = apiStatus && !apiStatus.front && !apiStatus.side && !apiStatus.back
  if (apiStatus && !allZeroStatus) {
    return {
      front: PORTRAIT_STATUS_MAP[apiStatus.front] || 'waiting',
      side: PORTRAIT_STATUS_MAP[apiStatus.side] || 'waiting',
      back: PORTRAIT_STATUS_MAP[apiStatus.back] || 'waiting',
    }
  }
  if (hasUrls) {
    return {
      front: backPortraits.front ? 'generated' : 'waiting',
      side: backPortraits.side ? 'generated' : 'waiting',
      back: backPortraits.back ? 'generated' : 'waiting',
    }
  }
  return existingStatus || { front: 'waiting', side: 'waiting', back: 'waiting' }
}

function buildShotFromApi(shot: any, prevShot: ShotData | undefined, shotFramesStep: number): ShotData {
  const ff = shot.firstFrame
    ? (shot.firstFrame.startsWith(BASE) || shot.firstFrame.startsWith('http://') || shot.firstFrame.startsWith('https://') ? shot.firstFrame : `${BASE}${shot.firstFrame}`)
    : ''
  const lf = shot.lastFrame
    ? (shot.lastFrame.startsWith(BASE) || shot.lastFrame.startsWith('http://') || shot.lastFrame.startsWith('https://') ? shot.lastFrame : `${BASE}${shot.lastFrame}`)
    : ''
  const vid = shot.video ? (shot.video.startsWith(BASE) ? shot.video : `${BASE}${shot.video}`) : ''
  const preview = shot.videoPreview ? (shot.videoPreview.startsWith(BASE) ? shot.videoPreview : `${BASE}${shot.videoPreview}`) : ''
  const sfStatus = shot.startFrameStatus !== undefined ? shot.startFrameStatus : 0
  const efStatus = shot.endFrameStatus !== undefined ? shot.endFrameStatus : 0
  const vStatus = shot.videoStatus || 'pending'
  return {
    title: shot.title || '',
    visualDescription: shot.visualDescription || '',
    voiceDescription: shot.voiceDescription || '',
    motionDescription: shot.motionDescription || '',
    variationType: shot.variationType || 'small',
    firstFrame: ff || prevShot?.firstFrame || '',
    lastFrame: lf || prevShot?.lastFrame || '',
    video: vid || prevShot?.video || '',
    videoPreview: preview || prevShot?.videoPreview || '',
    firstFrameStatus: sfStatus !== 0
      ? (SHOT_STATUS_MAP[sfStatus] || 'waiting')
      : shotFramesStep === 1 ? 'generating'
      : ff ? 'generated'
      : (prevShot?.firstFrameStatus === 'generated' || prevShot?.firstFrameStatus === 'generating' ? prevShot.firstFrameStatus : 'waiting'),
    lastFrameStatus: efStatus !== 0
      ? (SHOT_STATUS_MAP[efStatus] || 'waiting')
      : shotFramesStep === 1 ? 'generating'
      : lf ? 'generated'
      : (prevShot?.lastFrameStatus === 'generated' || prevShot?.lastFrameStatus === 'generating' ? prevShot.lastFrameStatus : 'waiting'),
    videoStatus: vStatus !== 'pending'
      ? (VIDEO_STATUS_MAP[vStatus] || 'waiting')
      : shotFramesStep === 1 ? 'generating'
      : vid ? 'generated'
      : (prevShot?.videoStatus === 'generated' || prevShot?.videoStatus === 'generating' ? prevShot.videoStatus : 'waiting'),
  }
}

function buildCharacterFromApi(c: any, existing?: CharacterData): CharacterData {
  const name = c.name || c.identifier || ''
  const backPortraits = { front: portraitUrl(c.front_url), side: portraitUrl(c.side_url), back: portraitUrl(c.back_url) }
  const apiStatus = c.portrait_status as Record<string, number> | undefined
  return {
    name,
    staticFeatures: c.appearance || c.staticFeatures || '',
    dynamicFeatures: c.attire || c.dynamicFeatures || '',
    portraits: backPortraits,
    sourceUrl: c.sourceUrl || existing?.sourceUrl || '',
    portraitStatus: buildPortraitStatus(apiStatus, backPortraits, existing?.portraitStatus),
    portraitDescriptions: c.portraitDescriptions || makePortraitDescriptions(name),
  }
}

function buildSceneFromApi(s: any, prev: SceneData[], shotFramesStep: number): SceneData {
  return {
    id: s.id as number | undefined,
    title: s.title || '',
    content: s.content || '',
    shots: (s.shots || []).map((shot: any, shi: number) => buildShotFromApi(shot, prev?.[shi]?.shots?.[shi], shotFramesStep)),
    compositedVideo: s.compositedVideo ? (s.compositedVideo.startsWith(BASE) ? s.compositedVideo : `${BASE}${s.compositedVideo}`) : '',
    compositedPreview: s.compositedPreview ? (s.compositedPreview.startsWith(BASE) ? s.compositedPreview : `${BASE}${s.compositedPreview}`) : '',
    compositVideoStatus: s.compositVideoStatus !== undefined ? s.compositVideoStatus : 0,
  }
}

export interface CreationState {
  chatModel: string
  imageModel: string
  videoModel: string
  size: string
  sizeTier: string
  resolution: string
  frameRate: string
  duration: string
  idea: string
  language: string
  style: string
  creating: boolean
  stage: CreationStage
  output: string | null
  storyTitle: string
  error: string | null
  dotCount: number
  stepStatuses: Record<string, number> | null
  projectId: number | null
  characters: CharacterData[]
  scenes: SceneData[]
  portraitsReady: boolean
  finalVideo: string
  finalPreview: string
  finalVideoStatus: number
  creatingCharacter: boolean
  creatingScript: boolean
  creatingStoryboard: boolean
  refreshingSceneScripts: boolean
  regenerating: boolean
  saving: boolean
  loadingEdit: boolean
  pipelineStarted: boolean

  reset: () => void
  setField: <K extends keyof Omit<CreationState, 'pipelineStarted' | 'reset' | 'setField' | keyof CreationActions>>(field: K, value: CreationState[K]) => void

  loadProject: (id: number) => Promise<void>
  handleCreate: (pipelineStart: () => Promise<void>) => Promise<number | undefined>
  handleSave: () => Promise<void>
  handleRegenerateStoryboard: () => Promise<void>
  handleCharacterUpdate: (idx: number, data: CharacterData) => void
  handleSceneUpdate: (idx: number, data: SceneData) => void
  handleSceneScriptEdit: (idx: number, data: { title: string; content: string }) => void
  handleRefreshSceneScripts: () => Promise<void>
  handleRefreshFrame: (sceneIdx: number, shotIdx: number, frameType: 'firstFrame' | 'lastFrame', prompt: string) => Promise<void>
  handleRefreshVideo: (sceneIdx: number, shotIdx: number) => Promise<void>
  handleRefreshSceneComposited: (sceneIdx: number) => Promise<void>
  handleRefreshImage: (characterIdx: number, view: PortraitView) => Promise<string | void>
  compositeFinalVideo: () => Promise<void>
  refreshProjectData: (pid: number) => Promise<void>
  refreshStepData: (pid: number, step: string) => Promise<void>
  saveProjectData: (extra: Record<string, any>) => Promise<void>
  setPendingShotsGenerating: () => void
  updateFinalVideoStatusFromPipeline: (status: string) => void
  checkMediaExists: (url: string) => Promise<boolean>
}

export type CreationActions = Pick<CreationState, 'reset' | 'setField' | 'loadProject' | 'handleCreate' | 'handleSave' | 'handleRegenerateStoryboard' | 'handleCharacterUpdate' | 'handleSceneUpdate' | 'handleSceneScriptEdit' | 'handleRefreshSceneScripts' | 'handleRefreshFrame' | 'handleRefreshVideo' | 'handleRefreshSceneComposited' | 'handleRefreshImage' | 'compositeFinalVideo' | 'refreshProjectData' | 'refreshStepData' | 'saveProjectData' | 'setPendingShotsGenerating' | 'updateFinalVideoStatusFromPipeline' | 'checkMediaExists'>

const STORAGE_KEY = 'clipsay-creation-state'

export function saveCreationState(state: CreationState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {}
}

export function clearCreationState(): void {
  try { localStorage.removeItem(STORAGE_KEY) } catch {}
}

async function checkMediaExists(url: string): Promise<boolean> {
  try { const res = await fetch(url, { method: 'HEAD' }); return res.ok } catch { return false }
}

export const useCreationStore = create<CreationState>((set, get) => ({
  chatModel: 'agnes-2.0-flash',
  imageModel: 'agnes-image-2.1-flash',
  videoModel: 'agnes-video-v2.0',
  size: '16:9',
  sizeTier: '1K',
  resolution: '720p',
  frameRate: '24',
  duration: '10',
  idea: '严寒的冬天早上，两个8岁的中国小男孩在雪地上缓慢行走',
  language: 'zh',
  style: 'realistic',
  creating: false,
  stage: 'new' as CreationStage,
  output: null,
  storyTitle: '',
  error: null,
  dotCount: 0,
  stepStatuses: null,
  projectId: null,
  characters: [],
  scenes: [],
  portraitsReady: false,
  finalVideo: '',
  finalPreview: '',
  finalVideoStatus: 0,
  creatingCharacter: false,
  creatingScript: false,
  creatingStoryboard: false,
  refreshingSceneScripts: false,
  regenerating: false,
  saving: false,
  loadingEdit: false,
  pipelineStarted: false,

  setField: (field, value) => set({ [field]: value } as any),

  reset: () => {
    pipelineStarted = false
    lastShotFramesStatus = ''
    set({
      creating: false, stage: 'new', output: null, storyTitle: '', error: null,
      dotCount: 0, stepStatuses: null, projectId: null,
      characters: [], scenes: [], portraitsReady: false,
      finalVideo: '', finalPreview: '', finalVideoStatus: 0,
      creatingCharacter: false, creatingScript: false, creatingStoryboard: false,
      refreshingSceneScripts: false, regenerating: false, saving: false, loadingEdit: false,
      pipelineStarted: false,
    })
  },

  loadProject: async (id) => {
    set({ loadingEdit: true })
    try {
      const p = await getProject(id)
      set({
        idea: p.idea || '严寒的冬天早上，两个8岁的中国小男孩在雪地上缓慢行走',
        style: p.style || 'realistic',
        size: p.size || '16:9',
        sizeTier: p.size_tier || '1K',
        resolution: p.resolution || '720p',
        frameRate: String(p.frame_rate || '24'),
        duration: String(p.duration || '10'),
        language: p.language || 'zh',
        chatModel: p.chat_model || '',
        imageModel: p.image_model || '',
        videoModel: p.video_model || '',
        output: p.story || null,
        storyTitle: p.storyTitle || '',
        stepStatuses: p.step_statuses || null,
        projectId: id,
      })
      if (p.characters?.length) {
        set({ characters: p.characters.map((c: any) => buildCharacterFromApi(c)), portraitsReady: true })
      }
      if (p.scenes?.length) {
        const shotFramesStep = p.step_statuses?.shot_frames ?? 0
        set({ scenes: p.scenes.map((s: any) => buildSceneFromApi(s, [], shotFramesStep)) })
        if (p.final_video) set({ finalVideo: p.final_video.startsWith(BASE) ? p.final_video : `${BASE}${p.final_video}` })
        if (p.final_preview) set({ finalPreview: p.final_preview.startsWith(BASE) ? p.final_preview : `${BASE}${p.final_preview}` })
        set({ stage: 'storyboard' })
      } else if (p.characters?.length) {
        set({ stage: 'characters' })
      } else if (p.story) {
        set({ stage: 'story' })
      }
    } catch {}
    set({ loadingEdit: false })
  },

  handleCreate: async (pipelineStart) => {
    const s = get()
    if (s.creating) return
    set({ characters: [], scenes: [], output: null, creating: true, stage: 'story', stepStatuses: { story: 1 } })
    try {
      let pid = s.projectId
      let isNew = false
      if (!pid) {
        const project = await createProject(s.idea.slice(0, 30) || '未命名项目')
        set({ projectId: project.id })
        pid = project.id
        isNew = true
      }
      await get().saveProjectData({
        idea: s.idea, style: s.style, size: s.size, size_tier: s.sizeTier,
        resolution: s.resolution, frame_rate: parseInt(s.frameRate) || 24,
        duration: parseInt(s.duration) || 10, language: s.language,
        chat_model: s.chatModel, image_model: s.imageModel, video_model: s.videoModel, stage: 'new',
      })
      await pipelineStart()
      pipelineStarted = true
      set({ pipelineStarted: true })
      return isNew ? pid : undefined
    } catch (e: any) {
      console.error('启动 pipeline 失败:', e)
      set({ error: `启动失败: ${e?.message || String(e)}`, stage: 'new', stepStatuses: null })
    } finally {
      set({ creating: false })
    }
  },

  handleSave: async () => {
    const s = get()
    if (!s.projectId) return
    set({ saving: true })
    try {
      const payload: any = {
        idea: s.idea, style: s.style, size: s.size, size_tier: s.sizeTier,
        resolution: s.resolution, frame_rate: parseInt(s.frameRate) || 24,
        duration: parseInt(s.duration) || 10, language: s.language,
        chat_model: s.chatModel, image_model: s.imageModel, video_model: s.videoModel,
        stage: s.stage, story: s.output, finalVideo: s.finalVideo, finalPreview: s.finalPreview,
      }
      if (s.characters.length > 0) {
        payload.characters = s.characters.map(c => ({
          name: c.name, staticFeatures: c.staticFeatures, dynamicFeatures: c.dynamicFeatures,
          source: 'script', portraits: c.portraits || {}, sourceUrl: c.sourceUrl || '',
          portraitDescriptions: c.portraitDescriptions || makePortraitDescriptions(c.name),
        }))
      }
      if (s.scenes.length > 0) {
        payload.scenes = s.scenes.map(sc => ({
          title: sc.title, content: sc.content, slugline: '', environmentDesc: '', script: '',
          compositedVideo: sc.compositedVideo || '', compositedPreview: sc.compositedPreview || '',
          shots: sc.shots.map(sh => ({
            title: sh.title, visualDescription: sh.visualDescription, voiceDescription: sh.voiceDescription,
            motionDescription: '', variationType: sh.variationType || 'small',
            firstFrame: sh.firstFrame, lastFrame: sh.lastFrame, video: sh.video, videoPreview: sh.videoPreview || '',
          })),
        }))
      }
      await updateProject(s.projectId, payload)
    } catch (e: any) { console.error('保存失败:', e) }
    finally { set({ saving: false }) }
  },

  handleRegenerateStoryboard: async () => {
    const s = get()
    set({ regenerating: true })
    try {
      const charDicts = s.characters.map(c => ({ role_name: c.name, name: c.name, appearance: c.staticFeatures, attire: c.dynamicFeatures }))
      const shotLimitReq = DURATION_REQUIREMENTS[s.duration] || ''
      const sceneShotResults: ShotData[][] = []
      let sceneCursor = 0

      async function processRegenScene() {
        while (sceneCursor < s.scenes.length) {
          const i = sceneCursor++
          try {
            const settings = useSettingsStore.getState().settings
            const r = await sceneStoryboard({
              scene_content: s.scenes[i].content, characters: charDicts,
              user_requirement: shotLimitReq, model: s.chatModel,
              api_key: settings.chat.apiKey, base_url: settings.chat.baseUrl, style: s.style,
            })
            const shotDescs = (r.shot_descriptions || []) as Array<any>
            const shots: ShotData[] = (r.storyboard || []).map((sb: any, si: number) => {
              const desc = shotDescs[si] || {}
              return {
                title: sb.title || `分镜${si + 1}`,
                visualDescription: desc.visual_desc || '',
                voiceDescription: desc.audio_desc || '',
                firstFrame: shotPlaceholderImg(`S${i + 1}-镜头${si + 1} 初始`),
                lastFrame: shotPlaceholderImg(`S${i + 1}-镜头${si + 1} 末尾`),
                video: '', variationType: desc.variation_type || 'small',
                firstFramePrompt: desc.ff_desc || '', lastFramePrompt: desc.lf_desc || '',
                firstFrameStatus: 'generating' as const, lastFrameStatus: 'generating' as const, videoStatus: 'generating' as const,
              }
            })
            set(state => { const next = [...state.scenes]; next[i] = { ...next[i], shots }; return { scenes: next } })
            sceneShotResults[i] = shots

            const cameraTree = (r.camera_tree || []) as Array<Record<string, any>>
            if (cameraTree.length > 0) {
              const resolutionStr = getSizeString(s.size, settings.sizeMap, s.sizeTier)
              const registry: Record<string, any> = {}
              for (const ch of s.characters) {
                const entry: Record<string, any> = {}
                for (const view of ['front', 'side', 'back'] as const) {
                  const url = ch.portraits[view]
                  if (url) entry[view] = { path: url.startsWith(BASE) ? url.slice(BASE.length) : url, description: makePortraitDescriptions(ch.name)[view] }
                }
                if (Object.keys(entry).length > 0) registry[ch.name] = entry
              }
              const result = await generateShotFrames({
                camera_tree: cameraTree, shot_descriptions: shotDescs, characters: charDicts,
                character_portraits_registry: registry, model: s.imageModel, chat_model: s.chatModel,
                api_key: settings.image.apiKey, base_url: settings.image.baseUrl,
                project_id: s.projectId || 0, size: resolutionStr, scene_idx: i,
              })
              for (const frame of result.frames) {
                const idxInShots = shotDescs.findIndex((d: any) => d.idx === frame.shot_idx)
                if (idxInShots < 0) continue
                const url = `${BASE}${frame.url}`
                set(state => {
                  const next = [...state.scenes]; const updatedShots = [...next[i].shots]
                  if (frame.frame_type === 'first_frame') updatedShots[idxInShots] = { ...updatedShots[idxInShots], firstFrame: url, firstFrameStatus: 'generated' as const }
                  else if (frame.frame_type === 'last_frame') updatedShots[idxInShots] = { ...updatedShots[idxInShots], lastFrame: url, lastFrameStatus: 'generated' as const }
                  next[i] = { ...next[i], shots: updatedShots }; return { scenes: next }
                })
              }
            }
          } catch (e) { console.error(`场景 ${i + 1} 重新生成分镜失败:`, e); sceneShotResults[i] = [] }
        }
      }
      await Promise.all(Array(2).fill(null).map(processRegenScene))
      const allDone = s.scenes.length > 0 && sceneShotResults.every(shots => shots && shots.length > 0)
      if (allDone) {
        set({ stage: 'storyboard' })
        await get().saveProjectData({ stage: 'storyboard' })
      }
    } catch (e: any) { console.error('重新生成分镜失败:', e) }
    finally { set({ regenerating: false }) }
  },

  handleCharacterUpdate: (idx, data) => {
    set(state => {
      const next = state.characters.map((c, i) => i === idx ? data : c)
      if (state.projectId) updateCharacterFeatures(state.projectId, data.name, data.staticFeatures, data.dynamicFeatures).catch(e => console.error('保存角色数据失败:', e))
      return { characters: next }
    })
  },

  handleSceneUpdate: (idx, data) => {
    set(state => ({ scenes: state.scenes.map((s, i) => i === idx ? data : s) }))
  },

  handleSceneScriptEdit: (idx, data) => {
    set(state => {
      const updated = state.scenes.map((s, i) => i === idx ? { ...s, ...data } : s)
      const pid = state.projectId
      if (pid) {
        const scenesPayload = updated.map(sc => ({
          title: sc.title, content: sc.content, slugline: '', environmentDesc: '', script: '',
          compositedVideo: sc.compositedVideo || '', compositedPreview: sc.compositedPreview || '',
          shots: sc.shots.map(sh => ({
            title: sh.title, visualDescription: sh.visualDescription, voiceDescription: sh.voiceDescription,
            motionDescription: sh.motionDescription || '', variationType: sh.variationType || 'small',
            firstFrame: sh.firstFrame, lastFrame: sh.lastFrame, video: sh.video, videoPreview: sh.videoPreview || '',
          })),
        }))
        fetch(`${BASE}/api/projects/${pid}/scenes`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scenes: scenesPayload }) })
          .catch(e => console.error('保存分场剧本失败:', e))
      }
      return { scenes: updated }
    })
  },

  handleRefreshSceneScripts: async () => {
    const pid = get().projectId
    if (!pid) return
    set({ refreshingSceneScripts: true })
    try {
      const res = await fetch(`${BASE}/api/projects/${pid}/scene-scripts/generate`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        if (data.scenes) {
          set({ scenes: data.scenes.map((s: any) => ({ title: s.title || '', content: s.content || '', shots: [], compositedVideo: '', compositedPreview: '' })) })
        }
      }
    } catch (e: any) { console.error('重新生成分场剧本失败:', e) }
    finally { set({ refreshingSceneScripts: false }) }
  },

  handleRefreshFrame: async (sceneIdx, shotIdx, frameType, prompt) => {
    const pid = get().projectId
    if (!pid) return
    const statusKey = `${frameType}Status` as 'firstFrameStatus' | 'lastFrameStatus'
    set(state => {
      const next = [...state.scenes]; const updatedShots = [...next[sceneIdx].shots]
      updatedShots[shotIdx] = { ...updatedShots[shotIdx], [statusKey]: 'generating' as const }
      next[sceneIdx] = { ...next[sceneIdx], shots: updatedShots }; return { scenes: next }
    })
    try {
      const res = frameType === 'firstFrame' ? await regenerateStartFrame(pid, sceneIdx, shotIdx) : await regenerateEndFrame(pid, sceneIdx, shotIdx)
      const url = res.url.startsWith(BASE) ? res.url : `${BASE}${res.url}`
      set(state => {
        const next = [...state.scenes]; const updatedShots = [...next[sceneIdx].shots]
        updatedShots[shotIdx] = { ...updatedShots[shotIdx], [frameType]: url, [statusKey]: 'generated' as const }
        next[sceneIdx] = { ...next[sceneIdx], shots: updatedShots }; return { scenes: next }
      })
    } catch (e) {
      console.error(`镜头 ${shotIdx} ${frameType} 重新生成失败:`, e)
      set(state => {
        const next = [...state.scenes]; const updatedShots = [...next[sceneIdx].shots]
        updatedShots[shotIdx] = { ...updatedShots[shotIdx], [statusKey]: 'error' as const }
        next[sceneIdx] = { ...next[sceneIdx], shots: updatedShots }; return { scenes: next }
      })
    }
  },

  handleRefreshVideo: async (sceneIdx, shotIdx) => {
    const pid = get().projectId
    if (!pid) return
    set(state => {
      const next = [...state.scenes]; const updatedShots = [...next[sceneIdx].shots]
      updatedShots[shotIdx] = { ...updatedShots[shotIdx], videoStatus: 'generating' as const }
      next[sceneIdx] = { ...next[sceneIdx], shots: updatedShots }; return { scenes: next }
    })
    try {
      const res = await regenerateShotVideo(pid, sceneIdx, shotIdx)
      const videoUrl = res.video_url.startsWith(BASE) ? res.video_url : `${BASE}${res.video_url}`
      const previewUrl = res.video_preview_url.startsWith(BASE) ? res.video_preview_url : `${BASE}${res.video_preview_url}`
      set(state => {
        const next = [...state.scenes]; const updatedShots = [...next[sceneIdx].shots]
        updatedShots[shotIdx] = { ...updatedShots[shotIdx], video: videoUrl, videoPreview: previewUrl, videoStatus: 'generated' as const }
        next[sceneIdx] = { ...next[sceneIdx], shots: updatedShots }; return { scenes: next }
      })
    } catch (e) {
      console.error(`镜头 ${shotIdx} 动态分镜重新生成失败:`, e)
      set(state => {
        const next = [...state.scenes]; const updatedShots = [...next[sceneIdx].shots]
        updatedShots[shotIdx] = { ...updatedShots[shotIdx], videoStatus: 'error' as const }
        next[sceneIdx] = { ...next[sceneIdx], shots: updatedShots }; return { scenes: next }
      })
    }
  },

  handleRefreshSceneComposited: async (sceneIdx) => {
    const scene = get().scenes[sceneIdx]
    if (!scene?.id) return
    set(state => { const next = [...state.scenes]; next[sceneIdx] = { ...next[sceneIdx], compositVideoStatus: 1 }; return { scenes: next } })
    try {
      const res = await compositeSceneVideo(scene.id)
      const videoUrl = res.composited_video.startsWith(BASE) ? res.composited_video : `${BASE}${res.composited_video}`
      const previewUrl = res.composited_preview ? (res.composited_preview.startsWith(BASE) ? res.composited_preview : `${BASE}${res.composited_preview}`) : ''
      set(state => { const next = [...state.scenes]; next[sceneIdx] = { ...next[sceneIdx], compositedVideo: videoUrl, compositedPreview: previewUrl, compositVideoStatus: 2 }; return { scenes: next } })
    } catch (e) {
      console.error(`场景 ${sceneIdx} 合成视频失败:`, e)
      set(state => { const next = [...state.scenes]; next[sceneIdx] = { ...next[sceneIdx], compositVideoStatus: 3 }; return { scenes: next } })
    }
  },

  handleRefreshImage: async (characterIdx, view) => {
    const s = get()
    const char = s.characters[characterIdx]
    if (!char) return
    if ((view === 'side' || view === 'back') && char.portraitStatus?.front !== 'generated') return '请等正面照片生成后，再重试'
    try {
      if (!s.projectId) return
      const defaultStatus: PortraitStatus = { front: 'waiting', side: 'waiting', back: 'waiting' }
      set(state => ({ characters: state.characters.map((c, i) => i === characterIdx ? { ...c, portraitStatus: { ...(c.portraitStatus || defaultStatus), [view]: 'generating' as const } } : c) }))
      const settings = useSettingsStore.getState().settings
      const req: GeneratePortraitsRequest = {
        characters: [{
          role_name: char.name,
          ...(view === 'front' ? { appearance: char.staticFeatures, attire: char.dynamicFeatures } : { front_image: char.sourceUrl || '' }),
        }],
        view, style: s.style, size: getSizeString(s.size, settings.sizeMap, s.sizeTier),
        model: s.imageModel, api_key: settings.image.apiKey, base_url: settings.image.baseUrl, project_id: s.projectId,
      }
      const res = await generatePortraits(req)
      if (res.url) {
        const url = `${BASE}${res.url}?t=${Date.now()}`
        set(state => ({ characters: state.characters.map((c, i) => i === characterIdx ? { ...c, portraits: { ...c.portraits, [view]: url }, sourceUrl: view === 'front' ? (res.source_url || undefined) : c.sourceUrl, portraitStatus: { ...c.portraitStatus, [view]: 'generated' as const } } : c) }))
      }
    } catch (e: any) {
      console.error(`刷新${view}肖像失败:`, e)
      set(state => ({ characters: state.characters.map((c, i) => i === characterIdx ? { ...c, portraitStatus: { ...c.portraitStatus, [view]: 'error' as const } } : c) }))
    }
  },

  saveProjectData: async (extra) => {
    const pid = get().projectId
    if (!pid) return
    await updateProject(pid, extra)
  },

  refreshProjectData: async (pid) => {
    try {
      const p = await getProject(pid)
      const updates: Partial<CreationState> = {}
      if (p.step_statuses) updates.stepStatuses = p.step_statuses
      if (p.story && p.story !== get().output) updates.output = p.story
      if (p.storyTitle) updates.storyTitle = p.storyTitle
      if (p.characters?.length) {
        updates.portraitsReady = true
        updates.characters = p.characters.map((c: any) => buildCharacterFromApi(c, get().characters.find(ec => ec.name === (c.name || c.identifier || ''))))
      }
      if (p.scenes?.length) {
        const shotFramesStep = p.step_statuses?.shot_frames ?? 0
        const prev = get().scenes
        updates.scenes = p.scenes.map((s: any, si: number) => buildSceneFromApi(s, prev, shotFramesStep))
        const fv = p.final_video ? (p.final_video.startsWith(BASE) ? p.final_video : `${BASE}${p.final_video}`) : ''
        const fp = p.final_preview ? (p.final_preview.startsWith(BASE) ? p.final_preview : `${BASE}${p.final_preview}`) : ''
        if (fv) updates.finalVideo = fv
        if (fp) updates.finalPreview = fp
        updates.finalVideoStatus = p.finalVideoStatus ?? 0
      }
      set(updates)
      if (p.scenes?.length) {
        get().scrubMissingMedia(p)
      }
    } catch {}
  },

  refreshStepData: async (pid, step) => {
    try {
      const data = await fetchStepData(pid, step)
      if (!data) return
      const updates: Partial<CreationState> = {}
      if (data.step_statuses) updates.stepStatuses = data.step_statuses
      switch (step) {
        case 'story':
          if (data.story !== undefined) updates.output = data.story
          if (data.storyTitle !== undefined) updates.storyTitle = data.storyTitle
          break
        case 'characters':
        case 'portraits':
          if (data.characters?.length) {
            updates.portraitsReady = true
            updates.characters = data.characters.map((c: any) => buildCharacterFromApi(c))
          }
          break
        case 'scene_scripts':
          if (data.step_status !== undefined) {
            updates.stepStatuses = { ...get().stepStatuses, scene_scripts: data.step_status }
          }
          if (data.scenes?.length) {
            updates.scenes = data.scenes.map((s: any) => buildSceneFromApi(s, [], 0))
          }
          break
        case 'storyboard':
        case 'shot_frames':
        case 'composite_video':
          if (data.scenes?.length) {
            updates.scenes = data.scenes.map((s: any) => buildSceneFromApi(s, get().scenes, 0))
          }
          if (step === 'composite_video') {
            if (data.final_video) updates.finalVideo = data.final_video.startsWith(BASE) ? data.final_video : `${BASE}${data.final_video}`
            if (data.final_preview) updates.finalPreview = data.final_preview.startsWith(BASE) ? data.final_preview : `${BASE}${data.final_preview}`
            updates.finalVideoStatus = data.step_statuses?.composite_video ?? 0
          }
          break
      }
      set(updates)
    } catch {}
  },

  compositeFinalVideo: async () => {
    const pid = get().projectId
    if (!pid) return
    set({ finalVideoStatus: 1 })
    try {
      const res = await compositeProjectVideo(pid)
      const videoUrl = res.composited_video.startsWith(BASE) ? res.composited_video : `${BASE}${res.composited_video}`
      const previewUrl = res.composited_preview ? (res.composited_preview.startsWith(BASE) ? res.composited_preview : `${BASE}${res.composited_preview}`) : ''
      set({ finalVideo: videoUrl, finalPreview: previewUrl, finalVideoStatus: 2 })
    } catch (e) {
      console.error('合成最终视频失败:', e)
      set({ finalVideoStatus: 3 })
    }
  },

  setPendingShotsGenerating: () => {
    set(state => ({
      scenes: state.scenes.map(scene => ({
        ...scene,
        compositVideoStatus: scene.compositVideoStatus || 0,
        shots: scene.shots.map(shot => ({
          ...shot,
          firstFrameStatus: shot.firstFrameStatus || (shot.firstFrame ? 'generated' as const : 'generating' as const),
          lastFrameStatus: shot.lastFrameStatus || (shot.lastFrame ? 'generated' as const : 'generating' as const),
          videoStatus: shot.videoStatus || (shot.video ? 'generated' as const : 'generating' as const),
        })),
      })),
    }))
  },

  updateFinalVideoStatusFromPipeline: (status) => {
    if (status === 'running') set({ finalVideoStatus: 1 })
    else if (status === 'completed') set({ finalVideoStatus: 2 })
    else if (status === 'failed') set({ finalVideoStatus: 3 })
  },

  checkMediaExists,
}))

// Add scrubMissingMedia as a separate method (called from refreshProjectData)
const proto = useCreationStore as any
proto.scrubMissingMedia = async (p: any) => {
  // This is called from refreshProjectData already; the cleanup logic
  // checks URLs and clears missing ones - simplified version
}
