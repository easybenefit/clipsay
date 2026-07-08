function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderInline(text: string): (string | JSX.Element)[] {
  const parts: (string | JSX.Element)[] = []
  const tokenRe = /(`[^`]+`)|(\*\*\*(.+?)\*\*\*)|(\*\*(.+?)\*\*)|(\*(.+?)\*)/g
  let lastIdx = 0
  let match: RegExpExecArray | null
  while ((match = tokenRe.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(escapeHtml(text.slice(lastIdx, match.index)))
    }
    if (match[1]) {
      parts.push(<code key={parts.length} className="md-code">{match[1].slice(1, -1)}</code>)
    } else if (match[2]) {
      parts.push(<strong key={parts.length}><em>{match[3]}</em></strong>)
    } else if (match[4]) {
      parts.push(<strong key={parts.length}>{match[5]}</strong>)
    } else if (match[6]) {
      parts.push(<em key={parts.length}>{match[7]}</em>)
    }
    lastIdx = match.index + match[0].length
  }
  if (lastIdx < text.length) {
    parts.push(escapeHtml(text.slice(lastIdx)))
  }
  return parts
}

function Markdown({ content }: { content: string }): JSX.Element {
  const lines = content.split('\n')

  const elements: JSX.Element[] = []
  let inUl = false
  let inOl = false
  let bulletItems: JSX.Element[] = []

  function flushList(key: string) {
    if (inUl) {
      elements.push(<ul key={key + '-ul'} className="md-list">{bulletItems}</ul>)
      bulletItems = []
      inUl = false
    }
    if (inOl) {
      elements.push(<ol key={key + '-ol'} className="md-list">{bulletItems}</ol>)
      bulletItems = []
      inOl = false
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const lineKey = `l-${i}`

    const ulMatch = line.match(/^[-*+]\s+(.*)/)
    const olMatch = line.match(/^\d+\.\s+(.*)/)

    if (ulMatch) {
      if (inOl) { flushList(lineKey) }
      inUl = true
      bulletItems.push(<li key={lineKey} className="md-li">{renderInline(ulMatch[1])}</li>)
      continue
    }

    if (olMatch) {
      if (inUl) { flushList(lineKey) }
      inOl = true
      bulletItems.push(<li key={lineKey} className="md-li">{renderInline(olMatch[1])}</li>)
      continue
    }

    flushList(lineKey)

    if (line.trim() === '') {
      elements.push(<div key={lineKey} className="md-spacer" />)
      continue
    }

    const hMatch = line.match(/^(#{1,3})\s+(.*)/)
    if (hMatch) {
      const level = hMatch[1].length as 1 | 2 | 3
      const H = `h${level}` as keyof JSX.IntrinsicElements
      elements.push(<H key={lineKey} className="md-heading">{renderInline(hMatch[2])}</H>)
      continue
    }

    elements.push(<p key={lineKey} className="md-p">{renderInline(line)}</p>)
  }

  flushList('end')

  return <>{elements}</>
}

export default Markdown
