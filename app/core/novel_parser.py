"""Novel Ingestion and Structural Chunking Engine with Deterministic Citations."""
import hashlib
import os
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.database import get_connection


@dataclass
class NovelChunk:
    chunk_id: str
    project_id: str
    chapter_number: int
    chapter_title: str
    chunk_index: int
    text_content: str
    word_count: int
    content_hash: str


class NovelParser:
    """Parses TXT/Markdown novels, detects chapter boundaries, and produces stable chunk citations."""

    CHAPTER_PATTERNS = [
        re.compile(r'^(?:#+\s*)?(?:Chapter|CHAPTER)\s+(\d+|[IVXLCDM]+)(?:\s*[:\-\u2013\u2014]\s*(.+))?$', re.MULTILINE),
        re.compile(r'^(?:#+\s*)?(?:Part|PART|Book|BOOK|Act|ACT)\s+(\d+|[IVXLCDM]+)(?:\s*[:\-\u2013\u2014]\s*(.+))?$', re.MULTILINE),
        re.compile(r'^(?:#+\s*)([A-Z0-9\s]{3,40})$', re.MULTILINE),
    ]

    @classmethod
    def split_chapters(cls, text: str) -> List[Dict[str, Any]]:
        """Identify chapter headings and split text into structural chapters."""
        lines = text.splitlines()
        chapters = []
        current_num = 1
        current_title = "Prologue / Opening"
        current_lines = []

        for line in lines:
            stripped = line.strip()
            matched = False
            for pat in cls.CHAPTER_PATTERNS:
                m = pat.match(stripped)
                if m:
                    # Save existing chapter if it has text
                    if current_lines:
                        raw_ch_text = "\n".join(current_lines).strip()
                        if raw_ch_text:
                            chapters.append({
                                "chapter_number": current_num,
                                "title": current_title,
                                "content": raw_ch_text
                            })
                            current_num += 1
                        current_lines = []

                    raw_num = m.group(1) if m.lastindex and m.lastindex >= 1 else str(current_num)
                    raw_title = m.group(2) if m.lastindex and m.lastindex >= 2 and m.group(2) else f"Chapter {raw_num}"
                    current_title = raw_title.strip()
                    matched = True
                    break

            if not matched:
                current_lines.append(line)

        # Append last chapter
        if current_lines:
            raw_ch_text = "\n".join(current_lines).strip()
            if raw_ch_text:
                chapters.append({
                    "chapter_number": current_num,
                    "title": current_title,
                    "content": raw_ch_text
                })

        if not chapters and text.strip():
            chapters.append({
                "chapter_number": 1,
                "title": "Chapter 1",
                "content": text.strip()
            })

        return chapters

    @classmethod
    def chunk_chapter(cls, project_id: str, chapter: Dict[str, Any], chunk_size_words: int = 500, overlap_words: int = 50) -> List[NovelChunk]:
        """Split chapter into stable, cited chunks with predictable IDs."""
        words = chapter["content"].split()
        chunks = []
        ch_num = chapter["chapter_number"]
        ch_title = chapter["title"]

        if not words:
            return chunks

        start = 0
        chunk_idx = 1

        while start < len(words):
            end = min(start + chunk_size_words, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:16]
            chunk_id = f"{project_id}_CH{ch_num:03d}_CHUNK{chunk_idx:04d}"

            chunks.append(NovelChunk(
                chunk_id=chunk_id,
                project_id=project_id,
                chapter_number=ch_num,
                chapter_title=ch_title,
                chunk_index=chunk_idx,
                text_content=chunk_text,
                word_count=len(chunk_words),
                content_hash=content_hash
            ))

            if end >= len(words):
                break
            start += chunk_size_words - overlap_words
            chunk_idx += 1

        return chunks

    @classmethod
    def ingest_novel_text(cls, project_id: str, title: str, raw_text: str) -> List[NovelChunk]:
        """Parse novel, generate chunks, index into SQLite FTS5 canon knowledge table."""
        chapters = cls.split_chapters(raw_text)
        all_chunks: List[NovelChunk] = []

        for ch in chapters:
            ch_chunks = cls.chunk_chapter(project_id, ch)
            all_chunks.extend(ch_chunks)

        # Store in SQLite FTS5 for citation retrieval
        conn = get_connection()
        try:
            for c in all_chunks:
                conn.execute(
                    """
                    INSERT INTO canon_knowledge_fts (entity_id, entity_type, title, content)
                    VALUES (?, 'novel_chunk', ?, ?)
                    """,
                    (c.chunk_id, f"{title} - {c.chapter_title} (Chunk {c.chunk_index})", c.text_content)
                )
            conn.commit()
        finally:
            conn.close()

        return all_chunks
