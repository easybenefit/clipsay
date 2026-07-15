import { memo, useMemo } from 'react'
import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/react'

const STATUS_COLORS: Record<string, string> = {
  pending: 'rgba(255,255,255,0.12)',
  running: '#60a5fa',
  generating: '#60a5fa',
  completed: '#22c55e',
  failed: '#ef4444',
  skipped: 'rgba(255,255,255,0.08)',
}

function PipelineEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
}: EdgeProps) {
  const [path] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const status = (data as any)?.status || 'pending'
  const color = STATUS_COLORS[status] || STATUS_COLORS.pending

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: color,
          strokeWidth: status === 'completed' ? 2 : 1.5,
          transition: 'stroke 0.3s',
        }}
        markerEnd={markerEnd}
      />
    </>
  )
}

export default memo(PipelineEdge)
