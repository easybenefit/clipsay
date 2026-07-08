interface ModelCardProps {
  title: string
  description: string
  model: string
  apiKey: string
  baseUrl: string
  rateLimitMin: string
  rateLimitDay: string
  modelOptions: string[]
  onModelChange: (model: string) => void
  onUpdate: (field: string, value: string) => void
  onSave: () => void
}

function ModelCard(props: ModelCardProps): JSX.Element {
  return (
    <div className="settings-card">
      <div className="settings-card-header">
        <span className="settings-card-title">{props.title}</span>
        <span className="settings-card-desc">{props.description}</span>
      </div>
      <div className="settings-field">
        <span>模型</span>
        <select className="settings-select" value={props.model} onChange={e => props.onModelChange(e.target.value)}>
          {props.modelOptions.map(m => <option key={m}>{m}</option>)}
        </select>
      </div>
      <div className="settings-field">
        <span>API 密钥</span>
        <input className="settings-input" type="password" value={props.apiKey} onChange={e => props.onUpdate('apiKey', e.target.value)} placeholder="sk-..." />
      </div>
      <div className="settings-field">
        <span>URL 地址</span>
        <input className="settings-input" type="text" value={props.baseUrl} onChange={e => props.onUpdate('baseUrl', e.target.value)} placeholder="https://..." />
      </div>
      <div className="settings-field">
        <span>速率限制</span>
        <div className="settings-rl-inline">
          <div className="settings-rl-row">
            <input className="settings-input" type="text" value={props.rateLimitMin} onChange={e => props.onUpdate('rateLimitMin', e.target.value)} placeholder="500" />
            <span className="settings-rl-label">/ 分钟</span>
          </div>
          <div className="settings-rl-row">
            <input className="settings-input" type="text" value={props.rateLimitDay} onChange={e => props.onUpdate('rateLimitDay', e.target.value)} placeholder="2000" />
            <span className="settings-rl-label">/ 天</span>
          </div>
        </div>
      </div>
      <div className="settings-card-actions">
        <button className="btn-primary" style={{ width: '100%' }} onClick={props.onSave}>保存</button>
      </div>
    </div>
  )
}

export default ModelCard