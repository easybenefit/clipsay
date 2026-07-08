import Markdown from './Markdown'
import './SceneScriptsCard.css'

export interface SceneScriptScene {
  title: string
  content: string
}

interface SceneScriptsCardProps {
  scenes: SceneScriptScene[]
  loading?: boolean
}

function SceneScriptsCard({ scenes, loading = false }: SceneScriptsCardProps): JSX.Element {
  return (
    <div className="scene-scripts-card">
      <div className="scene-scripts-card-header">
        <div className="scene-scripts-card-title">分场剧本</div>
      </div>
      <div className="scene-scripts-card-divider" />
      <div className="scene-scripts-card-body-area">
        <div className="scene-scripts-card-body">
          {scenes.length === 0 ? (
            <div className="scene-scripts-card-empty">暂无可用的场景</div>
          ) : (
            <ul className="scene-scripts-card-list">
              {scenes.map((scene, idx) => {
                const cleanTitle = scene.title || `场景${idx + 1}`
                return (
                  <li key={idx} className="scene-scripts-card-item">
                    <div className="scene-scripts-card-item-index">
                      <span className="scene-scripts-card-item-index-num">{String(idx + 1).padStart(2, '0')}</span>
                      <span className="scene-scripts-card-item-index-title">{cleanTitle}</span>
                    </div>
                    <div className="scene-scripts-card-item-content"><Markdown content={scene.content.replace(/\\n/g, '\n')} /></div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
        <div className={`scene-scripts-card-loading-overlay${loading ? ' active' : ''}`}>
          <div className="scene-scripts-card-loading-icon">✦</div>
          <div className="scene-scripts-card-loading-text">正在创作</div>
        </div>
      </div>
    </div>
  )
}

export default SceneScriptsCard
