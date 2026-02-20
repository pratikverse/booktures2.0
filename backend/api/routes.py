import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

try:
    from backend.core.database import get_db
    from backend.models.book import Book
    from backend.models.page import Page
    from backend.services.ingest.pdf_service import PDFService
except ModuleNotFoundError:
    from core.database import get_db
    from models.book import Book
    from models.page import Page
    from services.ingest.pdf_service import PDFService

logger = logging.getLogger(__name__)
router = APIRouter()
pdf_service = PDFService()

def error_payload(code: str, message: str, details: str | None = None) -> dict:
    # Standardized error body for easier frontend handling and debugging.
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "booktures2-backend"}


@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    title: str | None = None,
    author: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    Phase 1 endpoint:
    - validates and saves PDF
    - extracts page text
    - inserts one Book and related Page rows
    """
    try:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail=error_payload("INVALID_FILE", "Missing file name in upload."),
            )

        content = await file.read()
        pdf_path = pdf_service.save_pdf(content, file.filename)
        pages_data = pdf_service.extract_text_by_page(pdf_path)
        if not pages_data:
            raise HTTPException(
                status_code=400,
                detail=error_payload(
                    "EMPTY_EXTRACTED_CONTENT",
                    "No usable pages found after PDF preprocessing.",
                    "The document may be scanned/noisy or filtered as front matter.",
                ),
            )

        book = Book(
            title=title or file.filename.replace(".pdf", ""),
            author=author or "Unknown",
            total_pages=len(pages_data),
            description=f"Uploaded from {file.filename}",
        )
        db.add(book)
        db.flush()

        for page_data in pages_data:
            db.add(
                Page(
                    book_id=book.id,
                    page_number=page_data["page_number"],
                    text=page_data["text"],
                    pdf_path=pdf_path,
                )
            )

        db.commit()
        return {
            "book_id": book.id,
            "title": book.title,
            "author": book.author,
            "total_pages": len(pages_data),
            # Returning stored path helps later reprocessing/reference workflows.
            "pdf_path": pdf_path,
            "message": "PDF uploaded and pages extracted",
        }

    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=error_payload("VALIDATION_ERROR", "PDF validation failed.", str(e)),
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Upload failed")
        raise HTTPException(
            status_code=500,
            detail=error_payload("UPLOAD_FAILED", "Unexpected error during upload.", str(e)),
        )
