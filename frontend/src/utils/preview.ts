// Rebuild a non-interactive preview from API HTML. Never insert source HTML into
// the host DOM; discard all source CSS, URLs, attributes, SVG and executable tags.
const ALLOWED = new Set(['H1', 'H2', 'H3', 'H4', 'P', 'DIV', 'SECTION', 'ARTICLE', 'HEADER', 'FOOTER', 'SPAN', 'STRONG', 'B', 'EM', 'SMALL', 'CODE', 'PRE', 'TABLE', 'THEAD', 'TBODY', 'TR', 'TH', 'TD', 'UL', 'OL', 'LI', 'DL', 'DT', 'DD', 'BR', 'HR'])
const DROP = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'SVG', 'MATH', 'LINK', 'META', 'BASE', 'IMG', 'AUDIO', 'VIDEO', 'SOURCE', 'FORM', 'INPUT', 'BUTTON', 'TEMPLATE', 'HEAD', 'TITLE', 'NAV'])
const CLASSES = new Set(['metrics', 'metric', 'states', 'state', 'caption', 'scope', 'brand', 'verified', 'blocked', 'risk', 'unknown', 'not_applicable', 'issue', 'issue-body', 'tag', 'table-wrap', 'empty'])
const escape = (text: string) => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
export function safePreview(source: string): string {
  // Template contents are inert (including resource loading); never attach this
  // template to a document. DOMParser documents can load resource URLs.
  const template = document.createElement('template')
  template.innerHTML = source
  let budget = 50000
  let truncated = false
  function walk(node: Node, depth = 0): string {
    if (--budget < 0 || depth > 40) { truncated = true; return '' }
    if (node.nodeType === Node.TEXT_NODE) return escape((node.textContent || '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u00ad\u061c\u200b-\u200f\u2028-\u202e\u2060-\u206f\ud800-\udfff\ufeff]/gu,
      char => `[U+${char.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')}]`))
    if (node.nodeType !== Node.ELEMENT_NODE) return ''
    const el = node as Element
    if (DROP.has(el.tagName)) return ''
    const inner = Array.from(el.childNodes).map(child => walk(child, depth + 1)).join('')
    const tag = ({ DETAILS: 'section', SUMMARY: 'h3' } as Record<string, string>)[el.tagName] || el.tagName.toLowerCase()
    const classes = [...el.classList].filter(c => CLASSES.has(c)).join(' ')
    const attr = classes ? ` class="${classes}"` : ''
    return ALLOWED.has(el.tagName) || ['DETAILS', 'SUMMARY'].includes(el.tagName) ? `<${tag}${attr}>${inner}</${tag}>` : inner
  }
  let body = Array.from(template.content.childNodes).map(node => walk(node)).join('')
  if (truncated) body += '<p>预览内容超出显示预算，部分内容已省略。请下载完整报告。</p>'
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; font-src 'none'; media-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'"><meta name="referrer" content="no-referrer"><style>body{font:14px/1.7 'Segoe UI','Microsoft YaHei',sans-serif;color:#18324d;background:white;padding:28px;overflow-wrap:anywhere}h1,h2,h3{color:#132c48}h2{border-bottom:1px solid #dce3ed;padding-bottom:8px}table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #dce3ed;padding:8px;text-align:left}code,pre{font-family:Consolas,monospace;white-space:pre-wrap}section{margin:24px 0}.metrics,.states{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.metric,.state{padding:12px;border:1px solid #dce3ed;border-radius:4px}.metric strong,.state strong{display:block;font:24px/1.5 Consolas,monospace}.caption{font-size:11px;color:#64758a}.scope{background:#edf3fc;border-left:3px solid #285eff;padding:12px}.issue{border:1px solid #dce3ed;padding:16px}.tag{display:block;font-size:11px;color:#64758a}.table-wrap{overflow:auto}dt{color:#64758a}dd{margin-left:0;margin-bottom:10px}.brand{font:11px Consolas,monospace;color:#64758a}</style></head><body>${body}</body></html>`
}
