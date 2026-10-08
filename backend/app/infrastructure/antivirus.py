"""ClamAV INSTREAM privé, borné, sans fichier temporaire ni fail-open."""

from __future__ import annotations

import ipaddress
import socket
import struct

from fastapi import HTTPException


def scan_upload(data: bytes, settings) -> dict:
    if not settings.av_scan_enabled:
        return {"status": "not_enabled", "engine": None}
    try:
        addresses = socket.getaddrinfo(settings.av_host, settings.av_port, type=socket.SOCK_STREAM)
        if not addresses or any(
            not ipaddress.ip_address(item[4][0]).is_private for item in addresses
        ):
            raise OSError("PRIVATE_AV_REQUIRED")
        # La connexion utilise l'adresse vérifiée, sans seconde résolution DNS.
        family, kind, proto, _, address = addresses[0]
        with socket.socket(family, kind, proto) as connection:
            connection.settimeout(settings.av_timeout_seconds)
            connection.connect(address)
            connection.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), 65536):
                chunk = data[start : start + 65536]
                connection.sendall(struct.pack("!I", len(chunk)) + chunk)
            connection.sendall(struct.pack("!I", 0))
            response = bytearray()
            while b"\0" not in response and len(response) < 4096:
                part = connection.recv(1024)
                if not part:
                    break
                response.extend(part)
        result = bytes(response).split(b"\0", 1)[0]
        if result.endswith(b" FOUND"):
            raise HTTPException(
                422,
                detail={"code": "MALWARE_DETECTED", "message": "Fichier refusé par l'antivirus"},
            )
        if result != b"stream: OK":
            raise OSError("AV_INVALID_RESPONSE")
        return {"status": "clean", "engine": "clamav_instream"}
    except HTTPException:
        raise
    except (OSError, ValueError):
        raise HTTPException(
            503,
            detail={
                "code": "ANTIVIRUS_UNAVAILABLE",
                "message": "Contrôle antivirus impossible : upload bloqué",
            },
        ) from None
