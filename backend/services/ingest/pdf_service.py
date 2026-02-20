import logging
import os
import re
import uuid
from pathlib import Path
from typing import Dict, List

import pdfplumber

logger = logging.getLogger(__name__)

# Resolve storage path relative to project root (booktures2.0), not current working directory.
# This guarantees uploads always land in `<project>/storage/pdfs` even when server runs from `backend/`.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PDF_STORAGE_PATH = PROJECT_ROOT / "storage" / "pdfs"
PDF_STORAGE_PATH = Path(os.getenv("PDF_STORAGE_PATH", str(DEFAULT_PDF_STORAGE_PATH))).resolve()
MAX_FILE_SIZE_MB = int(os.getenv("MAX_PDF_SIZE_MB", "100"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf"}
ENABLE_TEXT_PREPROCESSING = os.getenv("ENABLE_TEXT_PREPROCESSING", "true").lower() == "true"


class PDFService:
    """
    Handles PDF validation, persistence, and page-wise extraction.
    Keeping this isolated makes later OCR/advanced ingestion upgrades simple.
    """

    def save_pdf(self, file_bytes: bytes, filename: str) -> str:
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File too large (> {MAX_FILE_SIZE_MB}MB)")

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError("Only PDF files are allowed")

        # Quick signature check to reject invalid payloads early.
        if not file_bytes.startswith(b"%PDF"):
            raise ValueError("File is not a valid PDF")

        os.makedirs(PDF_STORAGE_PATH, exist_ok=True)
        unique_name = f"{uuid.uuid4()}_{filename}"
        path = str(PDF_STORAGE_PATH / unique_name)

        with open(path, "wb") as f:
            f.write(file_bytes)

        logger.info("PDF saved at: %s", path)
        return path

    def extract_text_by_page(self, pdf_path: str) -> List[Dict]:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        raw_pages: List[Dict] = []
        with pdfplumber.open(pdf_path) as pdf:
            for idx, page in enumerate(pdf.pages):
                text = (page.extract_text() or "").strip()
                raw_pages.append(
                    {
                        "page_number": idx + 1,
                        "text": text,
                    }
                )

        if not ENABLE_TEXT_PREPROCESSING:
            return raw_pages

        # Preprocess text before persistence:
        # 1) remove repeating headers/footers
        # 2) drop obvious front-matter/noise pages (preface/about/index/etc)
        # This keeps downstream extraction cleaner and faster.
        return self._preprocess_pages(raw_pages)

    def _preprocess_pages(self, pages: List[Dict]) -> List[Dict]:
        if not pages:
            return pages

        header_counts: Dict[str, int] = {}
        footer_counts: Dict[str, int] = {}
        page_lines: List[List[str]] = []

        for page in pages:
            lines = [ln.strip() for ln in page["text"].splitlines() if ln.strip()]
            page_lines.append(lines)
            if lines:
                head = self._normalize_line(lines[0])
                tail = self._normalize_line(lines[-1])
                if head:
                    header_counts[head] = header_counts.get(head, 0) + 1
                if tail:
                    footer_counts[tail] = footer_counts.get(tail, 0) + 1

        recurring_threshold = max(3, int(len(pages) * 0.2))
        recurring_headers = {k for k, v in header_counts.items() if v >= recurring_threshold}
        recurring_footers = {k for k, v in footer_counts.items() if v >= recurring_threshold}

        cleaned_pages: List[Dict] = []
        for idx, page in enumerate(pages):
            lines = page_lines[idx]
            lines = self._strip_recurring_edges(lines, recurring_headers, recurring_footers)
            text = "\n".join(lines).strip()

            candidate = {"page_number": page["page_number"], "text": text}
            if self._is_noise_page(candidate, logical_position=idx + 1):
                continue
            if not text:
                continue
            cleaned_pages.append(candidate)

        # Safety fallback: never return empty output due to aggressive heuristics.
        return cleaned_pages or pages

    def _strip_recurring_edges(self, lines: List[str], recurring_headers: set, recurring_footers: set) -> List[str]:
        if not lines:
            return lines
        cleaned = list(lines)
        while cleaned and self._normalize_line(cleaned[0]) in recurring_headers:
            cleaned.pop(0)
        while cleaned and self._normalize_line(cleaned[-1]) in recurring_footers:
            cleaned.pop()
        return cleaned

    def _normalize_line(self, line: str) -> str:
        normalized = re.sub(r"\s+", " ", line.strip().lower())
        normalized = re.sub(r"[^a-z0-9 ]", "", normalized)
        return normalized.strip()

    def _is_noise_page(self, page: Dict, logical_position: int) -> bool:
        text = page.get("text", "").strip()
        if not text:
            return True

        lowered = text.lower()
        words = re.findall(r"[a-zA-Z']+", lowered)
        word_count = len(words)

        front_matter_keywords = [
            "preface", "about the author", "copyright", "all rights reserved", "table of contents",
            "contents", "acknowledg", "dedication", "isbn", "published by", "index"
        ]

        # Drop low-information pages.
        if word_count < 20:
            return True

        # Drop likely front matter only for early logical pages.
        keyword_hits = sum(1 for kw in front_matter_keywords if kw in lowered)
        if logical_position <= 15 and keyword_hits >= 1 and word_count < 220:
            return True

        return False
