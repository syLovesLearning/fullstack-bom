"""Markdown 结构感知切片器：保留标题面包屑并保护代码块不被截断。"""

from dataclasses import dataclass
import re


@dataclass
class TextChunk:
    chunk_index: int
    heading_path: str
    content: str


_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")


def chunk_markdown(
    text: str,
    max_chars: int = 600,
    overlap_chars: int = 80,
) -> list[TextChunk]:
    lines = text.splitlines()
    heading_stack: list[tuple[int, str]] = []
    blocks: list[tuple[str, str]] = []  # (heading_path, block_text)

    buf: list[str] = []
    in_code_block = False
    current_path = "正文"

    def flush_buf() -> None:
        nonlocal buf
        joined = "\n".join(buf).strip()
        if joined:
            blocks.append((current_path, joined))
        buf = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            buf.append(line)
            continue

        if not in_code_block:
            m = _HEADING_RE.match(line)
            if m:
                flush_buf()
                level, title = len(m.group(1)), m.group(2)
                heading_stack = [h for h in heading_stack if h[0] < level]
                heading_stack.append((level, title))
                current_path = " > ".join(h[1] for h in heading_stack)
                continue

        buf.append(line)
        if not in_code_block and sum(len(x) + 1 for x in buf) >= max_chars:
            flush_buf()

    flush_buf()

    chunks: list[TextChunk] = []
    for idx, (h_path, body) in enumerate(blocks):
        if idx > 0 and overlap_chars > 0 and not body.startswith("```"):
            prev_tail = blocks[idx - 1][1][-overlap_chars:].strip()
            if prev_tail and "```" not in prev_tail:
                body = f"{prev_tail}\n{body}"
        chunks.append(TextChunk(chunk_index=idx, heading_path=h_path, content=body))
    return chunks
