"""Protected document storage: files are encrypted with Fernet before they are stored.

Backends: local disk (default) or Postgres (STORAGE_BACKEND=db, for hosts without persistent disks).
Swap in an S3/GCS implementation with server-side encryption for larger deployments.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.crypto import decrypt_bytes, encrypt_bytes


class LocalEncryptedStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, user_id: str, data: bytes) -> tuple[str, str]:
        sha = hashlib.sha256(data).hexdigest()
        key = f"{user_id}/{uuid.uuid4().hex}.bin"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encrypt_bytes(data))
        path.chmod(0o600)
        return key, sha

    def load(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise PermissionError("Invalid storage key")
        return decrypt_bytes(path.read_bytes())

    def delete(self, key: str) -> None:
        path = (self.root / key).resolve()
        if str(path).startswith(str(self.root.resolve())) and path.exists():
            path.unlink()


class DbEncryptedStorage:
    """Stores encrypted bytes in the document_blobs table (own session, so it works from background tasks too)."""

    def save(self, user_id: str, data: bytes) -> tuple[str, str]:
        from app.db.session import SessionLocal
        from app.models import DocumentBlob

        sha = hashlib.sha256(data).hexdigest()
        key = f"db:{user_id}/{uuid.uuid4().hex}"
        with SessionLocal() as db:
            db.add(DocumentBlob(key=key, data=encrypt_bytes(data)))
            db.commit()
        return key, sha

    def load(self, key: str) -> bytes:
        from app.db.session import SessionLocal
        from app.models import DocumentBlob

        with SessionLocal() as db:
            blob = db.get(DocumentBlob, key)
            if not blob:
                raise FileNotFoundError(key)
            return decrypt_bytes(blob.data)

    def delete(self, key: str) -> None:
        from app.db.session import SessionLocal
        from app.models import DocumentBlob

        with SessionLocal() as db:
            blob = db.get(DocumentBlob, key)
            if blob:
                db.delete(blob)
                db.commit()


def get_storage(key: str | None = None) -> LocalEncryptedStorage | DbEncryptedStorage:
    if (key and key.startswith("db:")) or (key is None and get_settings().storage_backend == "db"):
        return DbEncryptedStorage()
    return LocalEncryptedStorage(get_settings().data_dir / "documents")


def load_file(key: str) -> bytes:
    return get_storage(key).load(key)


def delete_file(key: str) -> None:
    get_storage(key).delete(key)
