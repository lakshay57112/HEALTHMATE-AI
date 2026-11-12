"""Generate VAPID keys for Web Push. Paste the output into your .env.

    python scripts/generate_vapid_keys.py
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

key = ec.generate_private_key(ec.SECP256R1())
priv = key.private_numbers().private_value.to_bytes(32, "big")
pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")  # noqa: E731
print(f"VAPID_PUBLIC_KEY={b64(pub)}")
print(f"VAPID_PRIVATE_KEY={b64(priv)}")
