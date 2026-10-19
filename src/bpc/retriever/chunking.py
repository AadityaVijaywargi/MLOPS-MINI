"""Structure-aware chunking for bye-law / zoning PDFs (L1).

Why not fixed-size windows: the requirements live in table rows and in the
notes printed under tables ("If the road width is less than 9.0 m, then the
maximum height is restricted to ..."). A fixed window either splits a table from
its caption or buries a one-line note inside an unrelated passage, so a query
about height never sees it and a citation can only point at "page 28".

Strategy:
  1. Clean page text (running headers, page numbers, TOC dot-leaders).
  2. Segment on the document's own structure: chapters, numbered sections
     (3.4, 9.10.4, 4.1.2) and tables (Table 10 / TABLE 13). Section numbers must
     increase monotonically, which rejects table rows such as "2.25 Above 12.0".
  3. Inside a block, split on enumerated clauses ((ii), (b), iii.) so every note
     under a table is its own chunk with a clause-level id: ZR2015:T10:ii.b.
  4. Prefix every chunk with a context header (document > chapter > section >
     table > clause) before embedding, so a note that only says "the maximum
     height is restricted..." still carries "Residential (Main) / Table 10 / FAR".
  5. Record outgoing references ("Table.8", "bye-law 16.0") so the agent can
     follow them with a tool instead of hoping similarity search finds them.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

_NOISE = [
    re.compile(r"^\s*-\s*\d{1,3}\s*-\s*$"),
    re.compile(r"^\s*\d{1,3}\s*$"),
    re.compile(r"^\s*Building\s+Bye\s*-?\s*Laws\s*[–-]\s*2003\s*$", re.I),
    re.compile(r"\.{5,}"),  # table-of-contents leaders
]
_CHAPTER = re.compile(r"^\s*CHAPTER\s*[.\-]?\s*([0-9IVX]+(?:\.\d+)?)\s*[:.\-]?\s*(.*)$", re.I)
_TABLE = re.compile(r"^\s*TABLE\s*\.?\s*(?:No\.?\s*:?\s*)?(\d{1,2})\s*[:.\-]?\s*(.*)$", re.I)
_SECTION = re.compile(r"^\s*(\d{1,2}(?:\s?\.\s?\d{1,2}){1,3})\s*\)?\s*[:.\-]?\s+(\S.*)$")
_BAD_TITLE_START = re.compile(r"^(up\s*to|upto|above|over|below|and|or|to|m\b|mts?\b|sq|%|x\b)", re.I)
_MARKER = re.compile(r"^\s*\(?\s*([ivx]{1,4}|[a-h])\s*[\).]\s+(?=\S)")
_REF_TABLE = re.compile(r"Table\s*\.?\s*(?:No\.?\s*:?\s*)?(\d{1,2})\b", re.I)
_REF_BYELAW = re.compile(r"bye\s*-?\s*laws?\s*(?:No\.?\s*)?(\d{1,2}(?:\.\d{1,2}){1,3})", re.I)
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
          "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15}

MAX_CHUNK_CHARS = 1600
OVERLAP_CHARS = 150
MIN_SEGMENT_CHARS = 25  # "ii) Notes:" joins the clause after it; "a) TDR is applicable..." stays its own


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_short: str
    doc_title: str
    chapter: str | None
    section: str | None
    section_title: str | None
    table: str | None
    table_title: str | None
    marker: str | None
    page_start: int
    page_end: int
    text: str
    refs: list[str] = field(default_factory=list)
    neighbors: list[str] = field(default_factory=list)

    @property
    def clause_label(self) -> str:
        parts = [self.doc_short]
        if self.section:
            parts.append(f"§{self.section}")
        if self.table:
            parts.append(f"Table {self.table}")
        if self.marker:
            parts.append("(" + ")(".join(self.marker.split(".")) + ")")
        return " ".join(parts)

    @property
    def header(self) -> str:
        bits = [self.doc_title]
        if self.chapter:
            bits.append(self.chapter)
        if self.section:
            bits.append(f"{self.section} {self.section_title or ''}".strip())
        if self.table:
            bits.append(f"Table {self.table}: {self.table_title or ''}".strip())
        if self.marker:
            bits.append(f"clause ({self.marker})")
        return " > ".join(bits) + f" [p.{self.page_start}]"

    @property
    def embed_text(self) -> str:
        return f"{self.header}\n{self.text}"

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.embed_text.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id, "doc_id": self.doc_id, "doc_short": self.doc_short,
            "chapter": self.chapter, "section": self.section, "section_title": self.section_title,
            "table": self.table, "table_title": self.table_title, "marker": self.marker,
            "clause_label": self.clause_label, "page_start": self.page_start, "page_end": self.page_end,
            "header": self.header, "text": self.text, "refs": self.refs, "neighbors": self.neighbors,
            "content_hash": self.content_hash,
        }


@dataclass
class _Line:
    page: int
    text: str


@dataclass
class _Block:
    kind: str  # pre | section | table
    chapter: str | None
    section: str | None
    section_title: str | None
    table: str | None
    table_title: str | None
    lines: list[_Line]

    @property
    def body_chars(self) -> int:
        return sum(len(line.text) for line in self.lines[1:])


def clean_pages(pages: list[str]) -> list[_Line]:
    out: list[_Line] = []
    for pno, text in enumerate(pages, start=1):
        for raw in (text or "").splitlines():
            line = re.sub(r"[ \t ]+", " ", raw).strip()
            if not line or any(p.search(line) for p in _NOISE):
                continue
            out.append(_Line(pno, line))
    return out


def _section_tuple(num: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.sub(r"\s", "", num).split("."))


def _segment(lines: list[_Line]) -> list[_Block]:
    blocks: list[_Block] = []
    chapter: str | None = None
    section: str | None = None
    section_title: str | None = None
    last_sec: tuple[int, ...] = (0,)
    cur = _Block("pre", None, None, None, None, None, [])

    def start(block: _Block) -> None:
        nonlocal cur
        blocks.append(cur)
        cur = block

    for line in lines:
        t = line.text
        m = _CHAPTER.match(t)
        if m:
            chapter = f"Chapter {m.group(1)} {m.group(2)}".strip()
            start(_Block("section", chapter, section, section_title, None, None, [line]))
            continue
        m = _TABLE.match(t)
        if m and (not m.group(2) or not m.group(2)[0].islower()):
            start(_Block("table", chapter, section, section_title, m.group(1), m.group(2).strip(" :.-") or None, [line]))
            continue
        m = _SECTION.match(t)
        if m:
            num = re.sub(r"\s", "", m.group(1)).rstrip(".")
            title = m.group(2)
            tup = _section_tuple(num)
            plausible = (
                (title[0].isalpha() or title[0] in "'‘’\"“")
                and not _BAD_TITLE_START.match(title)
                and tup[0] <= 25
                and tup > last_sec
                and tup[0] - last_sec[0] <= 2
            )
            if plausible:
                last_sec = tup
                section, section_title = num, title[:90]
                start(_Block("section", chapter, section, section_title, None, None, [line]))
                continue
        cur.lines.append(line)
    blocks.append(cur)

    # Heading-only blocks (e.g. a "List of tables" entry) are folded into the previous block.
    merged: list[_Block] = []
    for b in blocks:
        if not b.lines:
            continue
        if merged and b.body_chars < 40 and b.kind == "table":
            merged[-1].lines.extend(b.lines)
            continue
        merged.append(b)
    for b in merged:  # table titles that sit on the lines after "TABLE 5"
        if b.kind == "table" and not b.table_title and len(b.lines) > 1:
            title_lines = [ln.text for ln in b.lines[1:4] if not ln.text.startswith("(")]
            b.table_title = " ".join(title_lines[:2])[:120]
    return merged


def _split_markers(lines: list[_Line]) -> list[tuple[str | None, list[_Line]]]:
    segments: list[tuple[str | None, list[_Line]]] = [(None, [])]
    roman: str | None = None
    alpha: str | None = None
    for line in lines:
        m = _MARKER.match(line.text)
        if m:
            tok = m.group(1).lower()
            is_alpha = tok in "abcdefgh" and len(tok) == 1 and not (tok == "i" and alpha != "h")
            if tok == "i" and alpha == "h":
                is_alpha = True
            if is_alpha:
                alpha = tok
                path = f"{roman}.{alpha}" if roman else alpha
            else:
                roman, alpha = tok, None
                path = roman
            segments.append((path, [line]))
        else:
            segments[-1][1].append(line)
    segments = [s for s in segments if s[1]]
    # merge tiny segments forward (e.g. "ii) Notes:" joins "a) Setbacks shall ...")
    out: list[tuple[str | None, list[_Line]]] = []
    carry: list[_Line] = []
    for idx, (path, seg_lines) in enumerate(segments):
        chars = sum(len(ln.text) for ln in seg_lines)
        if chars < MIN_SEGMENT_CHARS and idx < len(segments) - 1 and path is not None:
            carry.extend(seg_lines)
            continue
        out.append((path, carry + seg_lines))
        carry = []
    if carry:
        out.append((None, carry))
    return out


def _window(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + MAX_CHUNK_CHARS)
        if end < len(text):
            cut = text.rfind("\n", start + MAX_CHUNK_CHARS // 2, end)
            end = cut if cut > 0 else end
        parts.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)
    return parts


def _refs(doc_id: str, text: str) -> list[str]:
    refs = {f"{doc_id}:T{m.group(1)}" for m in _REF_TABLE.finditer(text)}
    refs |= {f"BBL2003:s{m.group(1)}" for m in _REF_BYELAW.finditer(text)}
    return sorted(refs)


def chunk_document(doc_id: str, doc_short: str, doc_title: str, pages: list[str]) -> list[Chunk]:
    lines = clean_pages(pages)
    chunks: list[Chunk] = []
    seen: dict[str, int] = {}
    blocks = _segment(lines)
    # A table number can appear in a "list of tables" before the real table; the
    # canonical id goes to the occurrence with the most body text.
    best: dict[str, int] = {}
    for i, b in enumerate(blocks):
        if b.table and (b.table not in best or b.body_chars > blocks[best[b.table]].body_chars):
            best[b.table] = i
    for i, block in enumerate(blocks):
        if block.table:
            base = f"{doc_id}:T{block.table}" + ("" if best[block.table] == i else "~list")
        else:
            base = f"{doc_id}:" + (f"s{block.section}" if block.section else "pre")
        block_chunks: list[Chunk] = []
        for path, seg_lines in _split_markers(block.lines):
            text = "\n".join(ln.text for ln in seg_lines)
            for wi, piece in enumerate(_window(text)):
                if len(piece) < 15:
                    continue
                cid = base + (f":{path}" if path else "") + (f"~w{wi + 1}" if wi else "")
                n = seen.get(cid, 0)
                seen[cid] = n + 1
                if n:
                    cid = f"{cid}~{n + 1}"
                block_chunks.append(Chunk(
                    chunk_id=cid, doc_id=doc_id, doc_short=doc_short, doc_title=doc_title,
                    chapter=block.chapter, section=block.section, section_title=block.section_title,
                    table=block.table, table_title=block.table_title, marker=path,
                    page_start=seg_lines[0].page, page_end=seg_lines[-1].page, text=piece,
                    refs=[r for r in _refs(doc_id, piece) if r != base],
                ))
        ids = [c.chunk_id for c in block_chunks]
        for c in block_chunks:  # siblings in the same block (table rows <-> its notes)
            c.neighbors = [i for i in ids if i != c.chunk_id][:12]
        chunks.extend(block_chunks)
    return chunks
