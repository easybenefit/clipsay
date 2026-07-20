import { create } from 'zustand'
import type { CarouselSlide } from '../Carousel'
import { listProjects, listTopCompletedProjects, duplicateProject, incrementProjectClick, checkPipelineRunning, BASE, type Project } from '../api'
import { useSettingsStore } from './settingsStore'

const DEFAULT_SLIDES: CarouselSlide[] = [
  { type: 'default', title: 'Seedance 2.0', storyTitle: 'Seedance 2.0', desc: 'AI 视频生成，前所未有的画质与一致性' },
  { type: 'default', title: '创作者挑战赛', storyTitle: '创作者挑战赛', desc: '参与挑战，赢取大奖与曝光机会' },
  { type: 'default', title: '智能剪辑', storyTitle: '智能剪辑', desc: 'AI 自动识别高光片段，一键成片' },
  { type: 'default', title: '语音转字幕', storyTitle: '语音转字幕', desc: '精准语音识别，自动生成多语言字幕' },
]

export function buildCarouselSlides(projects: Project[]): CarouselSlide[] {
  const projectSlides: CarouselSlide[] = projects.map(p => ({
    type: 'project' as const,
    projectId: p.id,
    title: p.name,
    storyTitle: (p as any).story_title || p.name,
    desc: p.idea,
    previewUrl: p.final_preview
      ? (p.final_preview.startsWith(BASE) ? p.final_preview : `${BASE}${p.final_preview}`)
      : undefined,
    videoUrl: p.final_video
      ? (p.final_video.startsWith(BASE) ? p.final_video : `${BASE}${p.final_video}`)
      : undefined,
  }))
  if (projectSlides.length >= 4) return projectSlides.slice(0, 4)
  return [...projectSlides, ...DEFAULT_SLIDES.slice(0, 4 - projectSlides.length)]
}

export async function requireNoRunningPipeline(): Promise<boolean> {
  const status = await checkPipelineRunning()
  if (status.running) {
    useSettingsStore.getState().showToast(`工程 ${status.project_id} 正在创作，请先完成或取消`)
    return false
  }
  return true
}

export function getProjectById(projects: Project[], id: number): Project | undefined {
  return projects.find(p => p.id === id)
}

interface ProjectStore {
  projects: Project[]
  topProjects: Project[]
  playVideo: { url: string; title: string; desc: string } | null

  refreshProjects: () => Promise<void>
  setPlayVideo: (data: { url: string; title: string; desc: string } | null) => void
  duplicateProjectAction: (id: number) => Promise<Project | undefined>
  incrementClick: (id: number) => void
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  topProjects: [],
  playVideo: null,

  refreshProjects: async () => {
    try {
      const [projects, topProjects] = await Promise.all([
        listProjects(),
        listTopCompletedProjects(),
      ])
      set({ projects, topProjects })
    } catch {}
  },

  setPlayVideo: (data) => set({ playVideo: data }),

  duplicateProjectAction: async (id) => {
    if (!await requireNoRunningPipeline()) return undefined
    try {
      const dup = await duplicateProject(id)
      get().refreshProjects()
      return dup
    } catch {
      useSettingsStore.getState().showToast('复制失败')
      return undefined
    }
  },

  incrementClick: (id) => {
    incrementProjectClick(id).catch(() => {})
  },
}))
