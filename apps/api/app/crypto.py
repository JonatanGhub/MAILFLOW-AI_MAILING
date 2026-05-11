"""Cifrado simétrico con Fernet para credenciales almacenadas en DB."""
from __future__ import annotations

import json

from cryptography.fernet import Fernet


def encrypt(data: dict, key: str) -> str:
    """Serializa dict a JSON, cifra con Fernet, devuelve token string."""
    return Fernet(key.encode()).encrypt(json.dumps(data).encode()).decode()


def decrypt(token: str, key: str) -> dict:
    """Descifra token Fernet, deserializa JSON, devuelve dict.

    Raises:
        cryptography.fernet.InvalidToken: si la clave es incorrecta o el token está corrupto.
    """
    return json.loads(Fernet(key.encode()).decrypt(token.encode()))
