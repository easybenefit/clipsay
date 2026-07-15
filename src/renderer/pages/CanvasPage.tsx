import { useCallback, useEffect, useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
  type Node,
  type Edge,
  type Connection,
  addEdge,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import './CanvasPage.css'

import StoryNode from '../components/canvas/nodes/StoryNode'
import CharactersNode from '../components/canvas/nodes/CharactersNode'
import SceneScriptsNode from '../components/canvas/nodes/SceneScriptsNode'
import StoryboardNode from '../components/canvas/nodes/StoryboardNode'
import CompositeNode from '../components/canvas/nodes/CompositeNode'
import PipelineEdge from '../components/canvas/edges/PipelineEdge'
import Toolbar from '../components/canvas/Toolbar'
import InspectorPanel from '../components/canvas/InspectorPanel'
import { useProjectStore } from '../stores/projectStore'

interface CanvasPageProps {
  editProjectId?: number
}

const nodeTypes = {
  story: StoryNode,
  characters: CharactersNode,
  sceneScripts: SceneScriptsNode,
  storyboard: StoryboardNode,
  composite: CompositeNode,
}

const edgeTypes = {
  pipeline: PipelineEdge,
}

function buildInitialNodes(story: string | null, characters: any[], scenes: any[]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []

  let yOffset = 0
  const nodeWidth = 220
  const nodeGap = 80
  const xOffset = 0

  nodes.push({
    id: 'story',
    type: 'story',
    position: { x: xOffset, y: yOffset },
    data: { label: '故事大纲' },
  })
  const storyBase = yOffset
  yOffset += nodeGap

  nodes.push({
    id: 'characters',
    type: 'characters',
    position: { x: xOffset, y: yOffset },
    data: { label: '角色' },
  })
  edges.push({
    id: 'e-story-characters',
    source: 'story',
    target: 'characters',
    type: 'pipeline',
    markerEnd: { type: MarkerType.ArrowClosed },
  })
  yOffset += nodeGap

  nodes.push({
    id: 'sceneScripts',
    type: 'sceneScripts',
    position: { x: xOffset, y: yOffset },
    data: { label: '分场剧本' },
  })
  edges.push({
    id: 'e-characters-sceneScripts',
    source: 'characters',
    target: 'sceneScripts',
    type: 'pipeline',
    markerEnd: { type: MarkerType.ArrowClosed },
  })
  yOffset += nodeGap

  nodes.push({
    id: 'storyboard',
    type: 'storyboard',
    position: { x: xOffset, y: yOffset },
    data: { label: '分镜设计' },
  })
  edges.push({
    id: 'e-sceneScripts-storyboard',
    source: 'sceneScripts',
    target: 'storyboard',
    type: 'pipeline',
    markerEnd: { type: MarkerType.ArrowClosed },
  })
  yOffset += nodeGap

  nodes.push({
    id: 'composite',
    type: 'composite',
    position: { x: xOffset, y: yOffset },
    data: { label: '视频合成' },
  })
  edges.push({
    id: 'e-storyboard-composite',
    source: 'storyboard',
    target: 'composite',
    type: 'pipeline',
    markerEnd: { type: MarkerType.ArrowClosed },
  })

  return { nodes, edges }
}

function CanvasFlow({ editProjectId }: { editProjectId?: number }) {
  const setCanvasLayout = useProjectStore(s => s.setCanvasLayout)
  const saveCanvasLayout = useProjectStore(s => s.saveCanvasLayout)
  const setSelectedNodeId = useProjectStore(s => s.setSelectedNodeId)
  const story = useProjectStore(s => s.output)
  const characters = useProjectStore(s => s.characters)
  const scenes = useProjectStore(s => s.scenes)
  const projectId = useProjectStore(s => s.projectId)
  const loadProject = useProjectStore(s => s.loadProject)
  const connectSSE = useProjectStore(s => s.connectSSE)
  const sseConnected = useProjectStore(s => s.sseConnected)
  const loadCanvasLayout = useProjectStore(s => s.loadCanvasLayout)
  const canvasLayoutLoaded = useProjectStore(s => s.canvasLayoutLoaded)

  useEffect(() => {
    if (editProjectId && editProjectId !== projectId) {
      loadProject(editProjectId)
      connectSSE(editProjectId)
    }
  }, [editProjectId])

  useEffect(() => {
    if (projectId && !sseConnected) {
      connectSSE(projectId)
    }
  }, [projectId])

  if (!editProjectId) {
    return (
      <div className="canvas-empty">
        <div className="canvas-empty-icon">▣</div>
        <div className="canvas-empty-text">请先创建项目</div>
        <div className="canvas-empty-hint">在"创作"页面创建项目后，可在这里查看流水线全貌</div>
      </div>
    )
  }

  const initial = useMemo(() => {
    if (canvasLayoutLoaded) return { nodes: [], edges: [] }
    return buildInitialNodes(story, characters, scenes)
  }, [story, characters, scenes, canvasLayoutLoaded])

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges)

  useEffect(() => {
    if (projectId && !canvasLayoutLoaded) {
      loadCanvasLayout().then(() => {
      })
    }
  }, [projectId])

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges(eds => addEdge({
        ...connection,
        type: 'pipeline',
        markerEnd: { type: MarkerType.ArrowClosed },
      }, eds))
    },
    [setEdges],
  )

  const onAutoLayout = useCallback(() => {
    let yOffset = 0
    const gap = 80
    setNodes(nds => nds.map((n, i) => {
      const node = { ...n, position: { x: 0, y: i * gap } }
      return node
    }))
  }, [setNodes])

  const onSave = useCallback(() => {
    saveCanvasLayout()
  }, [saveCanvasLayout])

  useEffect(() => {
    setCanvasLayout(nodes, edges, null)
  }, [nodes, edges])

  return (
    <div className="canvas-flow-container">
      <Toolbar onAutoLayout={onAutoLayout} />
      <div className="canvas-flow-area">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={(_, node) => setSelectedNodeId(node.id)}
          onPaneClick={() => setSelectedNodeId(null)}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          snapToGrid
          snapGrid={[10, 10]}
          defaultEdgeOptions={{
            type: 'pipeline',
            markerEnd: { type: MarkerType.ArrowClosed },
          }}
        >
          <Background gap={10} size={1} />
        </ReactFlow>
        <InspectorPanel />
      </div>
    </div>
  )
}

function CanvasPage({ editProjectId }: CanvasPageProps) {
  return (
    <ReactFlowProvider>
      <CanvasFlow editProjectId={editProjectId} />
    </ReactFlowProvider>
  )
}

export default CanvasPage
