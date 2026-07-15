import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useProjectStore } from '../../../stores/projectStore'

function CompositeNode({ selected }: NodeProps) {
  const finalVideo = useProjectStore(s => s.finalVideo)
  const finalPreview = useProjectStore(s => s.finalPreview)
  const status = useProjectStore(s => s.pipelineStatus?.steps?.composite_video?.status || 'pending')
  return (
    <div className={`canvas-node composite-node${selected ? ' selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <div className="canvas-node-header">
        <span className="canvas-node-icon">✨</span>
        视频合成
      </div>
      <div className="canvas-node-body">
        {finalPreview ? (
          <div className="canvas-video-preview">
            <img src={finalPreview} alt="" className="canvas-video-thumb" />
            {finalVideo && <span className="canvas-video-ready">已完成</span>}
          </div>
        ) : (
          <span className="canvas-node-empty">等待合成</span>
        )}
        <div className="canvas-node-status-row">
          <span className={`canvas-node-status-dot ${status === 'running' || status === 'generating' ? 'running' : status}`} />
          <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 10 }}>
            {status === 'completed' ? '已完成' : status === 'running' || status === 'generating' ? '合成中' : '待处理'}
          </span>
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

export default memo(CompositeNode)
