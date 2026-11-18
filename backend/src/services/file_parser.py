"""文件解析与安全解包服务：支持 .md / .txt / .pdf 及 .zip 批量安全解压。"""

import asyncio
import io
from pathlib import Path, PurePosixPath
import zipfile

from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".md", ".txt", ".pdf"}
MAX_FILE_BYTES = 10 * 1024 * 1024       # 单文件最大 10 MB
MAX_ZIP_UNCOMPRESSED = 30 * 1024 * 1024  # ZIP 解压后总大小上限 30 MB
MAX_ZIP_FILES = 50                       # 单包最多解析 50 个有效文件


def _extract_pdf_text(raw_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw_bytes))
    pages: list[str] = []
    for idx, page in enumerate(reader.pages, start=1):
        txt = (page.extract_text() or "").strip()
        if txt:
            pages.append(f"## 第 {idx} 页\n{txt}")
    return "\n\n".join(pages)


async def parse_uploaded_file(filename: str, raw_bytes: bytes) -> tuple[str, str]:
    """返回 (文档标题, 提取后的文本内容)。"""
    if len(raw_bytes) > MAX_FILE_BYTES:
        raise ValueError("文件超过 10MB 限制")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {ext}，仅支持 .md / .txt / .pdf")

    title = Path(filename).stem or "未命名文档"
    if ext == ".pdf":
        text = await asyncio.to_thread(_extract_pdf_text, raw_bytes)
    else:
        text = raw_bytes.decode("utf-8", errors="replace")

    if not text.strip():
        raise ValueError("未能从文件中提取到有效文本内容")
    return title, text


def expand_uploaded_archive(raw_bytes: bytes) -> list[tuple[str, bytes]]:
    """安全解压 ZIP：过滤 __MACOSX / 隐藏文件 / 路径穿越，限制总大小与数量。"""
    items: list[tuple[str, bytes]] = []
    total_size = 0

    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            parts = PurePosixPath(info.filename).parts
            if not parts or ".." in parts or "__MACOSX" in parts:
                continue
            if any(p.startswith(".") for p in parts):
                continue
            if Path(info.filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            total_size += info.file_size
            if total_size > MAX_ZIP_UNCOMPRESSED:
                raise ValueError("ZIP 解压后总体积超过 30MB 限制，请分批上传")
            if len(items) >= MAX_ZIP_FILES:
                raise ValueError(f"ZIP 内有效文档超过 {MAX_ZIP_FILES} 个上限，请分批上传")

            clean_name = "/".join(parts)
            items.append((clean_name, zf.read(info.filename)))
    return items
