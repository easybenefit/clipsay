import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { useProjectStore } from '../../../stores/projectStore'

function CharactersNode({ selected }: NodeProps) {
  const characters = useProjectStore(s => s.characters)
  const status = useProjectStore(s => s.pipelineStatus?.steps?.characters?.status || 'pending')
  return (
    <div className={`canvas-node characters-node${selected ? ' selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <div className="canvas-node-header">
        <span className="canvas-node-icon">👤</span>
        角色 ({characters.length})
      </div>
      <div className="canvas-node-body">
        {characters.length === 0 ? (
          <span className="canvas-node-empty">等待提取</span>
        ) : (
          <div className="canvas-char-list">
            {characters.slice(0, 4).map((c, i) => (
              <div key={i} className="canvas-char-item">
                {c.portraits?.front ? (
                  <img className="canvas-char-avatar" src={c.portraits.front} alt="" />
                ) : (
                  <div className="canvas-char-avatar-placeholder" />
                )}
                <span>{c.name}</span>
              </div>
            ))}
            {characters.length > 4 && (
              <div className="canvas-char-more">+{characters.length - 4}</div>
            )}
          </div>
        )}
        <div className="canvas-node-status-row">
          <span className={`canvas-node-status-dot ${status === 'running' || status === 'generating' ? 'running' : status}`} />
          <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 10 }}>
            {status === 'completed' ? '已完成' : status === 'running' || status === 'generating' ? '生成中' : '待处理'}
          </span>
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

export default memo(CharactersNode)
