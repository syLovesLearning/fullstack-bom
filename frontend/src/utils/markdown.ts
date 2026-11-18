import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.min.css'
import { Marked } from 'marked'

const marked = new Marked({
  breaks: true,
  gfm: true,
})

marked.use({
  renderer: {
    code({ text, lang }: { text: string; lang?: string }) {
      const valid = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
      const highlighted = hljs.highlight(text, { language: valid }).value
      return `<pre class="md-pre"><code class="hljs language-${valid}">${highlighted}</code></pre>`
    },
  },
})

/** 白名单净化：LLM 输出/知识库片段经 v-html 注入前必须过 DOMPurify，防存储型 XSS。 */
const PURIFY_CONFIG = { ALLOWED_ATTR: ['class', 'href', 'src', 'alt', 'title', 'target', 'rel'] }

export function renderMarkdown(source: string): string {
  if (!source) return ''
  const html = marked.parse(source) as string
  return DOMPurify.sanitize(html, PURIFY_CONFIG)
}
