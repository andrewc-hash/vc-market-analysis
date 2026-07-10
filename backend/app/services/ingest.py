"""Focal-startup document ingest.

Turns the files a user uploaded for their focal startup into ONE labeled text blob
that the researcher node injects as primary source material. Hybrid strategy:

  - .txt / .md            -> read directly
  - .docx                 -> python-docx paragraph text
  - .pdf                  -> PyMuPDF text; any sparse/image-only page falls back to a
                             vision-model transcription (handles image-heavy pitch decks)
  - .png/.jpg/.webp/...   -> vision-model transcription
  - .vtt / .srt           -> subtitle-format call transcript, flattened to "[mm:ss] line"
  - .mp3/.m4a/.wav/.webm  -> meeting recording, transcribed via the OpenAI audio API
                             (whisper), with per-segment [mm:ss] timestamps

Call transcripts / recordings are tagged "[CALL TRANSCRIPT]" in their source-file
header so downstream stages (founder-claim extraction + the fact-check audit) can
tell testimony from documents. `split_transcripts` separates the two.

Text extraction is dependency-light and unit-testable with no API calls; only the
vision fallback and audio transcription hit an API, and each is isolated behind a
module function (`_vision_image_bytes`, `_transcribe_audio`) so tests can monkeypatch.
"""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# A PDF page with fewer than this many extractable characters is treated as
# image-only and routed to the vision model instead of trusting the empty text.
_MIN_PAGE_CHARS = 80
# Cost guard: never vision-parse more than this many pages across one upload.
_MAX_VISION_PAGES = 40

_TEXT_EXTS = {".txt", ".md", ".markdown"}
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_SUBTITLE_EXTS = {".vtt", ".srt"}
_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".webm"}

# Header tag marking a chunk as call testimony (vs a document). Consumed by
# split_transcripts and the claim-extraction stage — keep the literal stable.
TRANSCRIPT_TAG = "[CALL TRANSCRIPT]"
# A .txt/.docx whose NAME says it's a call gets transcript-tagged too.
_TRANSCRIPT_NAME_RE = re.compile(r"transcript|meeting|call|recording", re.I)

_VISION_PROMPT = (
    "This is one page/slide from a startup's materials (pitch deck, financial model, "
    "or memo). Transcribe ALL text verbatim, and describe every chart/table/diagram with "
    "its concrete numbers and labels. Output plain text only — no preamble, no commentary."
)


def extract_materials_cached(upload_dir: str | Path, vision: bool = True) -> str:
    """extract_materials() with a per-upload cache at `<dir>/_extracted.txt`.

    The first caller (the /api/derive-scope endpoint OR the ingest node, whichever runs
    first) parses the files and writes the cache; the second reuses it — so an image-heavy
    deck is vision-parsed at most ONCE per upload, not twice.
    """
    p = Path(upload_dir)
    cache = p / "_extracted.txt"
    if cache.is_file():
        try:
            return cache.read_text(errors="ignore")
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to read extract cache %s: %s", cache, e)
    text = extract_materials(upload_dir, vision=vision)
    if text and p.is_dir():
        try:
            cache.write_text(text)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to write extract cache %s: %s", cache, e)
    return text


def extract_materials(upload_dir: str | Path, vision: bool = True) -> str:
    """Parse every file in `upload_dir` into one labeled text blob (or '' if none)."""
    p = Path(upload_dir)
    if not p.is_dir():
        logger.info("No upload dir at %s", p)
        return ""
    chunks: list[str] = []
    for fp in sorted(p.iterdir()):
        if not fp.is_file() or fp.name.startswith("_"):
            continue  # leading "_" is reserved for internal artifacts (e.g. the extract cache)
        try:
            text = _extract_one(fp, vision=vision)
        except Exception as e:  # noqa: BLE001 - one bad file must not sink the run
            logger.warning("Failed to parse upload %s: %s", fp.name, e)
            text = ""
        if text and text.strip():
            tag = f" {TRANSCRIPT_TAG}" if _is_transcript(fp) else ""
            chunks.append(f"### Source file: {fp.name}{tag}\n\n{text.strip()}")
    return "\n\n".join(chunks)


def _is_transcript(fp: Path) -> bool:
    ext = fp.suffix.lower()
    if ext in _SUBTITLE_EXTS or ext in _AUDIO_EXTS:
        return True
    return ext in (_TEXT_EXTS | {".docx"}) and bool(_TRANSCRIPT_NAME_RE.search(fp.stem))


def split_transcripts(blob: str) -> tuple[str, str]:
    """Split an extract_materials blob into (call transcripts, everything else),
    keyed on the TRANSCRIPT_TAG in each chunk's source-file header."""
    calls: list[str] = []
    docs: list[str] = []
    for chunk in (blob or "").split("\n\n### Source file: "):
        if not chunk.strip():
            continue
        body = chunk if chunk.startswith("### Source file: ") else f"### Source file: {chunk}"
        (calls if TRANSCRIPT_TAG in body.split("\n", 1)[0] else docs).append(body)
    return "\n\n".join(calls), "\n\n".join(docs)


def _extract_one(fp: Path, vision: bool) -> str:
    ext = fp.suffix.lower()
    if ext in _TEXT_EXTS:
        return fp.read_text(errors="ignore")
    if ext == ".docx":
        return _extract_docx(fp)
    if ext == ".pdf":
        return _extract_pdf(fp, vision=vision)
    if ext in _IMAGE_EXTS:
        return _safe_vision(fp.read_bytes(), ext) if vision else ""
    if ext in _SUBTITLE_EXTS:
        return _parse_subtitles(fp.read_text(errors="ignore"))
    if ext in _AUDIO_EXTS:
        return _safe_audio(fp)
    logger.info("Unsupported file type skipped: %s", fp.name)
    return ""


# --- Call transcripts (.vtt/.srt) + meeting recordings (audio) --------------- #

_TS_LINE_RE = re.compile(
    r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,]\d{1,3}\s*-->\s*[\d:.,]+"
)


def _parse_subtitles(text: str) -> str:
    """Flatten WebVTT/SRT cues to '[mm:ss] line' rows (hours folded into minutes),
    dropping cue indices, headers, and duplicate consecutive lines."""
    out: list[str] = []
    stamp = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or line.isdigit() or line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        m = _TS_LINE_RE.match(line)
        if m:
            h, mnt, sec = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
            stamp = f"[{h * 60 + mnt:02d}:{sec:02d}]"
            continue
        line = re.sub(r"</?[^>]+>", "", line)  # strip cue markup like <v Speaker>
        entry = f"{stamp} {line}".strip()
        if out and out[-1].split("] ", 1)[-1] == line:
            continue  # rolling-caption duplicate
        out.append(entry)
    return "\n".join(out)


def _safe_audio(fp: Path) -> str:
    """Audio transcription wrapped so a failure degrades to '' instead of raising."""
    try:
        return _transcribe_audio(fp)
    except Exception as e:  # noqa: BLE001
        logger.warning("Audio transcription failed (%s): %s", fp.name, e)
        return ""


def _transcribe_audio(fp: Path) -> str:
    """Transcribe one meeting recording via the OpenAI audio API (already a dependency
    through langchain-openai), returning '[mm:ss] text' rows from the segment timings."""
    from openai import OpenAI

    from app.config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("No OPENAI_API_KEY — cannot transcribe %s", fp.name)
        return ""
    client = OpenAI(api_key=settings.openai_api_key)
    with fp.open("rb") as fh:
        resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=fh,
            response_format="verbose_json",
        )
    segments = getattr(resp, "segments", None) or []
    lines = []
    for seg in segments:
        start = getattr(seg, "start", None)
        text = (getattr(seg, "text", "") or "").strip()
        if not text:
            continue
        if isinstance(start, (int, float)):
            lines.append(f"[{int(start) // 60:02d}:{int(start) % 60:02d}] {text}")
        else:
            lines.append(text)
    return "\n".join(lines) if lines else (getattr(resp, "text", "") or "")


def _extract_docx(fp: Path) -> str:
    import docx  # python-docx

    d = docx.Document(str(fp))
    return "\n".join(par.text for par in d.paragraphs if par.text.strip())


def _extract_pdf(fp: Path, vision: bool) -> str:
    import fitz  # PyMuPDF

    parts: list[str] = []
    vision_used = 0
    with fitz.open(str(fp)) as doc:
        for i, page in enumerate(doc):
            txt = (page.get_text("text") or "").strip()
            if len(txt) >= _MIN_PAGE_CHARS or not vision:
                if txt:
                    parts.append(txt)
            elif vision_used < _MAX_VISION_PAGES:
                # sparse / image-only page -> render and transcribe with the vision model
                png = page.get_pixmap(dpi=140).tobytes("png")
                vtxt = _safe_vision(png, ".png")
                vision_used += 1
                if vtxt.strip():
                    parts.append(f"[page {i + 1} (vision-read)]\n{vtxt.strip()}")
    if vision_used >= _MAX_VISION_PAGES:
        logger.warning("Hit the %d-page vision cap for %s — later pages skipped", _MAX_VISION_PAGES, fp.name)
    return "\n\n".join(parts)


def _safe_vision(data: bytes, ext: str) -> str:
    """Vision call wrapped so a single page failure degrades to '' instead of raising."""
    try:
        return _vision_image_bytes(data, ext)
    except Exception as e:  # noqa: BLE001
        logger.warning("Vision transcription failed (%s): %s", ext, e)
        return ""


def _vision_image_bytes(data: bytes, ext: str) -> str:
    """Send one image to the multimodal model and return its transcription."""
    from langchain_core.messages import HumanMessage
    from langchain_google_genai import ChatGoogleGenerativeAI

    from app.config import get_settings

    settings = get_settings()
    if not settings.google_api_key:
        return ""
    mime = {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "webp": "image/webp", "gif": "image/gif", "bmp": "image/bmp",
    }.get(ext.lstrip(".").lower(), "image/png")
    b64 = base64.b64encode(data).decode()
    llm = ChatGoogleGenerativeAI(
        model=settings.vision_model,
        google_api_key=settings.google_api_key,
        temperature=0.1,
        max_output_tokens=2048,
    )
    msg = HumanMessage(content=[
        {"type": "text", "text": _VISION_PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ])
    resp = llm.invoke([msg])
    content = resp.content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    return str(content)
