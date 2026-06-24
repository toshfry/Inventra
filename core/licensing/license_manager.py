"""
Inventra Offline Activation / License Manager

Security design:
- The client app contains only the PUBLIC verification key.
- The developer generator contains the PRIVATE signing key.
- A license key is locked to the client's Computer ID.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os
import platform
import socket
import uuid
from typing import Any, Dict, Optional, Tuple

from config.settings import DATA_DIR

PRODUCT_NAME = "Inventra"
LICENSE_FILE = os.path.join(DATA_DIR, "license.json")

# Public key only. Keep the private key only in your developer generator.
PUBLIC_KEY_B64 = "p1osPkV6qteFKtRCSENIacNVbRZvEihbl7lLPkBK9v0="


def _b64url_decode(value: str) -> bytes:
    value = "".join(str(value or "").strip().split())
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _canonical_json(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _get_windows_machine_guid() -> str:
    if platform.system().lower() != "windows":
        return ""

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value or "").strip()
    except Exception:
        return ""


def _safe_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return platform.node()


def _mac_address() -> str:
    try:
        mac = uuid.getnode()
        return f"{mac:012X}"
    except Exception:
        return ""


def get_computer_id() -> str:
    """
    Stable public Computer ID shown to the client.

    The raw machine details are never shown. We hash them and display only
    short groups, for example: A1B2-C3D4-E5F6-7788-99AA.
    """
    raw_parts = [
        PRODUCT_NAME,
        platform.system(),
        platform.machine(),
        _safe_hostname(),
        _mac_address(),
        _get_windows_machine_guid(),
    ]
    raw = "|".join(str(x or "").strip().lower() for x in raw_parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()[:20]
    return "-".join(digest[i:i + 4] for i in range(0, len(digest), 4))


def decode_activation_key(activation_key: str) -> Dict[str, Any]:
    key = "".join(str(activation_key or "").strip().split())

    if key.upper().startswith("INVENTRA-"):
        key = key[len("INVENTRA-"):]

    raw = _b64url_decode(key)
    data = json.loads(raw.decode("utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Invalid activation key format.")

    return data


def _load_public_key():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        raw = base64.b64decode(PUBLIC_KEY_B64.encode("ascii"))
        return Ed25519PublicKey.from_public_bytes(raw)
    except ImportError as exc:
        raise RuntimeError(
            "Missing cryptography package. Run: pip install cryptography"
        ) from exc


def validate_license_data(license_data: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    try:
        payload = license_data.get("payload")
        signature_b64 = license_data.get("signature")

        if not isinstance(payload, dict) or not signature_b64:
            return False, "Invalid license file format.", None

        signature = base64.b64decode(signature_b64.encode("ascii"))
        public_key = _load_public_key()
        public_key.verify(signature, _canonical_json(payload))

        if payload.get("product") != PRODUCT_NAME:
            return False, "This license is not for Inventra.", payload

        licensed_computer_id = str(payload.get("computer_id") or "").strip().upper()
        current_computer_id = get_computer_id().upper()

        if licensed_computer_id != current_computer_id:
            return (
                False,
                "This license key is for another computer.",
                payload,
            )

        expires_on = payload.get("expires_on")
        if expires_on:
            expiry = _dt.date.fromisoformat(str(expires_on))
            today = _dt.date.today()
            if today > expiry:
                return False, f"This license expired on {expires_on}.", payload

        return True, "Inventra is activated.", payload

    except Exception as exc:
        return False, f"Invalid license: {exc}", None


def validate_license() -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    if not os.path.exists(LICENSE_FILE):
        return False, "Inventra is not activated.", None

    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            license_data = json.load(f)
    except Exception as exc:
        return False, f"Cannot read license file: {exc}", None

    return validate_license_data(license_data)


def is_activated() -> bool:
    valid, _, _ = validate_license()
    return valid


def activate_from_key(activation_key: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    try:
        license_data = decode_activation_key(activation_key)
        valid, message, payload = validate_license_data(license_data)

        if not valid:
            return False, message, payload

        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(license_data, f, indent=2, ensure_ascii=False)

        return True, "Activation successful.", payload

    except Exception as exc:
        return False, f"Activation failed: {exc}", None


def license_status() -> Dict[str, Any]:
    valid, message, payload = validate_license()

    status = {
        "activated": valid,
        "message": message,
        "computer_id": get_computer_id(),
        "license_file": LICENSE_FILE,
    }

    if payload:
        status.update({
            "business_name": payload.get("business_name"),
            "owner_name": payload.get("owner_name"),
            "license_type": payload.get("license_type"),
            "issued_at": payload.get("issued_at"),
            "expires_on": payload.get("expires_on"),
        })

    return status
