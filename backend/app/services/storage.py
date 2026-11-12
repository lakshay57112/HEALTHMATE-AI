"""Protected document storage: files are encrypted with Fernet before touching disk.

Swap `LocalEncryptedStorage` for an S3/GCS implementation with server-side encryption in production.
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


def get_storage() -> LocalEncryptedStorage:
    return LocalEncryptedStorage(get_settings().data_dir / "documents")
