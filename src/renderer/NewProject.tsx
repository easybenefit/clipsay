import { useState, useEffect, useRef, useCallback } from 'react'
import { BASE, createProject, generateStory, extractCharacters, generateScript, sceneStoryboard, generatePortraits, generateFrame, generateShotFrames, getProject, updateProject } from './api'
import { usePipelineSSE } from './usePipelineSSE'

import StoryCard from './StoryCard'
import CharacterCard from './CharacterCard'
import ShootingScriptCard from './ShootingScriptCard'
import SceneScriptsCard from './SceneScriptsCard'
import type { CharacterData, PortraitStatus, PortraitView } from './CharacterCard'
import type { SceneData, ShotData } from './ShootingScriptCard'
import { SIZE_OPTIONS, getSizeString } from './sizeConfig'
import type { CreationStage } from './creationStore'

import './NewProject.css'

interface NewProjectProps {
  onCreated: () => void
  onCancel: () => void
  onProjectSelected?: (projectId: number) => void
  chatOptions: string[]
  imageOptions: string[]
  videoOptions: string[]
  chatApiKey: string
  chatBaseUrl: string
  imageApiKey: string
  imageBaseUrl: string
  videoApiKey: string
  videoBaseUrl: string
  chatRateLimitMin: string
  chatRateLimitDay: string
  imageRateLimitMin: string
  imageRateLimitDay: string
  videoRateLimitMin: string
  videoRateLimitDay: string
  sizeMap: Record<string, string>
  defaultSize: string
  editProjectId?: number
}

const SIZES = SIZE_OPTIONS.map(s => ({ id: s.id, label: s.label }))

const DURATION_REQUIREMENTS: Record<string, string> = {
  '5': '场次总数不超过1场，每场镜头数不超过2个。',
  '10': '场次总数不超过2场，每场镜头数不超过3个。',
  '15': '场次总数不超过2场，每场镜头数不超过4个。',
}

const RESOLUTIONS = [
  { id: '480p', label: '480p' },
  { id: '720p', label: '720p' },
  { id: '1080p', label: '1080p' },
]

const FRAME_RATES = [
  { id: '24', label: '24fps' },
  { id: '36', label: '36fps' },
  { id: '48', label: '48fps' },
  { id: '60', label: '60fps' },
]

const DURATIONS = [
  { id: '5', label: '5秒' },
  { id: '10', label: '10秒' },
  { id: '12', label: '12秒' },
]

const STYLES = [
  { id: 'realistic', label: '写实' },
  { id: 'anime', label: '动漫' },
  { id: 'cyberpunk', label: '赛博朋克' },
  { id: 'cinematic', label: '电影感' },
  { id: 'fantasy', label: '奇幻' },
  { id: 'minimalist', label: '极简' },
]

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

const STEP_KEYS = ['story', 'characters', 'portraits', 'scene_scripts', 'storyboard', 'shot_frames', 'composite_video'] as const
type StepKey = typeof STEP_KEYS[number]

interface StepDef {
  num: number
  title: string
  stepKey: StepKey
  icon: string
  desc: string
  detail: string
}

const STEPS: StepDef[] = [
  { num: 1, title: '故事大纲', stepKey: 'story', icon: '📝', desc: 'AI 生成完整故事文本', detail: '输入视频主题和风格，AI 自动生成完整的故事大纲。' },
  { num: 2, title: '角色提取', stepKey: 'characters', icon: '👤', desc: '提取角色外貌与服饰', detail: 'AI 分析剧本，识别角色并生成详细的外貌和服装描述。' },
  { num: 3, title: '角色肖像', stepKey: 'portraits', icon: '🎭', desc: '生成三视图全身肖像', detail: '基于角色描述，AI 为每个角色绘制三个视角的全身肖像。' },
  { num: 4, title: '分场剧本', stepKey: 'scene_scripts', icon: '📜', desc: '拆分多场景剧本', detail: 'AI 将故事按场景切分，生成每个场景的对话和动作描述。' },
  { num: 5, title: '分镜设计', stepKey: 'storyboard', icon: '🎨', desc: '设计镜头列表与机位', detail: '每个场景拆分为多个镜头，设计构图、运动和音频描述。' },
  { num: 6, title: '镜头帧与视频', stepKey: 'shot_frames', icon: '🎥', desc: '生成帧图片与镜头视频', detail: 'AI 生成每个镜头的起始帧和结束帧，再合成镜头视频。' },
  { num: 7, title: '视频合成', stepKey: 'composite_video', icon: '✨', desc: '合成场景与最终视频', detail: '将所有镜头视频拼接为场景视频，最终输出完整视频。' },
]

function NewProject(props: NewProjectProps): JSX.Element {
  const [chatModel, setChatModel] = useState(props.chatOptions[0] ?? '')
  const [imageModel, setImageModel] = useState(props.imageOptions[0] ?? '')
  const [videoModel, setVideoModel] = useState(props.videoOptions[0] ?? '')
  const [size, setSize] = useState(props.defaultSize || '16:9')
  const [resolution, setResolution] = useState('720p')
  const [frameRate, setFrameRate] = useState('24')
  const [duration, setDuration] = useState('10')
  const [idea, setIdea] = useState('严寒的冬天早上，两个8岁的中国小男孩在雪地上缓慢行走')
  const [language, setLanguage] = useState('zh')
  const [style, setStyle] = useState('realistic')
  const canGenerate = idea.trim().length >= 10
  const [creating, setCreating] = useState(false)
  const [output, setOutput] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dotCount, setDotCount] = useState(0)
  const [stage, setStage] = useState<CreationStage>('new')
  const [creatingCharacter, setCreatingCharacter] = useState(false)
  const [characters, setCharacters] = useState<CharacterData[]>([])
  const [creatingScript, setCreatingScript] = useState(false)
  const [creatingStoryboard, setCreatingStoryboard] = useState(false)
  const [portraitsReady, setPortraitsReady] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [scenes, setScenes] = useState<SceneData[]>([])
  const [finalVideo, setFinalVideo] = useState('')
  const [finalPreview, setFinalPreview] = useState('')
  const portraitRegistryRef = useRef<Record<string, any>>({})
  const pendingPortraitEventsRef = useRef<Array<{ identifier: string; view: string; status: string; image_url?: string }>>([])
  const [saving, setSaving] = useState(false)
  const [loadingEdit, setLoadingEdit] = useState(false)
  const [projectId, setProjectId] = useState<number | null>(null)
  const projectIdRef = useRef<number | null>(null)
  const pipelineStartedRef = useRef(false)
  const getEffectiveProjectId = (): number | null => props.editProjectId || projectIdRef.current

  const checkMediaExists = useCallback(async (url: string): Promise<boolean> => {
    try {
      const res = await fetch(url, { method: 'HEAD' })
      return res.ok
    } catch {
      return false
    }
  }, [])

  const scrubMissingMedia = useCallback(async (input: {
    scenes: SceneData[]
    finalVideo: string
    finalPreview: string
  }): Promise<void> => {
    type ShotClear = {
      firstFrame?: boolean
      lastFrame?: boolean
      video?: boolean
      videoPreview?: boolean
    }
    const shotClears = new Map<string, ShotClear>()
    const sceneCompositedClears = new Set<number>()
    let clearFinalVideo = false
    let clearFinalPreview = false

    const exists = (url: string) => checkMediaExists(url).then(ok => ok)

    const tasks: Promise<void>[] = []
    const setShotClear = (si: number, shi: number, patch: ShotClear) => {
      const key = `${si}:${shi}`
      const cur = shotClears.get(key) || {}
      shotClears.set(key, { ...cur, ...patch })
    }

    input.scenes.forEach((sc, si) => {
      sc.shots.forEach((sh, shi) => {
        if (sh.firstFrame && sh.firstFrame.startsWith(BASE)) {
          tasks.push(exists(sh.firstFrame).then(ok => { if (!ok) setShotClear(si, shi, { firstFrame: true }) }))
        }
        if (sh.lastFrame && sh.lastFrame.startsWith(BASE)) {
          tasks.push(exists(sh.lastFrame).then(ok => { if (!ok) setShotClear(si, shi, { lastFrame: true }) }))
        }
        if (sh.video && sh.video.startsWith(BASE)) {
          tasks.push(exists(sh.video).then(ok => { if (!ok) setShotClear(si, shi, { video: true }) }))
        }
        if (sh.videoPreview && sh.videoPreview.startsWith(BASE)) {
          tasks.push(exists(sh.videoPreview).then(ok => { if (!ok) setShotClear(si, shi, { videoPreview: true }) }))
        }
      })
      if (sc.compositedVideo && sc.compositedVideo.startsWith(BASE)) {
        tasks.push(exists(sc.compositedVideo).then(ok => { if (!ok) sceneCompositedClears.add(si) }))
      }
      if (sc.compositedPreview && sc.compositedPreview.startsWith(BASE)) {
        tasks.push(exists(sc.compositedPreview).then(ok => { if (!ok) sceneCompositedClears.add(si) }))
      }
    })

    if (input.finalVideo && input.finalVideo.startsWith(BASE)) {
      tasks.push(exists(input.finalVideo).then(ok => { if (!ok) clearFinalVideo = true }))
    }
    if (input.finalPreview && input.finalPreview.startsWith(BASE)) {
      tasks.push(exists(input.finalPreview).then(ok => { if (!ok) clearFinalPreview = true }))
    }

    await Promise.all(tasks)

    if (shotClears.size || sceneCompositedClears.size) {
      setScenes(prev => prev.map((scene, siIndex) => {
        let mutated = scene
        if (sceneCompositedClears.has(siIndex)) {
          mutated = { ...mutated, compositedVideo: '', compositedPreview: '' }
        }
        let shots = mutated.shots
        let shotsChanged = false
        scene.shots.forEach((_shot, shiIndex) => {
          const patch = shotClears.get(`${siIndex}:${shiIndex}`)
          if (!patch) return
          if (!shotsChanged) {
            shots = shots.slice()
            shotsChanged = true
          }
          shots[shiIndex] = {
            ...shots[shiIndex],
            ...(patch.firstFrame ? { firstFrame: '', firstFrameStatus: 'waiting' as const } : {}),
            ...(patch.lastFrame ? { lastFrame: '', lastFrameStatus: 'waiting' as const } : {}),
            ...(patch.video ? { video: '', videoStatus: 'waiting' as const } : {}),
            ...(patch.videoPreview ? { videoPreview: '' } : {}),
          }
        })
        return shotsChanged ? { ...mutated, shots } : mutated
      }))
    }
    if (clearFinalVideo) setFinalVideo('')
    if (clearFinalPreview) setFinalPreview('')
  }, [checkMediaExists])

  const handlePipelineEvent = useCallback((event: any) => {
    try {
      if (event.type === 'portrait_image_status') {
      const { identifier, view, status: imgStatus, image_url } = event
      // Try to process immediately. If characters aren't populated yet,
      // or there are already pending events, queue to avoid race with getProject replay.
      setCharacters(prev => {
        if (!prev || prev.length === 0 || !prev.find(c => c.name === identifier) || pendingPortraitEventsRef.current.length > 0) {
          pendingPortraitEventsRef.current.push({ identifier, view, status: imgStatus, image_url })
          return prev
        }
        return prev.map(c => {
          if (c.name !== identifier) return c
          const viewKey = view as 'front' | 'side' | 'back'
          const currentStatus = c.portraitStatus?.[viewKey]

          if (imgStatus === 'waiting' && currentStatus && currentStatus !== 'waiting') {
            return c
          }

          // generated 状态必须有 image_url 才生效，否则保持原状
          if (imgStatus === 'generated' && !image_url) {
            return c
          }

          const isWaiting = !currentStatus || currentStatus === 'waiting'

          const newStatus = { ...c.portraitStatus } as Record<string, any>
          const effectiveStatus = (isWaiting && imgStatus === 'waiting') ? 'generating' : imgStatus
          newStatus[viewKey] = effectiveStatus as 'waiting' | 'generating' | 'generated' | 'error'

          const newPortraits = { ...c.portraits }
          if (image_url) {
            newPortraits[viewKey] = image_url.startsWith(BASE) ? image_url : `${BASE}${image_url}`
          }
          
          return { ...c, portraits: newPortraits, portraitStatus: newStatus }
        })
      })
    } else if (event.type === 'storyboard_scene_ready') {
      const { scene_idx, scene } = event
      setScenes(prev => {
        const next = [...prev]
        while (next.length <= scene_idx) {
          next.push({ title: '', content: '', shots: [], compositedVideo: '', compositedPreview: '' })
        }
        next[scene_idx] = {
          title: scene.title || '',
          content: scene.content || '',
          shots: (scene.shots || []).map((s: any) => ({
            title: (s.visual_desc || '').slice(0, 50),
            visualDescription: s.visual_desc || '',
            voiceDescription: s.audio_desc || '',
            firstFrame: '',
            lastFrame: '',
            video: '',
            variationType: s.variation_type || 'small',
            firstFramePrompt: s.ff_desc || '',
            lastFramePrompt: s.lf_desc || '',
            firstFrameStatus: 'waiting' as const,
            lastFrameStatus: 'waiting' as const,
            videoStatus: 'waiting' as const,
          })),
          compositedVideo: '',
          compositedPreview: '',
        }
        return next
      })
    } else if (event.type === 'shot_frame_ready') {
      const { scene_idx, shot_idx, frame_type, image_url } = event
      setScenes(prev => {
        if (scene_idx >= prev.length || shot_idx >= prev[scene_idx].shots.length) return prev
        const next = [...prev]
        const scene = { ...next[scene_idx] }
        const shots = [...scene.shots]
        const shot = { ...shots[shot_idx] }
        if (!image_url) {
          // Empty image_url means the frame is being generated (status update only)
          if (frame_type === 'start_frame') {
            shot.firstFrameStatus = 'generating' as const
          } else if (frame_type === 'end_frame') {
            shot.lastFrameStatus = 'generating' as const
          }
        } else {
          const url = image_url.startsWith(BASE) || image_url.startsWith('http://') || image_url.startsWith('https://')
            ? image_url : `${BASE}${image_url}`
          if (frame_type === 'start_frame') {
            shot.firstFrame = url
            shot.firstFrameStatus = 'generated' as const
          } else if (frame_type === 'end_frame') {
            shot.lastFrame = url
            shot.lastFrameStatus = 'generated' as const
          }
        }
        shots[shot_idx] = shot
        scene.shots = shots
        next[scene_idx] = scene
        return next
      })
    } else if (event.type === 'shot_video_ready') {
      const { scene_idx, shot_idx, video_url, video_preview_url } = event
      setScenes(prev => {
        if (scene_idx >= prev.length || shot_idx >= prev[scene_idx].shots.length) return prev
        const next = [...prev]
        const scene = { ...next[scene_idx] }
        const shots = [...scene.shots]
        const shot = { ...shots[shot_idx] }
        if (!video_url) {
          shot.videoStatus = 'generating' as const
        } else {
          shot.video = video_url.startsWith(BASE) ? video_url : `${BASE}${video_url}`
          shot.videoStatus = 'generated' as const
          if (video_preview_url) {
            shot.videoPreview = video_preview_url.startsWith(BASE) ? video_preview_url : `${BASE}${video_preview_url}`
          }
        }
        shots[shot_idx] = shot
        scene.shots = shots
        next[scene_idx] = scene
        return next
      })
    } else if (event.type === 'scene_composite_ready') {
      const { scene_idx, composited_video, composited_preview } = event
      setScenes(prev => {
        if (scene_idx >= prev.length) return prev
        const next = [...prev]
        next[scene_idx] = {
          ...next[scene_idx],
          compositedVideo: composited_video ? (composited_video.startsWith(BASE) ? composited_video : `${BASE}${composited_video}`) : '',
          compositedPreview: composited_preview ? (composited_preview.startsWith(BASE) ? composited_preview : `${BASE}${composited_preview}`) : '',
        }
        return next
      })
    } else if (event.type === 'final_video_ready') {
      const { final_video_url, final_preview_url } = event
      if (final_video_url) {
        setFinalVideo(final_video_url.startsWith(BASE) ? final_video_url : `${BASE}${final_video_url}`)
      }
      if (final_preview_url) {
        setFinalPreview(final_preview_url.startsWith(BASE) ? final_preview_url : `${BASE}${final_preview_url}`)
      }
    }
  } catch (e) {
    console.error('[NewProject] handlePipelineEvent crashed:', e, 'event:', event)
  }
  }, [])

  const pipeline = usePipelineSSE(getEffectiveProjectId(), handlePipelineEvent)
  const pipelineRunning = pipeline.status?.pipeline_status === 'running'

  // Set API keys for pipeline use
  useEffect(() => {
    window.__pipelineApiKeys = {
      chatApiKey: props.chatApiKey,
      chatBaseUrl: props.chatBaseUrl,
      imageApiKey: props.imageApiKey,
      imageBaseUrl: props.imageBaseUrl,
      videoApiKey: props.videoApiKey,
      videoBaseUrl: props.videoBaseUrl,
      chatRateLimitMin: props.chatRateLimitMin,
      chatRateLimitDay: props.chatRateLimitDay,
      imageRateLimitMin: props.imageRateLimitMin,
      imageRateLimitDay: props.imageRateLimitDay,
      videoRateLimitMin: props.videoRateLimitMin,
      videoRateLimitDay: props.videoRateLimitDay,
    }
  }, [props.chatApiKey, props.chatBaseUrl, props.imageApiKey, props.imageBaseUrl, props.videoApiKey, props.videoBaseUrl,
      props.chatRateLimitMin, props.chatRateLimitDay, props.imageRateLimitMin, props.imageRateLimitDay,
      props.videoRateLimitMin, props.videoRateLimitDay])

  // Refresh project data when pipeline steps complete or fail
  // (data may have been committed to DB before the error occurred)
  const lastCompletedStepsRef = useRef<Set<string>>(new Set())
  const lastRunningStepsRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    const pid = getEffectiveProjectId()
    if (!pid || !pipeline.status) return
    const steps = pipeline.status.steps || {}
    for (const [stepKey, stepState] of Object.entries(steps)) {
      const terminalStatus = stepState.status === 'completed' || stepState.status === 'failed'
      if (terminalStatus && !lastCompletedStepsRef.current.has(stepKey)) {
        lastCompletedStepsRef.current.add(stepKey)
        lastRunningStepsRef.current.delete(stepKey)
        getProject(pid).then(p => {
          if (p.story && p.story !== output) setOutput(p.story)
          if (p.characters?.length) {
            setCharacters(prev => {
              const prevMap = new Map(prev.map(c => [c.name, c]))
              const pending = pendingPortraitEventsRef.current
              pendingPortraitEventsRef.current = []
              return p.characters.map((c: any) => {
                const name = c.name || c.identifier || ''
                const existing = prevMap.get(name)
                const portraitUrl = (url: unknown) => {
                  if (!url || typeof url !== 'string') return ''
                  return url.startsWith(BASE) || url.startsWith('http://') || url.startsWith('https://')
                    ? url
                    : `${BASE}${url}`
                }
                const backPortraits = {
                  front: portraitUrl(c.front_url),
                  side: portraitUrl(c.side_url),
                  back: portraitUrl(c.back_url),
                }
                const hasBackPortraits = !!(backPortraits.front || backPortraits.side || backPortraits.back)

                // Start from existing or waiting status, then apply pending events
                let status = hasBackPortraits
                  ? { front: backPortraits.front ? 'generated' as const : 'waiting' as const, side: backPortraits.side ? 'generated' as const : 'waiting' as const, back: backPortraits.back ? 'generated' as const : 'waiting' as const }
                  : (existing?.portraitStatus || { front: 'waiting' as const, side: 'waiting' as const, back: 'waiting' as const })

                const portraits = hasBackPortraits
                  ? backPortraits
                  : (existing?.portraits || { front: '', side: '', back: '' })

                // Replay any pending portrait events that arrived before characters were populated
                for (const pe of pending) {
                  if (name !== pe.identifier) continue
                  const vk = pe.view as 'front' | 'side' | 'back'
                  if (pe.status === 'waiting' && status[vk] !== 'waiting') continue
                  // generated 状态必须有 image_url 才生效
                  if (pe.status === 'generated' && !pe.image_url) continue
                  status = { ...status, [vk]: (pe.status === 'waiting' ? 'generating' : pe.status) as 'waiting' | 'generating' | 'generated' | 'error' }
                  if (pe.image_url) {
                    portraits[vk] = pe.image_url.startsWith(BASE) ? pe.image_url : `${BASE}${pe.image_url}`
                  }
                }

                return {
                  name,
                  staticFeatures: c.appearance || c.staticFeatures || '',
                  dynamicFeatures: c.attire || c.dynamicFeatures || '',
                  portraits,
                  sourceUrl: c.sourceUrl || existing?.sourceUrl || '',
                  portraitStatus: status,
                }
              })
            })
          }
          if (p.scenes?.length) {
            const hydratedScenes = p.scenes.map((s: any) => ({
              title: s.title || '',
              content: s.content || '',
              shots: (s.shots || []).map((shot: any) => ({
                title: shot.title || '',
                visualDescription: shot.visualDescription || '',
                voiceDescription: shot.voiceDescription || '',
                motionDescription: shot.motionDescription || '',
                variationType: shot.variationType || 'small',
                firstFrame: shot.firstFrame ? (
                  shot.firstFrame.startsWith(BASE)
                  || shot.firstFrame.startsWith('http://')
                  || shot.firstFrame.startsWith('https://')
                ) ? shot.firstFrame : `${BASE}${shot.firstFrame}` : '',
                lastFrame: shot.lastFrame ? (
                  shot.lastFrame.startsWith(BASE)
                  || shot.lastFrame.startsWith('http://')
                  || shot.lastFrame.startsWith('https://')
                ) ? shot.lastFrame : `${BASE}${shot.lastFrame}` : '',
                video: shot.video ? (shot.video.startsWith(BASE) ? shot.video : `${BASE}${shot.video}`) : '',
                videoPreview: shot.videoPreview ? (shot.videoPreview.startsWith(BASE) ? shot.videoPreview : `${BASE}${shot.videoPreview}`) : '',
                firstFrameStatus: shot.firstFrame ? 'generated' as const : 'waiting' as const,
                lastFrameStatus: shot.lastFrame ? 'generated' as const : 'waiting' as const,
                videoStatus: shot.video ? 'generated' as const : 'waiting' as const,
              })),
              compositedVideo: s.compositedVideo || '',
              compositedPreview: s.compositedPreview || '',
            }))
            const finalVideoUrl = p.final_video ? (p.final_video.startsWith(BASE) ? p.final_video : `${BASE}${p.final_video}`) : ''
            const finalPreviewUrl = p.final_preview ? (p.final_preview.startsWith(BASE) ? p.final_preview : `${BASE}${p.final_preview}`) : ''
            setScenes(hydratedScenes)
            if (finalVideoUrl) setFinalVideo(finalVideoUrl)
            if (finalPreviewUrl) setFinalPreview(finalPreviewUrl)
            scrubMissingMedia({
              scenes: hydratedScenes,
              finalVideo: finalVideoUrl,
              finalPreview: finalPreviewUrl,
            })
          }
        }).catch(() => {})
      }
      if (stepKey === 'portraits' && stepState.status === 'running' && !lastRunningStepsRef.current.has('portraits')) {
        lastRunningStepsRef.current.add('portraits')
      }
    }
  }, [pipeline.status])

  // When shot_frames step is running, set pending shots to "generating"
  const lastShotFramesStatusRef = useRef<string>('')
  useEffect(() => {
    if (!pipeline.status) return
    const sfStep = pipeline.status.steps?.shot_frames
    const status = sfStep?.status || ''
    if (status === 'running' && lastShotFramesStatusRef.current !== 'running') {
      lastShotFramesStatusRef.current = 'running'
      setScenes(prev => prev.map(scene => ({
        ...scene,
        shots: scene.shots.map(shot => ({
          ...shot,
          firstFrameStatus: shot.firstFrameStatus || (shot.firstFrame ? 'generated' as const : 'generating' as const),
          lastFrameStatus: shot.lastFrameStatus || (shot.lastFrame ? 'generated' as const : 'generating' as const),
          videoStatus: shot.videoStatus || (shot.video ? 'generated' as const : 'generating' as const),
        })),
      })))
    } else if (status !== 'running') {
      lastShotFramesStatusRef.current = status
    }
  }, [pipeline.status?.steps?.shot_frames?.status])

  // Update portrait placeholder statuses based on pipeline progress phase
  const lastPortraitMsgRef = useRef('')
  useEffect(() => {
    if (!pipeline.status) return
    const msg = pipeline.status.pipeline_message || ''
    const portraitRunning = pipeline.status.steps?.portraits?.status === 'running'
    if (!portraitRunning || msg === lastPortraitMsgRef.current) return
    lastPortraitMsgRef.current = msg

    // Parse "正在生成 <character> (<phase>)肖像..." → identify the active character and phase
    // If the message doesn't match, don't touch existing statuses (SSE events handle them)
    const m = msg.match(/正在生成 (.+?) (正面|侧面|背面)肖像/)
    if (!m) return
    const ident = m[1]
    const phase = m[2]

    // Only update the matched character by fuzzy name lookup;
    // never reset other characters' statuses (handlePortraitImageEvent owns those).
    setCharacters(prev => {
      const matched = prev.find(c => ident.includes(c.name) || c.name.includes(ident))
      if (!matched) return prev

      const targetView = phase === '正面' ? 'front' : phase === '侧面' ? 'side' : 'back'
      return prev.map(c => {
        if (c.name !== matched.name) return c
        const newStatus = {
          front: (c.portraitStatus?.front === 'generated' || !!c.portraits?.front) ? 'generated' as const : (c.portraitStatus?.front === 'generating') ? 'generating' as const : 'waiting' as const,
          side: (c.portraitStatus?.side === 'generated' || !!c.portraits?.side) ? 'generated' as const : (c.portraitStatus?.side === 'generating') ? 'generating' as const : 'waiting' as const,
          back: (c.portraitStatus?.back === 'generated' || !!c.portraits?.back) ? 'generated' as const : (c.portraitStatus?.back === 'generating') ? 'generating' as const : 'waiting' as const,
        }
        newStatus[targetView] = c.portraits?.[targetView] ? 'generated' as const : 'generating' as const
        return { ...c, portraitStatus: newStatus }
      })
    })
  }, [pipeline.status?.pipeline_message, pipeline.status?.steps?.portraits?.status])

  const saveProjectData = async (extra: Record<string, any>) => {
    const pid = getEffectiveProjectId()
    if (!pid) return
    await updateProject(pid, extra)
  }

  // 编辑模式：加载已有项目数据
  useEffect(() => {
    if (!props.editProjectId) return
    setLoadingEdit(true)
    getProject(props.editProjectId).then(p => {
      setIdea(p.idea || '')
      setStyle(p.style || 'realistic')
      setSize(p.size || '16:9')
      setResolution(p.resolution || '720p')
      setFrameRate(String(p.frame_rate || '24'))
      setDuration(String(p.duration || '10'))
      setLanguage(p.language || 'zh')
      setChatModel(p.chat_model || '')
      setImageModel(p.image_model || '')
      setVideoModel(p.video_model || '')
      if (p.story) setOutput(p.story)
      if (p.characters?.length) {
        setCharacters(p.characters.map((c: any) => ({
          name: c.name || c.identifier || '',
          staticFeatures: c.appearance || c.staticFeatures || '',
          dynamicFeatures: c.attire || c.dynamicFeatures || '',
          portraits: {
            front: c.portraits?.front || '',
            side: c.portraits?.side || '',
            back: c.portraits?.back || '',
          },
          sourceUrl: c.sourceUrl || '',
          portraitStatus: {
            front: c.portraits?.front ? 'generated' as const : 'waiting' as const,
            side: c.portraits?.side ? 'generated' as const : 'waiting' as const,
            back: c.portraits?.back ? 'generated' as const : 'waiting' as const,
          },
          portraitDescriptions: c.portraitDescriptions || makePortraitDescriptions(c.name || c.identifier || ''),
        })) as CharacterData[])
        setPortraitsReady(true)
      }
      if (p.scenes?.length) {
        setScenes(p.scenes.map((s: any) => ({
          title: s.title || '',
          content: s.content || '',
          shots: (s.shots || []).map((shot: any) => ({
            title: shot.title || '',
            visualDescription: shot.visualDescription || '',
            voiceDescription: shot.voiceDescription || '',
            motionDescription: shot.motionDescription || '',
            variationType: shot.variationType || 'small',
            firstFrame: shot.firstFrame ? (
              shot.firstFrame.startsWith(BASE)
              || shot.firstFrame.startsWith('http://')
              || shot.firstFrame.startsWith('https://')
            ) ? shot.firstFrame : `${BASE}${shot.firstFrame}` : '',
            lastFrame: shot.lastFrame ? (
              shot.lastFrame.startsWith(BASE)
              || shot.lastFrame.startsWith('http://')
              || shot.lastFrame.startsWith('https://')
            ) ? shot.lastFrame : `${BASE}${shot.lastFrame}` : '',
            video: shot.video ? (shot.video.startsWith(BASE) ? shot.video : `${BASE}${shot.video}`) : '',
            videoPreview: shot.videoPreview ? (shot.videoPreview.startsWith(BASE) ? shot.videoPreview : `${BASE}${shot.videoPreview}`) : '',
            firstFrameStatus: shot.firstFrame ? 'generated' as const : 'waiting' as const,
            lastFrameStatus: shot.lastFrame ? 'generated' as const : 'waiting' as const,
            videoStatus: shot.video ? 'generated' as const : 'waiting' as const,
          })),
          compositedVideo: s.compositedVideo || '',
          compositedPreview: s.compositedPreview || '',
        })))
        if (p.final_video) {
          setFinalVideo(p.final_video.startsWith(BASE) ? p.final_video : `${BASE}${p.final_video}`)
        }
        if (p.final_preview) {
          setFinalPreview(p.final_preview.startsWith(BASE) ? p.final_preview : `${BASE}${p.final_preview}`)
        }
        setStage('storyboard')
      } else if (p.characters?.length) {
        setStage('characters')
      } else if (p.story) {
        setStage('story')
      }
      setLoadingEdit(false)
    }).catch(() => {
      setLoadingEdit(false)
    })
  }, [props.editProjectId])

  // When user navigates from an existing project back to blank creation, reset all state
  useEffect(() => {
    if (props.editProjectId !== undefined) return
    setCharacters([])
    setScenes([])
    setOutput(null)
    setError(null)
    setProjectId(null)
    projectIdRef.current = null
    setStage('new')
    setCreating(false)
    pipelineStartedRef.current = false
  }, [props.editProjectId])

  useEffect(() => {
    if (!creating) return
    const id = setInterval(() => setDotCount(n => (n + 1) % 4), 2000)
    return () => clearInterval(id)
  }, [creating])

  useEffect(() => {
    if (!creating) setDotCount(0)
  }, [creating])

  const showPlaceholder = !pipelineStartedRef.current && stage === 'new' && !output && !error

  const handleCreate = async () => {
    if (!canGenerate) return
    setCharacters([])
    setScenes([])
    setOutput(null)

    setCreating(true)
    try {
      // 1. 首次创建才创建项目
      let pid = getEffectiveProjectId()
      let isNew = false
      if (!pid) {
        const project = await createProject(idea.slice(0, 30) || '未命名项目')
        setProjectId(project.id)
        projectIdRef.current = project.id
        pid = project.id
        isNew = true
      }

      // 2. 保存项目配置到后端（让 pipeline 步骤能从 DB 读取）
      await saveProjectData({
        idea,
        style,
        size,
        resolution,
        frame_rate: parseInt(frameRate) || 24,
        duration: parseInt(duration) || 10,
        language,
        chat_model: chatModel,
        image_model: imageModel,
        video_model: videoModel,
        stage: 'new',
      })

      // 3. 启动 pipeline（后端异步执行，前端通过 SSE 接收进度）
      await pipeline.start()
      pipelineStartedRef.current = true
      setStage('story')

      // 4. Now propagate project ID to parent so it persists in localStorage
      if (isNew) {
        props.onProjectSelected?.(pid)
      }
    } catch (e: any) {
      console.error('启动 pipeline 失败:', e)
      setError(`启动失败: ${e?.message || String(e)}`)
    } finally {
      setCreating(false)
    }
  }

  const handleSave = async () => {
    if (!props.editProjectId) return
    setSaving(true)
    try {
      await updateProject(props.editProjectId, {
        idea,
        style,
        size,
        resolution,
        frame_rate: parseInt(frameRate) || 24,
        duration: parseInt(duration) || 10,
        language,
        chat_model: chatModel,
        image_model: imageModel,
        video_model: videoModel,
        stage,
        story: output,
        characters: characters.map(c => ({
          name: c.name,
          staticFeatures: c.staticFeatures,
          dynamicFeatures: c.dynamicFeatures,
          source: 'script',
          portraits: c.portraits || {},
          sourceUrl: c.sourceUrl || '',
          portraitDescriptions: c.portraitDescriptions || makePortraitDescriptions(c.name),
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
            motionDescription: '',
            variationType: sh.variationType || 'small',
            firstFrame: sh.firstFrame,
            lastFrame: sh.lastFrame,
            video: sh.video,
            videoPreview: sh.videoPreview || '',
          })),
        })),
        finalVideo,
        finalPreview,
      })
    } catch (e: any) {
      console.error('保存失败:', e)
    } finally {
      setSaving(false)
    }
  }

  // 故事大纲就绪后，通过 pipeline SSE 事件自动刷新 UI 卡片
  // 该逻辑已由 pipeline.status 的 useEffect 处理

  const handleRegenerateCharacters = async () => {
    setCreatingCharacter(true)
    try {
      const script = output || idea
      const res = await extractCharacters({
        script,
        model: chatModel,
        api_key: props.chatApiKey,
        base_url: props.chatBaseUrl,
      })
      const waitingStatus: PortraitStatus = { front: 'waiting', side: 'waiting', back: 'waiting' }
      const chars: CharacterData[] = (res.characters || []).map((c: any, i: number) => ({
        name: c.role_name || `角色${i + 1}`,
        staticFeatures: c.appearance || '',
        dynamicFeatures: c.attire || '',
        portraits: {
          front: '',
          side: '',
          back: '',
        },
        portraitStatus: { ...waitingStatus },
      }))
      setCharacters(chars)
      setStage('characters')
      await saveProjectData({
        characters: chars.map(c => ({
          name: c.name,
          staticFeatures: c.staticFeatures,
          dynamicFeatures: c.dynamicFeatures,
          source: 'script',
          portraits: c.portraits || {},
          sourceUrl: c.sourceUrl || '',
          portraitDescriptions: makePortraitDescriptions(c.name),
        })),
        stage: 'characters',
      })
      setCreatingCharacter(false)
      if (chars.length > 0) {
        generatePortraitsForCharacters(chars)
      }
    } catch (e: any) {
      console.error('重新提取角色失败:', e)
      setCreatingCharacter(false)
    }
  }

  const handleRegenerateStoryboard = async () => {
    setRegenerating(true)
    try {
      const charDicts = characters.map(c => ({
        role_name: c.name,
        name: c.name,
        appearance: c.staticFeatures,
        attire: c.dynamicFeatures,
      }))
      const shotLimitReq = DURATION_REQUIREMENTS[duration] || ''

      const sceneShotResults: ShotData[][] = []
      let sceneCursor = 0

      async function processRegenScene(): Promise<void> {
        while (sceneCursor < scenes.length) {
          const i = sceneCursor++
          try {
            const r = await sceneStoryboard({
              scene_content: scenes[i].content,
              characters: charDicts,
              user_requirement: shotLimitReq,
              model: chatModel,
              api_key: props.chatApiKey,
              base_url: props.chatBaseUrl,
              style,
            })

            const shotDescs = (r.shot_descriptions || []) as Array<any>
            const shots: ShotData[] = (r.storyboard || []).map((s: any, si: number) => {
              const desc = shotDescs[si] || {}
              return {
                title: s.title || `分镜${si + 1}`,
                visualDescription: desc.visual_desc || '',
                voiceDescription: desc.audio_desc || '',
                firstFrame: shotPlaceholderImg(`S${i + 1}-镜头${si + 1} 初始`),
                lastFrame: shotPlaceholderImg(`S${i + 1}-镜头${si + 1} 末尾`),
                video: '',
                variationType: desc.variation_type || 'small',
                firstFramePrompt: desc.ff_desc || '',
                lastFramePrompt: desc.lf_desc || '',
                firstFrameStatus: 'generating' as const,
                lastFrameStatus: 'generating' as const,
                videoStatus: 'generating' as const,
              }
            })

            setScenes(prev => {
              const next = [...prev]
              next[i] = { ...next[i], shots }
              return next
            })
            sceneShotResults[i] = shots

            // Use ShotFrameOrchestrator to generate all frames for this scene
            const cameraTree = (r.camera_tree || []) as Array<Record<string, any>>
            if (cameraTree.length > 0) {
              const pid = getEffectiveProjectId()
              const resolutionStr = getSizeString(size, props.sizeMap)

              // Build portrait registry from current characters
              const registry: Record<string, any> = {}
              for (const ch of characters) {
                const entry: Record<string, any> = {}
                for (const view of ['front', 'side', 'back'] as const) {
                  const url = ch.portraits[view]
                  if (url) {
                    entry[view] = {
                      path: url.startsWith(BASE) ? url.slice(BASE.length) : url,
                      description: makePortraitDescriptions(ch.name)[view],
                    }
                  }
                }
                if (Object.keys(entry).length > 0) registry[ch.name] = entry
              }

              try {
                const result = await generateShotFrames({
                  camera_tree: cameraTree,
                  shot_descriptions: shotDescs,
                  characters: charDicts,
                  character_portraits_registry: registry,
                  model: imageModel,
                  chat_model: chatModel,
                  api_key: props.imageApiKey,
                  base_url: props.imageBaseUrl,
                  project_id: pid || 0,
                  size: resolutionStr,
                  scene_idx: i,
                })

                for (const frame of result.frames) {
                  const idxInShots = shotDescs.findIndex((d: any) => d.idx === frame.shot_idx)
                  if (idxInShots < 0) continue

                  const url = `${BASE}${frame.url}`
                  setScenes(prev => {
                    const next = [...prev]
                    const updatedShots = [...next[i].shots]
                    if (frame.frame_type === 'first_frame') {
                      updatedShots[idxInShots] = { ...updatedShots[idxInShots], firstFrame: url }
                    } else if (frame.frame_type === 'last_frame') {
                      updatedShots[idxInShots] = { ...updatedShots[idxInShots], lastFrame: url }
                    }
                    next[i] = { ...next[i], shots: updatedShots }
                    return next
                  })
                  if (sceneShotResults[i]) {
                    sceneShotResults[i] = sceneShotResults[i].map((sh, si) =>
                      si === idxInShots
                        ? { ...sh, [frame.frame_type === 'first_frame' ? 'firstFrame' : 'lastFrame']: url }
                        : sh
                    )
                  }
                }
              } catch (e) {
                console.error(`场景 ${i + 1} 镜头帧生成失败:`, e)
              }
            }
          } catch (e: any) {
            console.error(`场景 ${i + 1} 重新生成分镜失败:`, e)
            sceneShotResults[i] = []
          }
        }
      }

      await Promise.all(Array(2).fill(null).map(processRegenScene))

      const allDone = scenes.length > 0 && sceneShotResults.every(shots => shots && shots.length > 0)
      if (allDone) {
        setStage('storyboard')
        await saveProjectData({
          stage: 'storyboard',
          scenes: scenes.map((s, i) => ({
            title: s.title,
            content: s.content,
            slugline: '',
            environmentDesc: '',
            script: '',
            compositedVideo: s.compositedVideo || '',
            compositedPreview: s.compositedPreview || '',
            shots: (sceneShotResults[i] || []).map(sh => ({
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
        })
      }
    } catch (e: any) {
      console.error('重新生成分镜失败:', e)
    } finally {
      setRegenerating(false)
    }
  }

  const generatePortraitsForCharacters = async (chars: CharacterData[]): Promise<void> => {
    try {
      const pid = getEffectiveProjectId()!

      setCharacters(prev => prev.map(c => ({
        ...c,
        portraitStatus: { front: 'generating' as const, side: 'waiting' as const, back: 'waiting' as const },
      })))

      const style_ = style
      const imageModel_ = imageModel
      const imageApiKey_ = props.imageApiKey
      const imageBaseUrl_ = props.imageBaseUrl

      // Process each character independently in parallel with retry
      // For each character: front → (immediately update UI) → side+back
      const updatedCharsMap = new Map<string, CharacterData>()
      const MAX_RETRIES = 50
      await Promise.all(chars.map(async (char) => {
        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
          try {
            // Step 1: Generate front portrait
            const frontRes = await generatePortraits({
              characters: [{
                role_name: char.name,
                appearance: char.staticFeatures,
                attire: char.dynamicFeatures,
              }],
              view: 'front',
              style: style_,
              model: imageModel_,
              api_key: imageApiKey_,
              base_url: imageBaseUrl_,
              project_id: pid,
            })

            const frontData = frontRes.portraits[char.name]
            if (!frontData?.front) {
              throw new Error('正面肖像返回为空')
            }
            const frontUrl = `${BASE}${frontData.front}`
            const sourceUrl = frontData.source_url || ''
            // Show front immediately, trigger side+back generation concurrently
            setCharacters(prev => prev.map(c =>
              c.name === char.name ? {
                ...c,
                portraits: { ...c.portraits, front: frontUrl },
                sourceUrl,
                portraitStatus: { front: 'generated' as const, side: 'generating' as const, back: 'generating' as const },
              } : c
            ))

            // Step 2: Generate side and back portraits concurrently
            const [sideRes, backRes] = await Promise.all([
              generatePortraits({
                characters: [{ role_name: char.name, front_image: sourceUrl }],
                view: 'side',
                style: style_,
                model: imageModel_,
                api_key: imageApiKey_,
                base_url: imageBaseUrl_,
                project_id: pid,
              }),
              generatePortraits({
                characters: [{ role_name: char.name, front_image: sourceUrl }],
                view: 'back',
                style: style_,
                model: imageModel_,
                api_key: imageApiKey_,
                base_url: imageBaseUrl_,
                project_id: pid,
              }),
            ])

            const sideData = sideRes.portraits[char.name]
            const backData = backRes.portraits[char.name]
            if (!sideData?.side) throw new Error('侧面肖像返回为空')
            if (!backData?.back) throw new Error('背面肖像返回为空')
            const sideUrl = `${BASE}${sideData.side}`
            const backUrl = `${BASE}${backData.back}`

            setCharacters(prev => prev.map(c =>
              c.name === char.name ? {
                ...c,
                portraits: { ...c.portraits, front: frontUrl, side: sideUrl, back: backUrl },
                portraitStatus: { front: 'generated' as const, side: 'generated' as const, back: 'generated' as const },
              } : c
            ))
            updatedCharsMap.set(char.name, {
              ...char,
              portraits: { front: frontUrl, side: sideUrl, back: backUrl },
              portraitStatus: { front: 'generated', side: 'generated', back: 'generated' },
            })
            break // success, exit retry loop
          } catch (e) {
            if (attempt < MAX_RETRIES) {
              console.log(`角色 ${char.name} 肖像第 ${attempt} 次生成失败，等待后重试:`, e)
              await new Promise(r => setTimeout(r, 2000))
            } else {
              console.error(`角色 ${char.name} 肖像生成失败（已重试 ${MAX_RETRIES} 次）:`, e)
              setCharacters(prev => prev.map(c =>
                c.name === char.name ? {
                  ...c,
                  portraitStatus: { front: 'error' as const, side: 'error' as const, back: 'error' as const },
                } : c
              ))
              updatedCharsMap.set(char.name, {
                ...char,
                portraitStatus: { front: 'error', side: 'error', back: 'error' },
              })
            }
          }
        }
      }))

      // If any character still has error status after retries, abort
      for (const ch of chars) {
        const updated = updatedCharsMap.get(ch.name)
        if (!updated || updated.portraitStatus?.front !== 'generated') {
          throw new Error(`角色 ${ch.name} 肖像生成失败`)
        }
      }

      // 保存肖像数据到后端
      const pid2 = getEffectiveProjectId()
      if (pid2 && updatedCharsMap.size > 0) {
        const savedChars = chars.map(c => {
          const updated = updatedCharsMap.get(c.name)
          return {
            name: c.name,
            staticFeatures: c.staticFeatures,
            dynamicFeatures: c.dynamicFeatures,
            source: 'script' as const,
            portraits: {
              front: updated?.portraits?.front || '',
              side: updated?.portraits?.side || '',
              back: updated?.portraits?.back || '',
            },
            sourceUrl: updated?.sourceUrl || c.sourceUrl || '',
            portraitDescriptions: makePortraitDescriptions(c.name),
          }
        })
        await saveProjectData({
          characters: savedChars,
        }).catch(e => console.error('保存肖像数据失败:', e))
      }

      // Build portrait registry for ShotFrameOrchestrator
      const registry: Record<string, any> = {}
      updatedCharsMap.forEach((ch, name) => {
        const entry: Record<string, any> = {}
        for (const view of ['front', 'side', 'back'] as const) {
          const url = ch.portraits[view]
          if (url) {
            entry[view] = {
              path: url.startsWith(BASE) ? url.slice(BASE.length) : url,
              description: makePortraitDescriptions(name)[view],
            }
          }
        }
        if (Object.keys(entry).length > 0) registry[name] = entry
      })
      portraitRegistryRef.current = registry
    } catch (e: any) {
      console.error('生成角色肖像失败:', e)
      setCharacters(prev => prev.map(c => ({
        ...c,
        portraitStatus: { front: 'error' as const, side: 'error' as const, back: 'error' as const },
      })))
    }
  }

  const handleCharacterUpdate = (idx: number, data: CharacterData) => {
    setCharacters(prev => prev.map((c, i) => i === idx ? data : c))
  }

  const handleSceneUpdate = (idx: number, data: SceneData) => {
    setScenes(prev => prev.map((s, i) => i === idx ? data : s))
  }

  const handleRefreshFrame = async (sceneIdx: number, shotIdx: number, frameType: 'firstFrame' | 'lastFrame', prompt: string) => {
    const resolutionStr = getSizeString(size, props.sizeMap)
    try {
      const res = await generateFrame({
        prompt,
        size: resolutionStr,
        model: imageModel,
        api_key: props.imageApiKey,
        base_url: props.imageBaseUrl,
      })
      const url = res.url.startsWith(BASE) ? res.url : `${BASE}${res.url}`
      setScenes(prev => {
        const next = [...prev]
        const updatedShots = [...next[sceneIdx].shots]
        updatedShots[shotIdx] = { ...updatedShots[shotIdx], [frameType]: url }
        next[sceneIdx] = { ...next[sceneIdx], shots: updatedShots }
        return next
      })
    } catch (e) {
      console.error(`镜头 ${shotIdx} ${frameType} 重新生成失败:`, e)
    }
  }

  const handleRefreshImage = async (characterIdx: number, view: PortraitView): Promise<string | void> => {
    const char = characters[characterIdx]
    if (!char) return

    if ((view === 'side' || view === 'back') && char.portraitStatus?.front !== 'generated') {
      return '请等正面照片生成后，再重试'
    }

    try {
      const pid = getEffectiveProjectId()!
      if (!pid) return

      const defaultStatus: PortraitStatus = { front: 'waiting', side: 'waiting', back: 'waiting' }

      setCharacters(prev => prev.map((c, i) =>
        i === characterIdx ? { ...c, portraitStatus: { ...(c.portraitStatus || defaultStatus), [view]: 'generating' as const } } : c
      ))

      if (view === 'front') {
        const res = await generatePortraits({
          characters: [{
            role_name: char.name,
            appearance: char.staticFeatures,
            attire: char.dynamicFeatures,
          }],
          view: 'front',
          style,
          model: imageModel,
          api_key: props.imageApiKey,
          base_url: props.imageBaseUrl,
          project_id: pid,
        })
        const p = res.portraits[char.name]
        if (p?.front) {
          const frontUrl = `${BASE}${p.front}`
          setCharacters(prev => prev.map((c, i) =>
            i === characterIdx ? {
              ...c,
              portraits: { ...c.portraits, front: frontUrl },
              sourceUrl: p.source_url || undefined,
              portraitStatus: { ...c.portraitStatus, front: 'generated' as const },
            } : c
          ))
          await saveCharacterPortrait(pid, characterIdx, char.name, char.staticFeatures, char.dynamicFeatures,
            frontUrl, char.portraits?.side || '', char.portraits?.back || '', p.source_url || '')
        }
      } else {
        const sourceUrl = char.sourceUrl || ''
        const res = await generatePortraits({
          characters: [{
            role_name: char.name,
            front_image: sourceUrl,
          }],
          view: view,
          style,
          model: imageModel,
          api_key: props.imageApiKey,
          base_url: props.imageBaseUrl,
          project_id: pid,
        })
        const p = res.portraits[char.name]
        if (p?.[view]) {
          const url = `${BASE}${p[view]}`
          setCharacters(prev => prev.map((c, i) =>
            i === characterIdx ? {
              ...c,
              portraits: { ...c.portraits, [view]: url },
              portraitStatus: { ...c.portraitStatus, [view]: 'generated' as const },
            } : c
          ))
          await saveCharacterPortrait(pid, characterIdx, char.name, char.staticFeatures, char.dynamicFeatures,
            char.portraits?.front || '',
            view === 'side' ? url : char.portraits?.side || '',
            view === 'back' ? url : char.portraits?.back || '',
            sourceUrl)
        }
      }
    } catch (e: any) {
      console.error(`刷新${view}肖像失败:`, e)
      setCharacters(prev => prev.map((c, i) =>
        i === characterIdx ? {
          ...c,
          portraitStatus: { ...c.portraitStatus, [view]: 'error' as const },
        } : c
      ))
    }
  }

  const makePortraitDescriptions = (name: string) => ({
    front: `${name}的正面特写`,
    side: `${name}的侧面特写`,
    back: `${name}的背面特写`,
  })

  const saveCharacterPortrait = async (pid: number, idx: number, name: string, staticFeatures: string, dynamicFeatures: string, front: string, side: string, back: string, sourceUrl: string) => {
    const allChars = characters.map((c, i) => {
      if (i === idx) {
        return {
          name,
          staticFeatures,
          dynamicFeatures,
          source: 'script' as const,
          portraits: { front, side, back },
          sourceUrl,
          portraitDescriptions: makePortraitDescriptions(name),
        }
      }
      return {
        name: c.name,
        staticFeatures: c.staticFeatures,
        dynamicFeatures: c.dynamicFeatures,
        source: 'script' as const,
        portraits: { ...c.portraits },
        sourceUrl: c.sourceUrl || '',
        portraitDescriptions: c.portraitDescriptions || makePortraitDescriptions(c.name),
      }
    })
    await updateProject(pid, { characters: allChars }).catch(e => console.error('保存肖像数据失败:', e))
  }

  return (
    <div className="new-project-page">
      <div className="new-project-layout">
        <aside className="new-project-sidebar">
          <div className="new-project-sidebar-body">
            <div className="new-project-sidebar-header">
              <div className="new-project-sidebar-icon">✦</div>
              <h1 className="new-project-sidebar-title">开启 AI 创作之旅</h1>
            </div>
            <div className="np-model-group">
              <div className="np-model-group-title">选择模型</div>
              <div className="np-section">
              <label className="np-label">语言模型</label>
              <select
                className="np-select"
                value={chatModel}
                onChange={e => setChatModel(e.target.value)}
              >
                {props.chatOptions.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div className="np-section">
              <label className="np-label">图像模型</label>
              <select
                className="np-select"
                value={imageModel}
                onChange={e => setImageModel(e.target.value)}
              >
                {props.imageOptions.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div className="np-section">
              <label className="np-label">视频模型</label>
              <select
                className="np-select"
                value={videoModel}
                onChange={e => setVideoModel(e.target.value)}
              >
                {props.videoOptions.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">创意</div>
               <textarea className="np-idea-input" rows={5} placeholder="创意即影像..." value={idea} onChange={e => setIdea(e.target.value)} />
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">风格</div>
              <div className="np-center-grid">
                {STYLES.map(s => (
                  <button
                    key={s.id}
                    className={`np-size-btn${style === s.id ? ' active' : ''}`}
                    onClick={() => setStyle(s.id)}
                  >
                    <span>{s.label}</span>
                    <span className="np-size-check" />
                  </button>
                ))}
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">生成尺寸</div>
              <div className="np-size-grid">
                {SIZES.map(s => (
                  <button
                    key={s.id}
                    className={`np-size-btn${size === s.id ? ' active' : ''}`}
                    data-aspect={s.id}
                    onClick={() => setSize(s.id)}
                  >
                    <div className="np-size-schema" />
                    <span>{s.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">清晰度</div>
              <div className="np-size-grid">
                {RESOLUTIONS.map(r => (
                  <button
                    key={r.id}
                    className={`np-size-btn${resolution === r.id ? ' active' : ''}`}
                    onClick={() => setResolution(r.id)}
                  >
                    <span>{r.label}</span>
                    <span className="np-size-check" />
                  </button>
                ))}
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">帧率</div>
              <div className="np-size-grid">
                {FRAME_RATES.map(f => (
                  <button
                    key={f.id}
                    className={`np-size-btn${frameRate === f.id ? ' active' : ''}`}
                    onClick={() => setFrameRate(f.id)}
                  >
                    <span>{f.label}</span>
                    <span className="np-size-check" />
                  </button>
                ))}
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">生成时长</div>
              <div className="np-size-grid">
                {DURATIONS.map(d => (
                  <button
                    key={d.id}
                    className={`np-size-btn${duration === d.id ? ' active' : ''}`}
                    onClick={() => setDuration(d.id)}
                  >
                    <span>{d.label}</span>
                    <span className="np-size-check" />
                  </button>
                ))}
              </div>
            </div>
          </div>

          {props.editProjectId && !creating && !pipelineStartedRef.current && pipeline.status?.pipeline_status !== 'running' ? (
            <button className="np-generate-btn" onClick={handleSave} disabled={saving}>
              {saving ? '保存中...' : '💾 保存'}
            </button>
          ) : (
            (() => {
              const ps = pipeline.status?.pipeline_status
              const steps = pipeline.status?.steps || {}
              const stepKeys = Object.keys(steps)
              const allDone = stepKeys.length > 0 && stepKeys.every(k => steps[k]?.status === 'completed')
              const isRunning = ps === 'running'
              const isPaused = ps === 'paused'
              let text: string, onClick: () => void, btnDisabled: boolean
              if (creating) {
                text = '正在创作'; onClick = () => {}; btnDisabled = true
              } else if (isRunning) {
                text = '正在创作'; onClick = () => {}; btnDisabled = true
              } else if (isPaused) {
                text = '继续创作'; onClick = () => pipeline.resume(); btnDisabled = false
              } else if (allDone) {
                text = '重新创作'; onClick = () => { pipelineStartedRef.current = true; pipeline.start(); }; btnDisabled = false
              } else {
                text = '立即创作'; onClick = handleCreate; btnDisabled = !canGenerate
              }
              const spinning = creating || isRunning
              return (
                <button className={`np-generate-btn${spinning ? ' creating' : ''}`} onClick={onClick} disabled={btnDisabled}>
                  {spinning ? <><span className="np-btn-icon">✦</span> 正在创作</> : <><span className="np-btn-icon">✦</span> {text}</>}
                </button>
              )
            })()
          )}

        </aside>

        <main className="new-project-main">
          <div className="npm-header">
            <h2 className="npm-title">创作流程</h2>
          </div>

          <div className="npm-steps">
            {STEPS.map(step => {
              const stepState = pipeline.status?.steps?.[step.stepKey]
              const rawStatus = stepState?.status || 'pending'
              const statusClass = rawStatus === 'completed' ? 'npm-step-completed'
                : rawStatus === 'running' ? 'npm-step-running'
                : rawStatus === 'failed' ? 'npm-step-failed'
                : 'npm-step-pending'
              return (
                <div key={step.num} className={`npm-step ${statusClass}`}>
                  <span className="npm-step-icon">{step.icon}</span>
                  <div className="npm-step-title-sm">
                    {rawStatus === 'running' && <span className="npm-step-dot" />}
                    {step.title}
                  </div>
                  <div className="npm-step-desc-sm">{step.desc}</div>
                </div>
              )
            })}
          </div>

          {showPlaceholder && !creating && (
            <div className="npm-placeholder">
              <div className="npm-placeholder-ring">
                <div className="npm-placeholder-icon">✦</div>
              </div>
              <div className="npm-placeholder-text">快来创作吧</div>
            </div>
          )}

          {(!showPlaceholder || creating) && (
            <div className="npm-card-enter">
            <StoryCard
              content={output || ''}
              loading={(creating || (pipelineStartedRef.current && !output)) || pipeline.status?.steps?.story?.status === 'running'}
              disabled={pipelineRunning}
              onRegenerate={handleCreate}
              onSave={(text) => setOutput(text)}
            />
            </div>
          )}
            {(creatingCharacter || characters.length > 0 || 
              pipeline.status?.steps?.characters?.status === 'running' || 
              pipeline.status?.steps?.portraits?.status === 'running' ||
              (output && characters.length === 0 && pipelineRunning)) && (
            <div className="npm-card-enter">
              <CharacterCard
                characters={characters}
                aspectRatio={size}
                loading={creatingCharacter || (pipelineStartedRef.current && characters.length === 0)}
                statusMessage={characters.length === 0 ? '正在提取角色...' : undefined}
                disabled={pipelineRunning}
                onRegenerate={handleRegenerateCharacters}
                onCharacterUpdate={handleCharacterUpdate}
                onRefreshImage={handleRefreshImage}
              />
            </div>
          )}
          {(scenes.length > 0 || (pipeline.status?.steps?.scene_scripts?.status && pipeline.status?.steps?.scene_scripts?.status !== 'pending')) && (
            <div className="npm-card-enter">
              <SceneScriptsCard
                scenes={scenes}
                loading={pipeline.status?.steps?.scene_scripts?.status === 'running' || scenes.length === 0}
              />
            </div>
          )}
          {(portraitsReady || creatingStoryboard || regenerating || pipeline.status?.steps?.storyboard?.status === 'running' || pipeline.status?.steps?.storyboard?.status === 'completed' || pipeline.status?.steps?.shot_frames?.status === 'running' || pipeline.status?.steps?.shot_frames?.status === 'completed' || scenes.some(s => s.shots.length > 0)) && scenes.length > 0 && (
            <div className="npm-card-enter">
              <ShootingScriptCard
                scenes={scenes}
                loading={pipeline.status?.steps?.storyboard?.status === 'running' || pipeline.status?.steps?.shot_frames?.status === 'running' || creatingStoryboard || regenerating}
                disabled={pipelineRunning}
                onSceneUpdate={handleSceneUpdate}
                onRegenerate={handleRegenerateStoryboard}
                onRefreshFrame={handleRefreshFrame}
                aspectRatio={size}
                finalVideo={finalVideo}
                finalPreview={finalPreview}
              />
            </div>
          )}
          {error && (
            <div className="npm-output npm-error">
              <div className="npm-output-content">{error}</div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

export default NewProject
