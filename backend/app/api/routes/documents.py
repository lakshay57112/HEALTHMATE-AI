from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.serializers import document_out
from app.core.config import BASE_DIR, get_settings
from app.core.security import require_patient
from app.db.session import get_db
from app.models import DocumentChunk, MedicalDocument, User
from app.services.audit import audit
from app.services.consent import has_consent
from app.services.extraction.commit import commit_document
from app.services.extraction.pipeline import process_document
from app.services.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()

DOC_TYPES = {"auto", "lab_report", "prescription", "consultation_note", "diet_advice", "appointment", "other"}
SAMPLE_DIR = BASE_DIR / "sample_docs"
SAMPLES = {
    "lab_report": ("sample_lipid_diabetes_report.pdf", "application/pdf", "lab_report"),
    "prescription": ("sample_prescription.pdf", "application/pdf", "prescription"),
    "prescription_photo": ("sample_prescription_photo.png", "image/png", "prescription"),
    "diet_advice": ("sample_diet_advice.pdf", "application/pdf", "diet_advice"),
    "appointment": ("sample_appointment.pdf", "application/pdf", "appointment"),
    "consultation_note": ("sample_consultation_note.pdf", "application/pdf", "consultation_note"),
    "injection_test": ("sample_injection_test.pdf", "application/pdf", "auto"),
}


def sniff_mime(data: bytes) -> str | None:
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return None


def _create(db: Session, user: User, data: bytes, filename: str, declared: str, request: Request, bg: BackgroundTasks) -> MedicalDocument:
    if not has_consent(db, user.id, "ai_processing"):
        raise HTTPException(403, "Please allow AI document processing in Settings → Privacy before uploading.")
    if declared not in DOC_TYPES:
        raise HTTPException(422, "Unknown document type")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
    if len(data) < 100:
        raise HTTPException(422, "File looks empty")
    mime = sniff_mime(data)
    if not mime:
        raise HTTPException(415, "Only PDF, JPG and PNG files are supported")
    key, sha = get_storage().save(user.id, data)
    doc = MedicalDocument(user_id=user.id, declared_type=declared, filename=Path(filename or "document").name[:200], mime_type=mime, size_bytes=len(data),
                          sha256=sha, storage_key=key, status="uploaded")
    dup = db.scalar(select(MedicalDocument).where(MedicalDocument.user_id == user.id, MedicalDocument.sha256 == sha, MedicalDocument.status == "verified"))
    if dup:
        doc.flags = ["duplicate_upload"]
    db.add(doc)
    audit(db, "document.upload", actor_id=user.id, resource_type="document", resource_id=doc.id, meta={"mime": mime, "declared": declared, "size": len(data)}, request=request)
    db.commit()
    bg.add_task(process_document, doc.id)
    return doc


@router.post("")
async def upload(request: Request, bg: BackgroundTasks, file: UploadFile = File(...), declared_type: str = Form("auto"),
                 user: User = Depends(require_patient), db: Session = Depends(get_db)):
    data = await file.read()
    doc = _create(db, user, data, file.filename or "upload", declared_type, request, bg)
    return {"document": document_out(doc)}


@router.get("/samples")
def list_samples():
    return {"items": [{"key": k, "filename": v[0], "type": v[2]} for k, v in SAMPLES.items() if (SAMPLE_DIR / v[0]).exists()]}


@router.post("/samples/{key}")
def upload_sample(key: str, request: Request, bg: BackgroundTasks, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    if key not in SAMPLES:
        raise HTTPException(404, "Unknown sample")
    fname, _, declared = SAMPLES[key]
    path = SAMPLE_DIR / fname
    if not path.exists():
        raise HTTPException(404, "Sample file missing — run scripts/generate_samples.py")
    doc = _create(db, user, path.read_bytes(), fname, declared, request, bg)
    return {"document": document_out(doc)}


@router.get("")
def list_documents(status: str | None = None, doc_type: str | None = None, q: str | None = None, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    query = select(MedicalDocument).where(MedicalDocument.user_id == user.id)
    if status:
        query = query.where(MedicalDocument.status.in_(status.split(",")))
    if doc_type:
        query = query.where(or_(MedicalDocument.detected_type == doc_type, MedicalDocument.declared_type == doc_type))
    if q:
        query = query.where(MedicalDocument.filename.ilike(f"%{q}%"))
    docs = db.scalars(query.order_by(MedicalDocument.created_at.desc()).limit(200)).all()
    return {"items": [document_out(d) for d in docs]}


def _owned(db: Session, user: User, doc_id: str) -> MedicalDocument:
    doc = db.get(MedicalDocument, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/{doc_id}")
def get_document(doc_id: str, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return {"document": document_out(_owned(db, user, doc_id), detail=True)}


@router.get("/{doc_id}/file")
def get_file(doc_id: str, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    doc = _owned(db, user, doc_id)
    data = get_storage().load(doc.storage_key)
    audit(db, "document.view_file", actor_id=user.id, resource_type="document", resource_id=doc.id, request=request, commit=True)
    return Response(content=data, media_type=doc.mime_type, headers={"Content-Disposition": f'inline; filename="{doc.filename}"', "Cache-Control": "private, no-store"})


@router.get("/{doc_id}/preview")
def preview(doc_id: str, page: int = 1, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    """First-page PNG preview — works in every browser (iOS Safari and headless included), unlike embedded PDFs."""
    import io

    from PIL import Image

    doc = _owned(db, user, doc_id)
    data = get_storage().load(doc.storage_key)
    if doc.mime_type == "application/pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        idx = max(0, min(page - 1, len(pdf) - 1))
        img = pdf[idx].render(scale=1.6).to_pil()
        pages = len(pdf)
    else:
        from PIL import ImageOps

        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        pages = 1
    img.thumbnail((1400, 1800))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=300", "X-Page-Count": str(pages)})


class ConfirmIn(BaseModel):
    type: Literal["lab_report", "prescription", "consultation_note", "diet_advice", "appointment", "other"]
    data: dict = {}
    options: dict = {}


@router.post("/{doc_id}/confirm")
def confirm(doc_id: str, body: ConfirmIn, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    doc = _owned(db, user, doc_id)
    if doc.status not in ("needs_review",):
        raise HTTPException(409, f"This document is {doc.status.replace('_', ' ')} and cannot be confirmed")
    result = commit_document(db, user, doc, body.model_dump())
    audit(db, "document.verify", actor_id=user.id, resource_type="document", resource_id=doc.id, meta={"type": body.type, **{k: v for k, v in result["created"].items() if not isinstance(v, (dict, list))}}, request=request)
    db.commit()
    return {"document": document_out(doc), "result": result}


@router.post("/{doc_id}/reprocess")
def reprocess(doc_id: str, bg: BackgroundTasks, request: Request, declared_type: str | None = None, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    doc = _owned(db, user, doc_id)
    if doc.status == "verified":
        raise HTTPException(409, "Verified documents cannot be reprocessed")
    if declared_type:
        if declared_type not in DOC_TYPES:
            raise HTTPException(422, "Unknown document type")
        doc.declared_type = declared_type
    doc.status = "uploaded"
    audit(db, "document.reprocess", actor_id=user.id, resource_type="document", resource_id=doc.id, request=request)
    db.commit()
    bg.add_task(process_document, doc.id)
    return {"document": document_out(doc)}


@router.post("/{doc_id}/reject")
def reject(doc_id: str, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    doc = _owned(db, user, doc_id)
    doc.status = "rejected"
    audit(db, "document.reject", actor_id=user.id, resource_type="document", resource_id=doc.id, request=request)
    db.commit()
    return {"document": document_out(doc)}


@router.delete("/{doc_id}")
def delete_document(doc_id: str, request: Request, user: User = Depends(require_patient), db: Session = Depends(get_db)):
    doc = _owned(db, user, doc_id)
    get_storage().delete(doc.storage_key)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
    db.delete(doc)
    audit(db, "document.delete", actor_id=user.id, resource_type="document", resource_id=doc_id, request=request)
    db.commit()
    return {"ok": True}
