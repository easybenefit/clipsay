import { useState, useEffect, useRef, useCallback } from 'react'
import { BASE, createProject, generateStory, extractCharacters, sceneStoryboard, generatePortraits, GeneratePortraitsRequest, generateFrame, generateShotFrames, getProject, updateProject, updateCharacterFeatures, fetchStepData } from './api'
import { usePipelineSSE, EVENT_PROJECT_UPDATED } from './usePipelineSSE'

import StoryCard from './StoryCard'
import CharacterCard from './CharacterCard'
import ShootingScriptCard from './ShootingScriptCard'
import CreativeVideoCard from './CreativeVideoCard'
import SceneScriptsCard from './SceneScriptsCard'
import type { CharacterData, PortraitStatus, PortraitView, PortraitViewStatus } from './CharacterCard'
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
  const [refreshingSceneScripts, setRefreshingSceneScripts] = useState(false)
  const [creatingStoryboard, setCreatingStoryboard] = useState(false)
  const [portraitsReady, setPortraitsReady] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [stepStatuses, setStepStatuses] = useState<Record<string, number> | null>(null)
  const [scenes, setScenes] = useState<SceneData[]>([])
  const [finalVideo, setFinalVideo] = useState('')
  const [finalPreview, setFinalPreview] = useState('')
  const [finalVideoStatus, setFinalVideoStatus] = useState(0)
  const portraitRegistryRef = useRef<Record<string, any>>({})
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

  const refreshProjectData = useCallback(async (pid: number) => {
    const p = await getProject(pid)
    if (p.step_statuses) setStepStatuses(p.step_statuses)
    if (p.story && p.story !== output) setOutput(p.story)
    if (p.characters?.length) {
      setPortraitsReady(true)
      setCharacters(prev => {
        const prevMap = new Map(prev.map(c => [c.name, c]))
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
          const apiStatus = c.portrait_status as Record<string, number> | undefined
          const status: PortraitStatus = apiStatus
            ? {
                front: PORTRAIT_STATUS_MAP[apiStatus.front] || 'waiting' as const,
                side: PORTRAIT_STATUS_MAP[apiStatus.side] || 'waiting' as const,
                back: PORTRAIT_STATUS_MAP[apiStatus.back] || 'waiting' as const,
              }
            : // fallback for old data without portrait_status
              (backPortraits.front || backPortraits.side || backPortraits.back
                ? {
                    front: backPortraits.front ? 'generated' as const : 'waiting' as const,
                    side: backPortraits.side ? 'generated' as const : 'waiting' as const,
                    back: backPortraits.back ? 'generated' as const : 'waiting' as const,
                  }
                : (existing?.portraitStatus || { front: 'waiting' as const, side: 'waiting' as const, back: 'waiting' as const }))
          const portraits: { front: string; side: string; back: string } = apiStatus
            ? backPortraits
            : (backPortraits.front || backPortraits.side || backPortraits.back
                ? backPortraits
                : existing?.portraits || { front: '', side: '', back: '' })
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
      const shotFramesStep = p.step_statuses?.shot_frames ?? 0
      setScenes(prev => {
        const hydratedScenes = p.scenes.map((s: any, si: number) => ({
          title: s.title || '',
          content: s.content || '',
          shots: (s.shots || []).map((shot: any, shi: number) => {
            const prevShot = prev?.[si]?.shots?.[shi]
            const ff = shot.firstFrame ? (
              shot.firstFrame.startsWith(BASE)
              || shot.firstFrame.startsWith('http://')
              || shot.firstFrame.startsWith('https://')
            ) ? shot.firstFrame : `${BASE}${shot.firstFrame}` : ''
            const lf = shot.lastFrame ? (
              shot.lastFrame.startsWith(BASE)
              || shot.lastFrame.startsWith('http://')
              || shot.lastFrame.startsWith('https://')
            ) ? shot.lastFrame : `${BASE}${shot.lastFrame}` : ''
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
                : shotFramesStep === 1
                  ? 'generating' as const
                  : ff
                    ? 'generated' as const
                    : (prevShot?.firstFrameStatus === 'generated' || prevShot?.firstFrameStatus === 'generating'
                      ? prevShot.firstFrameStatus as ImageState
                      : 'waiting' as const),
              lastFrameStatus: efStatus !== 0
                ? (SHOT_STATUS_MAP[efStatus] || 'waiting')
                : shotFramesStep === 1
                  ? 'generating' as const
                  : lf
                    ? 'generated' as const
                    : (prevShot?.lastFrameStatus === 'generated' || prevShot?.lastFrameStatus === 'generating'
                      ? prevShot.lastFrameStatus as ImageState
                      : 'waiting' as const),
              videoStatus: vStatus !== 'pending'
                ? (VIDEO_STATUS_MAP[vStatus] || 'waiting')
                : shotFramesStep === 1
                  ? 'generating' as const
                  : vid
                    ? 'generated' as const
                    : (prevShot?.videoStatus === 'generated' || prevShot?.videoStatus === 'generating'
                      ? prevShot.videoStatus as ImageState
                      : 'waiting' as const),
            }
          }),
          compositedVideo: s.compositedVideo ? (s.compositedVideo.startsWith(BASE) ? s.compositedVideo : `${BASE}${s.compositedVideo}`) : '',
          compositedPreview: s.compositedPreview ? (s.compositedPreview.startsWith(BASE) ? s.compositedPreview : `${BASE}${s.compositedPreview}`) : '',
          compositVideoStatus: s.compositVideoStatus !== undefined ? s.compositVideoStatus : 0,
        }))
        return hydratedScenes
      })
      const finalVideoUrl = p.final_video ? (p.final_video.startsWith(BASE) ? p.final_video : `${BASE}${p.final_video}`) : ''
      const finalPreviewUrl = p.final_preview ? (p.final_preview.startsWith(BASE) ? p.final_preview : `${BASE}${p.final_preview}`) : ''
      if (finalVideoUrl) setFinalVideo(finalVideoUrl)
      if (finalPreviewUrl) setFinalPreview(finalPreviewUrl)
      setFinalVideoStatus(p.finalVideoStatus ?? 0)
      scrubMissingMedia({
        scenes: p.scenes.map((s: any) => ({
          title: s.title || '',
          content: s.content || '',
          shots: (s.shots || []).map((shot: any) => ({
            firstFrame: shot.firstFrame || '',
            lastFrame: shot.lastFrame || '',
            video: shot.video || '',
            videoPreview: shot.videoPreview || '',
          })),
          compositedVideo: s.compositedVideo ? (s.compositedVideo.startsWith(BASE) ? s.compositedVideo : `${BASE}${s.compositedVideo}`) : '',
          compositedPreview: s.compositedPreview ? (s.compositedPreview.startsWith(BASE) ? s.compositedPreview : `${BASE}${s.compositedPreview}`) : '',
        })),
        finalVideo: finalVideoUrl,
        finalPreview: finalPreviewUrl,
      })
    }
  }, [output])

  const refreshStepData = useCallback(async (pid: number, step: string) => {
    try {
      const data = await fetchStepData(pid, step)
      if (!data) return

      if (data.step_statuses) setStepStatuses(data.step_statuses)

      switch (step) {
        case 'story':
          if (data.story !== undefined) setOutput(data.story)
          break

        case 'characters':
        case 'portraits':
          if (data.characters?.length) {
            setPortraitsReady(true)
            setCharacters(data.characters.map((c: any) => {
              const name = c.name || c.identifier || ''
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
              const apiStatus = c.portrait_status as Record<string, number> | undefined
              const status: PortraitStatus = apiStatus
                ? {
                    front: PORTRAIT_STATUS_MAP[apiStatus.front] || 'waiting' as const,
                    side: PORTRAIT_STATUS_MAP[apiStatus.side] || 'waiting' as const,
                    back: PORTRAIT_STATUS_MAP[apiStatus.back] || 'waiting' as const,
                  }
                : {
                    front: backPortraits.front ? 'generated' as const : 'waiting' as const,
                    side: backPortraits.side ? 'generated' as const : 'waiting' as const,
                    back: backPortraits.back ? 'generated' as const : 'waiting' as const,
                  }
              return {
                name,
                staticFeatures: c.appearance || '',
                dynamicFeatures: c.attire || '',
                portraits: backPortraits,
                sourceUrl: c.sourceUrl || '',
                portraitStatus: status,
              }
            }))
          }
          break

        case 'scene_scripts':
          if (data.step_status !== undefined) {
            setStepStatuses(prev => ({ ...prev, scene_scripts: data.step_status }))
          }
          if (data.scenes?.length) {
            setScenes(data.scenes.map((s: any) => ({
              title: s.title || '',
              content: s.content || '',
              shots: (s.shots || []).map((shot: any) => {
                const ff = shot.firstFrame
                  ? (shot.firstFrame.startsWith(BASE) || shot.firstFrame.startsWith('http://') || shot.firstFrame.startsWith('https://')
                    ? shot.firstFrame
                    : `${BASE}${shot.firstFrame}`)
                  : ''
                const lf = shot.lastFrame
                  ? (shot.lastFrame.startsWith(BASE) || shot.lastFrame.startsWith('http://') || shot.lastFrame.startsWith('https://')
                    ? shot.lastFrame
                    : `${BASE}${shot.lastFrame}`)
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
                  firstFrame: ff,
                  lastFrame: lf,
                  video: vid,
                  videoPreview: preview,
                  firstFrameStatus: sfStatus !== 0
                    ? (SHOT_STATUS_MAP[sfStatus] || 'waiting')
                    : ff
                      ? 'generated' as const
                      : 'waiting' as const,
                  lastFrameStatus: efStatus !== 0
                    ? (SHOT_STATUS_MAP[efStatus] || 'waiting')
                    : lf
                      ? 'generated' as const
                      : 'waiting' as const,
                  videoStatus: vStatus !== 'pending'
                    ? (VIDEO_STATUS_MAP[vStatus] || 'waiting')
                    : vid
                      ? 'generated' as const
                      : 'waiting' as const,
                }
              }),
              compositedVideo: s.compositedVideo
                ? (s.compositedVideo.startsWith(BASE) ? s.compositedVideo : `${BASE}${s.compositedVideo}`)
                : '',
              compositedPreview: s.compositedPreview
                ? (s.compositedPreview.startsWith(BASE) ? s.compositedPreview : `${BASE}${s.compositedPreview}`)
                : '',
              compositVideoStatus: s.compositVideoStatus !== undefined ? s.compositVideoStatus : 0,
            })))
          }
          break

        case 'storyboard':
        case 'shot_frames':
        case 'composite_video':
          if (data.scenes?.length) {
            setScenes(data.scenes.map((s: any) => ({
              title: s.title || '',
              content: s.content || '',
              shots: (s.shots || []).map((shot: any) => {
                const ff = shot.firstFrame
                  ? (shot.firstFrame.startsWith(BASE) || shot.firstFrame.startsWith('http://') || shot.firstFrame.startsWith('https://')
                    ? shot.firstFrame
                    : `${BASE}${shot.firstFrame}`)
                  : ''
                const lf = shot.lastFrame
                  ? (shot.lastFrame.startsWith(BASE) || shot.lastFrame.startsWith('http://') || shot.lastFrame.startsWith('https://')
                    ? shot.lastFrame
                    : `${BASE}${shot.lastFrame}`)
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
                  firstFrame: ff,
                  lastFrame: lf,
                  video: vid,
                  videoPreview: preview,
                  firstFrameStatus: sfStatus !== 0
                    ? (SHOT_STATUS_MAP[sfStatus] || 'waiting')
                    : ff
                      ? 'generated' as const
                      : 'waiting' as const,
                  lastFrameStatus: efStatus !== 0
                    ? (SHOT_STATUS_MAP[efStatus] || 'waiting')
                    : lf
                      ? 'generated' as const
                      : 'waiting' as const,
                  videoStatus: vStatus !== 'pending'
                    ? (VIDEO_STATUS_MAP[vStatus] || 'waiting')
                    : vid
                      ? 'generated' as const
                      : 'waiting' as const,
                }
              }),
              compositedVideo: s.compositedVideo
                ? (s.compositedVideo.startsWith(BASE) ? s.compositedVideo : `${BASE}${s.compositedVideo}`)
                : '',
              compositedPreview: s.compositedPreview
                ? (s.compositedPreview.startsWith(BASE) ? s.compositedPreview : `${BASE}${s.compositedPreview}`)
                : '',
              compositVideoStatus: s.compositVideoStatus !== undefined ? s.compositVideoStatus : 0,
            })))
          }
          if (step === 'composite_video') {
            if (data.final_video) {
              setFinalVideo(data.final_video.startsWith(BASE) ? data.final_video : `${BASE}${data.final_video}`)
            }
            if (data.final_preview) {
              setFinalPreview(data.final_preview.startsWith(BASE) ? data.final_preview : `${BASE}${data.final_preview}`)
            }
            setFinalVideoStatus(data.step_statuses?.composite_video ?? 0)
          }
          break
      }
    } catch (e) {
      console.error(`[NewProject] refreshStepData failed for ${step}:`, e)
    }
  }, [])

  const handlePipelineEvent = useCallback((event: any) => {
    try {
      const pid = getEffectiveProjectId()
      if (!pid) return
      if (event.type === 'step_data_ready' && event.step) {
        refreshStepData(pid, event.step)
      } else if (event.type === EVENT_PROJECT_UPDATED) {
        refreshProjectData(pid)
      }
    } catch (e) {
      console.error('[NewProject] handlePipelineEvent crashed:', e, 'event:', event)
    }
  }, [refreshProjectData, refreshStepData])

  const pipeline = usePipelineSSE(getEffectiveProjectId(), handlePipelineEvent)
  const pipelineRunning = pipeline.status?.pipeline_status === 'running'

  const PORTRAIT_STATUS_MAP: Record<number, PortraitViewStatus> = {
    0: 'waiting',
    1: 'generating',
    2: 'generated',
    3: 'error',
  }

  const SHOT_STATUS_MAP: Record<number, ImageState> = {
    0: 'waiting',
    1: 'generating',
    2: 'generated',
    3: 'error',
    4: 'generating',
  }

  const VIDEO_STATUS_MAP: Record<string, ImageState> = {
    'pending': 'waiting',
    'generating': 'generating',
    'completed': 'generated',
    'failed': 'error',
  }

  const STEP_STATUS_MAP: Record<number, string> = {
    0: 'pending',
    1: 'generating',
    2: 'completed',
    3: 'failed',
    4: 'regenerating',
  }

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
        compositVideoStatus: scene.compositVideoStatus || 0,
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

  // Sync finalVideoStatus from composite_video step status (SSE updates)
  useEffect(() => {
    const cvStep = pipeline.status?.steps?.composite_video
    if (!cvStep) return
    if (cvStep.status === 'running') {
      setFinalVideoStatus(1)
    } else if (cvStep.status === 'completed') {
      setFinalVideoStatus(2)
    } else if (cvStep.status === 'failed') {
      setFinalVideoStatus(3)
    }
  }, [pipeline.status?.steps?.composite_video?.status])

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
      if (p.step_statuses) setStepStatuses(p.step_statuses)
      if (p.characters?.length) {
        setCharacters(p.characters.map((c: any) => ({
          name: c.name || c.identifier || '',
          staticFeatures: c.appearance || c.staticFeatures || '',
          dynamicFeatures: c.attire || c.dynamicFeatures || '',
          portraits: {
            front: c.front_url
              ? (c.front_url.startsWith(BASE) || c.front_url.startsWith('http://') || c.front_url.startsWith('https://')
                ? c.front_url
                : `${BASE}${c.front_url}`)
              : '',
            side: c.side_url
              ? (c.side_url.startsWith(BASE) || c.side_url.startsWith('http://') || c.side_url.startsWith('https://')
                ? c.side_url
                : `${BASE}${c.side_url}`)
              : '',
            back: c.back_url
              ? (c.back_url.startsWith(BASE) || c.back_url.startsWith('http://') || c.back_url.startsWith('https://')
                ? c.back_url
                : `${BASE}${c.back_url}`)
              : '',
          },
          sourceUrl: c.sourceUrl || '',
          portraitStatus: c.portrait_status
            ? {
                front: PORTRAIT_STATUS_MAP[c.portrait_status.front] || 'waiting' as const,
                side: PORTRAIT_STATUS_MAP[c.portrait_status.side] || 'waiting' as const,
                back: PORTRAIT_STATUS_MAP[c.portrait_status.back] || 'waiting' as const,
              }
            : {
                front: c.front_url ? 'generated' as const : 'waiting' as const,
                side: c.side_url ? 'generated' as const : 'waiting' as const,
                back: c.back_url ? 'generated' as const : 'waiting' as const,
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
          compositedVideo: s.compositedVideo ? (s.compositedVideo.startsWith(BASE) ? s.compositedVideo : `${BASE}${s.compositedVideo}`) : '',
          compositedPreview: s.compositedPreview ? (s.compositedPreview.startsWith(BASE) ? s.compositedPreview : `${BASE}${s.compositedPreview}`) : '',
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

  const showPlaceholder = !pipelineStartedRef.current && stage === 'new' && !output && !error && !(stepStatuses?.story && stepStatuses.story >= 1)

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
      setStepStatuses({ story: 1 })

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
      const payload: any = {
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
        finalVideo,
        finalPreview,
      }
      if (characters.length > 0) {
        payload.characters = characters.map(c => ({
          name: c.name,
          staticFeatures: c.staticFeatures,
          dynamicFeatures: c.dynamicFeatures,
          source: 'script',
          portraits: c.portraits || {},
          sourceUrl: c.sourceUrl || '',
          portraitDescriptions: c.portraitDescriptions || makePortraitDescriptions(c.name),
        }))
      }
      if (scenes.length > 0) {
        payload.scenes = scenes.map(s => ({
          title: s.title,
          content: s.content,
          slugline: '',
          environmentDesc: '',
          script: '',
          compositedVideo: s.compositedVideo ? (s.compositedVideo.startsWith(BASE) ? s.compositedVideo : `${BASE}${s.compositedVideo}`) : '',
          compositedPreview: s.compositedPreview ? (s.compositedPreview.startsWith(BASE) ? s.compositedPreview : `${BASE}${s.compositedPreview}`) : '',
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
        }))
      }
      await updateProject(props.editProjectId, payload)
    } catch (e: any) {
      console.error('保存失败:', e)
    } finally {
      setSaving(false)
    }
  }

  // 故事大纲就绪后，通过 pipeline SSE 事件自动刷新 UI 卡片
  // 该逻辑已由 pipeline.status 的 useEffect 处理

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
            compositedVideo: s.compositedVideo ? (s.compositedVideo.startsWith(BASE) ? s.compositedVideo : `${BASE}${s.compositedVideo}`) : '',
            compositedPreview: s.compositedPreview ? (s.compositedPreview.startsWith(BASE) ? s.compositedPreview : `${BASE}${s.compositedPreview}`) : '',
            compositVideoStatus: s.compositVideoStatus !== undefined ? s.compositVideoStatus : 0,
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

  const handleCharacterUpdate = (idx: number, data: CharacterData) => {
    setCharacters(prev => {
      const next = prev.map((c, i) => i === idx ? data : c)
      const pid = getEffectiveProjectId()
      if (pid) {
        updateCharacterFeatures(pid, data.name, data.staticFeatures, data.dynamicFeatures)
          .catch(e => console.error('保存角色数据失败:', e))
      }
      return next
    })
  }

  const handleSceneUpdate = (idx: number, data: SceneData) => {
    setScenes(prev => prev.map((s, i) => i === idx ? data : s))
  }

  const handleSceneScriptEdit = (idx: number, data: { title: string; content: string }) => {
    setScenes(prev => {
      const updated = prev.map((s, i) => i === idx ? { ...s, ...data } : s)
      const pid = getEffectiveProjectId()
      if (pid) {
        const scenesPayload = updated.map(s => ({
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
        }))
        fetch(`${BASE}/api/projects/${pid}/scenes`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenes: scenesPayload }),
        }).then(async r => {
          if (!r.ok) {
            const err = await r.json().catch(() => ({ error: r.statusText }))
            console.error('保存分场剧本失败:', err.error || r.statusText)
          }
        }).catch(e => console.error('保存分场剧本失败:', e))
      }
      return updated
    })
  }

  const handleRefreshSceneScripts = async () => {
    const pid = getEffectiveProjectId()
    if (!pid) return
    setRefreshingSceneScripts(true)
    try {
      const res = await fetch(`${BASE}/api/projects/${pid}/scene-scripts/generate`, { method: 'POST' })
      if (res.ok) {
        const data = await res.json()
        if (data.scenes) {
          setScenes(data.scenes.map((s: any) => ({
            title: s.title || '',
            content: s.content || '',
            shots: [],
            compositedVideo: '',
            compositedPreview: '',
          })))
        }
      }
    } catch (e: any) {
      console.error('重新生成分场剧本失败:', e)
    } finally {
      setRefreshingSceneScripts(false)
    }
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

    console.log(`[portraits] handleRefreshImage charIdx=${characterIdx} view=${view} name=${char.name}`)

    if ((view === 'side' || view === 'back') && char.portraitStatus?.front !== 'generated') {
      console.warn(`[portraits] handleRefreshImage rejected: front not generated yet for side/back`)
      return '请等正面照片生成后，再重试'
    }

    try {
      const pid = getEffectiveProjectId()!
      if (!pid) return

      const defaultStatus: PortraitStatus = { front: 'waiting', side: 'waiting', back: 'waiting' }

      setCharacters(prev => prev.map((c, i) =>
        i === characterIdx ? { ...c, portraitStatus: { ...(c.portraitStatus || defaultStatus), [view]: 'generating' as const } } : c
      ))

      const req: GeneratePortraitsRequest = {
        characters: [{
          role_name: char.name,
          ...(view === 'front'
            ? { appearance: char.staticFeatures, attire: char.dynamicFeatures }
            : { front_image: char.sourceUrl || '' }),
        }],
        view,
        style,
        model: imageModel,
        api_key: props.imageApiKey,
        base_url: props.imageBaseUrl,
        project_id: pid,
      }

      const res = await generatePortraits(req)
      console.log(`[portraits] handleRefreshImage ${view} response:`, res)

      if (res.url) {
        const url = `${BASE}${res.url}`
        setCharacters(prev => prev.map((c, i) =>
          i === characterIdx ? {
            ...c,
            portraits: { ...c.portraits, [view]: url },
            sourceUrl: view === 'front' ? (res.source_url || undefined) : c.sourceUrl,
            portraitStatus: { ...c.portraitStatus, [view]: 'generated' as const },
          } : c
        ))
      } else {
        console.error(`[portraits] handleRefreshImage ${view}: no url in response`, res)
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

          {props.editProjectId && !creating && !pipelineStartedRef.current && pipeline.status?.pipeline_status !== 'running' && pipeline.status?.pipeline_status !== 'paused' && pipeline.status?.pipeline_status !== 'completed' && (characters.length > 0 || scenes.length > 0) ? (
            <button className="np-generate-btn" onClick={handleSave} disabled={saving}>
              {saving ? '保存中...' : '💾 保存'}
            </button>
          ) : pipeline.status?.pipeline_status === 'completed' ? (
            <button className="np-generate-btn" disabled>
              已完成
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
                text = '继续'; onClick = () => pipeline.resume(); btnDisabled = false
              } else if (allDone) {
                text = '已完成'; onClick = () => {}; btnDisabled = true
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
              const dbStatus = STEP_STATUS_MAP[stepStatuses?.[step.stepKey] ?? 0]
              const rawStatus = stepState?.status || dbStatus
              const isRunning = rawStatus === 'running' || rawStatus === 'generating' || rawStatus === 'regenerating'
              const statusClass = rawStatus === 'completed' ? 'npm-step-completed'
                : isRunning ? 'npm-step-running'
                : rawStatus === 'failed' ? 'npm-step-failed'
                : 'npm-step-pending'
              return (
                <div key={step.num} className={`npm-step ${statusClass}`}>
                  <span className="npm-step-icon">{step.icon}</span>
                  <div className="npm-step-title-sm">
                    {isRunning && <span className="npm-step-dot" />}
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
              loading={stepStatuses?.story != null && stepStatuses.story !== 2 && stepStatuses.story !== 3}
              regenerating={stepStatuses?.story === 4}
              onRegenerate={async () => {
                setOutput(null)
                setStepStatuses(prev => ({ ...prev, story: 4 }))
                const pid = getEffectiveProjectId()
                if (!pid) return
                try {
                  const res = await fetch(`${BASE}/api/projects/${pid}/regenerate-story`, { method: 'POST' })
                  if (!res.ok) throw new Error(await res.text())
                  const data = await res.json()
                  setOutput(data.result)
                  refreshProjectData(pid)
                } catch (e: any) {
                  console.error('regenerate story failed', e)
                  setError(`重新生成故事失败: ${e?.message || String(e)}`)
                  setStepStatuses(prev => ({ ...prev, story: 3 }))
                }
              }}
              onSave={async (text) => {
                setOutput(text)
                const pid = getEffectiveProjectId()
                if (pid) await updateProject(pid, { story: text })
              }}
            />
            </div>
          )}
            {(creatingCharacter || characters.length > 0 || 
              pipeline.status?.steps?.characters?.status === 'running' || 
              pipeline.status?.steps?.portraits?.status === 'running' ||
              (output && characters.length === 0)) && (
            <div className="npm-card-enter">
              <CharacterCard
                characters={characters}
                aspectRatio={size}
                loading={creatingCharacter || (pipelineStartedRef.current && characters.length === 0)}
                statusMessage={characters.length === 0 ? '正在提取角色...' : undefined}
                onCharacterUpdate={handleCharacterUpdate}
                onRefreshImage={handleRefreshImage}
              />
            </div>
          )}
          {(scenes.length > 0 || (pipeline.status?.steps?.scene_scripts?.status && pipeline.status?.steps?.scene_scripts?.status !== 'pending') || stepStatuses?.scene_scripts === 1) && (
            <div className="npm-card-enter">
              <SceneScriptsCard
                scenes={scenes}
                loading={refreshingSceneScripts || stepStatuses?.scene_scripts === 1}
                onRefresh={handleRefreshSceneScripts}
                onSceneEdit={handleSceneScriptEdit}
              />
            </div>
          )}
          {(portraitsReady || creatingStoryboard || regenerating || pipeline.status?.steps?.storyboard?.status === 'running' || pipeline.status?.steps?.storyboard?.status === 'completed' || pipeline.status?.steps?.shot_frames?.status === 'running' || pipeline.status?.steps?.shot_frames?.status === 'completed' || scenes.some(s => s.shots.length > 0)) && scenes.length > 0 && (
            <div className="npm-card-enter">
              <ShootingScriptCard
                scenes={scenes}
                loading={pipeline.status?.steps?.storyboard?.status === 'running' || pipeline.status?.steps?.shot_frames?.status === 'running' || creatingStoryboard || regenerating}
                creating={creatingStoryboard || regenerating || pipeline.status?.steps?.storyboard?.status === 'running' || pipeline.status?.steps?.shot_frames?.status === 'running'}
                onSceneUpdate={handleSceneUpdate}
                onRegenerate={handleRegenerateStoryboard}
                onRefreshFrame={handleRefreshFrame}
                aspectRatio={size}
              />
            </div>
          )}
          {(finalVideo || scenes.some(s => s.compositedVideo) || finalVideoStatus === 1) && (
            <div className="npm-card-enter">
              <CreativeVideoCard
                scenes={scenes}
                aspectRatio={size}
                finalVideo={finalVideo}
                finalPreview={finalPreview}
                finalVideoStatus={finalVideoStatus}
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
