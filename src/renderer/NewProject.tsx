import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { usePipelineSSE, EVENT_PROJECT_UPDATED } from './usePipelineSSE'

import StoryCard from './StoryCard'
import CharacterCard from './CharacterCard'
import ShootingScriptCard from './ShootingScriptCard'
import CreativeVideoCard from './CreativeVideoCard'
import SceneScriptsCard from './SceneScriptsCard'
import { ModelSelect } from './ModelCard'
import { useCreationStore, SIZES, SIZE_TIERS, RESOLUTIONS, FRAME_RATES, DURATIONS, STYLES, STEPS, STEP_STATUS_MAP } from './stores/creationStore'
import { useSettingsStore, CHAT_OPTIONS, IMAGE_OPTIONS, VIDEO_OPTIONS } from './stores/settingsStore'

import './NewProject.css'

interface NewProjectProps {
  editProjectId?: number
  onCreated: () => void
  onCancel: () => void
  onProjectSelected?: (projectId: number) => void
}

function NewProject(props: NewProjectProps): JSX.Element {
  const store = useCreationStore()
  const modelOpts = useMemo(() => ({
    chat: { options: CHAT_OPTIONS, value: store.chatModel, onChange: (v: string) => useCreationStore.getState().setField('chatModel', v) },
    image: { options: IMAGE_OPTIONS, value: store.imageModel, onChange: (v: string) => useCreationStore.getState().setField('imageModel', v) },
    video: { options: VIDEO_OPTIONS, value: store.videoModel, onChange: (v: string) => useCreationStore.getState().setField('videoModel', v) },
  }), [store.chatModel, store.imageModel, store.videoModel])

  const canGenerate = store.idea.trim().length >= 5
  const showPlaceholder = !store.pipelineStarted && store.stage === 'new' && !store.output && !store.error && !(store.stepStatuses?.story && store.stepStatuses.story >= 1)

  const handlePipelineEvent = useCallback((event: any) => {
    const cs = useCreationStore.getState()
    const pid = cs.projectId
    if (!pid) return
    if (event.type === 'step_data_ready' && event.step) {
      cs.refreshStepData(pid, event.step)
    } else if (event.type === EVENT_PROJECT_UPDATED) {
      cs.refreshProjectData(pid)
    }
  }, [])

  const projectId = store.projectId ?? props.editProjectId ?? null
  const pipeline = usePipelineSSE(projectId, handlePipelineEvent)

  const lastShotFramesRef = useRef('')
  useEffect(() => {
    const sfStep = pipeline.status?.steps?.shot_frames
    const status = sfStep?.status || ''
    if (status === 'running' && lastShotFramesRef.current !== 'running') {
      lastShotFramesRef.current = 'running'
      useCreationStore.getState().setPendingShotsGenerating()
    } else {
      lastShotFramesRef.current = status
    }
  }, [pipeline.status?.steps?.shot_frames?.status])

  useEffect(() => {
    const cvStep = pipeline.status?.steps?.composite_video
    if (!cvStep) return
    useCreationStore.getState().updateFinalVideoStatusFromPipeline(cvStep.status)
  }, [pipeline.status?.steps?.composite_video?.status])

  useEffect(() => {
    if (!props.editProjectId) return
    useCreationStore.getState().loadProject(props.editProjectId)
  }, [props.editProjectId])

  useEffect(() => {
    if (props.editProjectId !== undefined) return
    useCreationStore.getState().reset()
  }, [props.editProjectId])

  const handleCreate = useCallback(async () => {
    const newPid: number | undefined = await useCreationStore.getState().handleCreate(pipeline.start)
    if (newPid) props.onProjectSelected?.(newPid)
  }, [pipeline.start, props.onProjectSelected])

  const handleSave = useCallback(async () => {
    await useCreationStore.getState().handleSave()
  }, [])

  const stepState = (stepKey: string) => {
    const ps = pipeline.status?.steps?.[stepKey]
    const dbStatus = STEP_STATUS_MAP[store.stepStatuses?.[stepKey] ?? 0]
    const rawStatus = ps?.status || dbStatus
    const isRunning = rawStatus === 'running' || rawStatus === 'generating' || rawStatus === 'regenerating'
    return { rawStatus, isRunning, progress: ps?.progress ?? 0, message: ps?.status === 'running' && pipeline.status?.pipeline_message ? pipeline.status.pipeline_message : '' }
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
                <ModelSelect options={modelOpts.chat.options} value={modelOpts.chat.value} onChange={modelOpts.chat.onChange} />
              </div>
              <div className="np-section">
                <label className="np-label">图像模型</label>
                <ModelSelect options={modelOpts.image.options} value={modelOpts.image.value} onChange={modelOpts.image.onChange} />
              </div>
              <div className="np-section">
                <label className="np-label">视频模型</label>
                <ModelSelect options={modelOpts.video.options} value={modelOpts.video.value} onChange={modelOpts.video.onChange} />
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">创意</div>
              <textarea className="np-idea-input" rows={5} placeholder="创意即影像..." value={store.idea} onChange={e => useCreationStore.getState().setField('idea', e.target.value)} />
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">风格</div>
              <div className="np-center-grid">
                {STYLES.map(s => (
                  <button key={s.id} className={`np-size-btn${store.style === s.id ? ' active' : ''}`} onClick={() => useCreationStore.getState().setField('style', s.id)}><span>{s.label}</span></button>
                ))}
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">尺寸</div>
              <div className="np-size-grid">
                {SIZE_TIERS.map(t => (
                  <button key={t.id} className={`np-size-btn${store.sizeTier === t.id ? ' active' : ''}`} onClick={() => useCreationStore.getState().setField('sizeTier', t.id)}><span>{t.subLabel}</span></button>
                ))}
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">宽高比</div>
              <div className="np-size-grid">
                {SIZES.map(s => (
                  <button key={s.id} className={`np-size-btn${store.size === s.id ? ' active' : ''}`} data-aspect={s.id} onClick={() => useCreationStore.getState().setField('size', s.id)}>
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
                  <button key={r.id} className={`np-size-btn${store.resolution === r.id ? ' active' : ''}`} onClick={() => useCreationStore.getState().setField('resolution', r.id)}><span>{r.label}</span></button>
                ))}
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">帧率</div>
              <div className="np-size-grid">
                {FRAME_RATES.map(f => (
                  <button key={f.id} className={`np-size-btn${store.frameRate === f.id ? ' active' : ''}`} onClick={() => useCreationStore.getState().setField('frameRate', f.id)}><span>{f.label}</span></button>
                ))}
              </div>
            </div>

            <div className="np-model-group">
              <div className="np-model-group-title">生成时长</div>
              <div className="np-size-grid">
                {DURATIONS.map(d => (
                  <button key={d.id} className={`np-size-btn${store.duration === d.id ? ' active' : ''}`} onClick={() => useCreationStore.getState().setField('duration', d.id)}><span>{d.label}</span></button>
                ))}
              </div>
            </div>
          </div>

          {props.editProjectId && !store.creating && !store.pipelineStarted && pipeline.status?.pipeline_status !== 'running' && pipeline.status?.pipeline_status !== 'paused' && pipeline.status?.pipeline_status !== 'completed' && (store.characters.length > 0 || store.scenes.length > 0) ? (
            <button className="np-generate-btn" onClick={handleSave} disabled={store.saving}>
              {store.saving ? '保存中...' : '💾 保存'}
            </button>
          ) : pipeline.status?.pipeline_status === 'completed' ? (
            <button className="np-generate-btn" disabled>已完成</button>
          ) : (() => {
            const ps = pipeline.status?.pipeline_status
            const steps = pipeline.status?.steps || {}
            const stepKeys = Object.keys(steps)
            const allDone = stepKeys.length > 0 && stepKeys.every(k => steps[k]?.status === 'completed')
            const isRunning = ps === 'running'
            const isPaused = ps === 'paused'
            let text: string, onClick: () => void, btnDisabled: boolean
            if (store.creating) { text = '正在创作'; onClick = () => {}; btnDisabled = true }
            else if (isRunning) { text = '正在创作'; onClick = () => {}; btnDisabled = true }
            else if (isPaused) { text = '继续'; onClick = () => pipeline.resume(); btnDisabled = false }
            else if (allDone) { text = '已完成'; onClick = () => {}; btnDisabled = true }
            else { text = '立即创作'; onClick = handleCreate; btnDisabled = !canGenerate }
            const spinning = store.creating || isRunning
            return (
              <button className={`np-generate-btn${spinning ? ' creating' : ''}`} onClick={onClick} disabled={btnDisabled}>
                {spinning ? '正在创作' : text}
              </button>
            )
          })()}
        </aside>

        <main className="new-project-main">
          <div className="npm-steps-section">
            <div className="npm-steps-header">
              <h2 className="npm-steps-title">创作流程</h2>
            </div>
            <div className="npm-steps">
              {STEPS.map((step, si) => {
                const ss = stepState(step.stepKey)
                const statusClass = ss.rawStatus === 'completed' ? 'npm-step-completed'
                  : ss.isRunning ? 'npm-step-running'
                  : ss.rawStatus === 'failed' ? 'npm-step-failed' : 'npm-step-pending'
                return (
                  <div key={step.num} className={`npm-step ${statusClass}`} style={{ '--step-index': si } as React.CSSProperties}>
                    <span className="npm-step-icon">{step.icon}</span>
                    <div className="npm-step-title-sm">
                      {ss.isRunning && <span className="npm-step-dot" />}
                      {step.title}
                    </div>
                    <div className="npm-step-desc-sm">{step.desc}</div>
                    {ss.isRunning && ss.progress > 0 && (
                      <div className="npm-step-message">{ss.message || `${Math.round(ss.progress * 100)}%`}</div>
                    )}

                    <div className="npm-step-glow" />
                  </div>
                )
              })}
            </div>
          </div>

          <div className="npm-scroll-area">
            {showPlaceholder && !store.creating && (
              <div className="npm-placeholder">
                <div className="npm-placeholder-ring"><div className="npm-placeholder-icon">✦</div></div>
                <div className="npm-placeholder-text">快来创作吧</div>
              </div>
            )}

            {store.creating && showPlaceholder && (
              <div className="npm-creating-overlay">
                <div className="npm-creating-orb">
                  <div className="npm-creating-orb-ring" /><div className="npm-creating-orb-ring" /><div className="npm-creating-orb-ring" />
                  <div className="npm-creating-orb-core">✦</div>
                </div>
                <div className="npm-creating-text">
                  <div className="npm-creating-title">正在创作</div>
                  <div className="npm-creating-sub">{pipeline.status?.pipeline_message || 'AI 正在全力构思你的故事...'}</div>
                  {pipeline.status?.pipeline_step && (
                    <div className="npm-creating-step">
                      <span className="npm-creating-step-dot" />
                      {STEPS.find(s => s.stepKey === pipeline.status!.pipeline_step)?.title || pipeline.status.pipeline_step}
                    </div>
                  )}
                </div>
              </div>
            )}

            {(store.creating || !!store.stepStatuses?.story) && (
              <div className="npm-card-enter"><StoryCard /></div>
            )}

            {(store.creatingCharacter || store.characters.length > 0 ||
              pipeline.status?.steps?.characters?.status === 'running' ||
              pipeline.status?.steps?.portraits?.status === 'running' ||
              (store.output && store.characters.length === 0)) && (
              <div className="npm-card-enter"><CharacterCard /></div>
            )}

            {(store.scenes.length > 0 || (pipeline.status?.steps?.scene_scripts?.status && pipeline.status?.steps?.scene_scripts?.status !== 'pending') || store.stepStatuses?.scene_scripts === 1) && (
              <div className="npm-card-enter"><SceneScriptsCard /></div>
            )}

            {(store.portraitsReady || store.creatingStoryboard || store.regenerating ||
              pipeline.status?.steps?.storyboard?.status === 'running' || pipeline.status?.steps?.storyboard?.status === 'completed' ||
              pipeline.status?.steps?.shot_frames?.status === 'running' || pipeline.status?.steps?.shot_frames?.status === 'completed' ||
              store.scenes.some(s => s.shots.length > 0) ||
              store.stepStatuses?.storyboard === 1 || store.stepStatuses?.storyboard === 4 ||
              store.stepStatuses?.shot_frames === 1 || store.stepStatuses?.shot_frames === 4) && store.scenes.length > 0 && (
              <div className="npm-card-enter"><ShootingScriptCard /></div>
            )}

            {(store.finalVideo || store.finalVideoStatus >= 1) && (
              <div className="npm-card-enter"><CreativeVideoCard /></div>
            )}

            {store.error && (
              <div className="npm-output npm-error">
                <div className="npm-output-content">{store.error}</div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

export default NewProject
