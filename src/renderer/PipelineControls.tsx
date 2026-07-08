import { usePipelineSSE, PipelineStatus } from './usePipelineSSE'
import './NewProject.css'

interface PipelineControlsProps {
  projectId: number | null
  pipelineStatus: PipelineStatus | null
  connected: boolean
  onRegenerateStep: (step: string) => void
  disabled?: boolean
}

const STEP_LABELS: Record<string, string> = {
  story: '故事大纲',
  characters: '角色提取',
  portraits: '角色肖像',
  scene_scripts: '场景脚本',
  storyboard: '分镜设计',
  shot_frames: '镜头帧生成',
  composite_video: '视频合成',
}

function getStepDotClass(status: string): string {
  switch (status) {
    case 'completed': return 'pstep-dot done'
    case 'running': return 'pstep-dot active'
    case 'failed': return 'pstep-dot error'
    case 'skipped': return 'pstep-dot skip'
    default: return 'pstep-dot'
  }
}

const STEP_RESULT_LABELS: Record<string, (r: any) => string> = {
  characters: (r) => r.character_count ? `${r.character_count}个角色` : '',
  portraits: (r) => r.portrait_count ? `${r.portrait_count}张肖像` : '',
  scene_scripts: (r) => r.scene_count ? `${r.scene_count}场场景` : '',
  storyboard: (r) => r.scene_count ? `${r.scene_count}场分镜` : '',
  shot_frames: (r) => r.frame_count ? `${r.frame_count}帧` : '',
  composite_video: (r) => r.scene_count ? `${r.scene_count}段视频` : '',
}

function getStatusText(status: string, s: any, stepKey?: string): string {
  switch (status) {
    case 'pending': return '等待中'
    case 'running': return s?.progress ? `${Math.round(s.progress * 100)}%` : '运行中'
    case 'completed': {
      let text = '已完成'
      if (stepKey) {
        try {
          const result = s?.result ? JSON.parse(s.result) : null
          const label = result && STEP_RESULT_LABELS[stepKey]?.(result)
          if (label) text += ` (${label})`
        } catch { /* ignore */ }
      }
      return text
    }
    case 'failed': return `失败: ${s?.error || ''}`
    case 'skipped': return '已跳过'
    default: return status
  }
}

export function PipelineControls({ projectId, pipelineStatus: status, connected, onRegenerateStep, disabled }: PipelineControlsProps) {
  if (!projectId) return null

  const s = status
  const isRunning = s?.is_running || false
  const steps = s?.steps || {}

  return (
    <div className="pipeline-controls">
      <div className="pipeline-header">
        <h3 className="pipeline-title">Pipeline 进度</h3>
        <span className={`pipeline-badge ${connected ? 'online' : 'offline'}`}>
          {connected ? '已连接' : '未连接'}
        </span>
      </div>

      <div className="pipeline-steps">
        {Object.entries(STEP_LABELS).map(([stepKey, label]) => {
          const stepState = steps[stepKey]
          const st = stepState?.status || 'pending'
          return (
            <div key={stepKey} className={`pstep-row ${st}`}>
              <div className={getStepDotClass(st)} />
              <span className="pstep-label">{label}</span>
              <span className="pstep-status">{getStatusText(st, stepState, stepKey)}</span>
              {st === 'completed' && (
                <button className="pstep-regen" onClick={() => onRegenerateStep(stepKey)} disabled={isRunning}>
                  重做
                </button>
              )}
              {st === 'failed' && (
                <button className="pstep-regen" onClick={() => onRegenerateStep(stepKey)}>
                  重试
                </button>
              )}
            </div>
          )
        })}
      </div>

      {s?.pipeline_error && (
        <div className="pipeline-error">{s.pipeline_error}</div>
      )}
    </div>
  )
}
