import { memo } from 'react'
import { useReactFlow } from '@xyflow/react'
import { useProjectStore } from '../../stores/projectStore'

interface ToolbarProps {
  onAutoLayout: () => void
}

const VIEW_BOX = '0 0 16 16'

const icons = {
  autoLayout: (
    <svg width="14" height="14" viewBox={VIEW_BOX} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="2" y="2" width="5" height="5" rx="1" />
      <rect x="9" y="2" width="5" height="5" rx="1" />
      <rect x="2" y="9" width="5" height="5" rx="1" />
      <rect x="9" y="9" width="5" height="5" rx="1" />
    </svg>
  ),
  save: (
    <svg width="14" height="14" viewBox={VIEW_BOX} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M12 14H4a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h6.5L13 5.5V13a1 1 0 0 1-1 1z" />
      <path d="M5 14V9h6v5" />
      <path d="M6 2v3h3.5" />
    </svg>
  ),
  fitView: (
    <svg width="14" height="14" viewBox={VIEW_BOX} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M2 5V2h3" />
      <path d="M14 5V2h-3" />
      <path d="M2 11v3h3" />
      <path d="M14 11v3h-3" />
    </svg>
  ),
}

function ToolbarInner({ onAutoLayout }: ToolbarProps) {
  const { fitView } = useReactFlow()
  const saveCanvasLayout = useProjectStore(s => s.saveCanvasLayout)
  const sseConnected = useProjectStore(s => s.sseConnected)
  const pipelineStatus = useProjectStore(s => s.pipelineStatus)
  const projectId = useProjectStore(s => s.projectId)

  const isRunning = pipelineStatus?.pipeline_status === 'running'
  const pipelineText = isRunning ? '运行中' : pipelineStatus?.pipeline_status === 'completed' ? '已完成' : '待运行'

  return (
    <div className="canvas-toolbar">
      <div className="canvas-toolbar-left">
        <button className="canvas-tb-btn" onClick={onAutoLayout} title="自动布局">
          {icons.autoLayout}
          布局
        </button>
        <div className="canvas-tb-divider" />
        <button className="canvas-tb-btn" onClick={() => { saveCanvasLayout(); fitView() }} title="保存布局">
          {icons.save}
          保存
        </button>
        <button className="canvas-tb-btn" onClick={() => fitView({ padding: 0.2 })} title="适配视图">
          {icons.fitView}
          适配
        </button>
      </div>
      <div className="canvas-toolbar-right">
        <div className="canvas-status-badge">
          <span className={`canvas-status-dot ${sseConnected ? 'connected' : 'disconnected'}`} />
          {pipelineText}
        </div>
        {projectId && <span className="canvas-status-badge">#{projectId}</span>}
      </div>
    </div>
  )
}

const Toolbar = memo(ToolbarInner)
export default Toolbar
