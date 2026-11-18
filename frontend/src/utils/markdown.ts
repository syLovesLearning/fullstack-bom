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

export function renderMarkdown(source: string): string {
  if (!source) return ''
  return marked.parse(source) as string
}
