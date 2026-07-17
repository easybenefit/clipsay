import type { CharacterData } from './CharacterCard'
import type { SceneData } from './ShootingScriptCard'

export type CreationStage = 'new' | 'story' | 'characters' | 'script' | 'storyboard'

export interface CreationState {
  stage: CreationStage
  idea: string
  style: string
  size: string
  sizeTier: string
  resolution: string
  frameRate: string
  duration: string
  language: string
  chatModel: string
  imageModel: string
  videoModel: string
  output: string | null
  characters: CharacterData[]
  scenes: SceneData[]
}

const STORAGE_KEY = 'clipsay-creation-state'

export function saveCreationState(state: CreationState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (e) {
    console.error('Failed to save creation state:', e)
  }
}

export function loadCreationState(): CreationState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as CreationState
  } catch (e) {
    console.error('Failed to load creation state:', e)
    return null
  }
}

export function clearCreationState(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    console.error('Failed to clear creation state:', e)
  }
}
