"""Tests para app.crypto — encrypt/decrypt con Fernet."""
import pytest
from cryptography.fernet import InvalidToken


def test_encrypt_decrypt_roundtrip():
    from app.crypto import decrypt, encrypt
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    data = {"password": "secret123", "extra": 42}

    token = encrypt(data, key)
    assert isinstance(token, str)
    assert token != str(data)

    recovered = decrypt(token, key)
    assert recovered == data


def test_decrypt_wrong_key_raises():
    from app.crypto import decrypt, encrypt
    from cryptography.fernet import Fernet

    key1 = Fernet.generate_key().decode()
    key2 = Fernet.generate_key().decode()
    token = encrypt({"x": 1}, key1)

    with pytest.raises(InvalidToken):
        decrypt(token, key2)


def test_encrypt_returns_different_tokens_each_call():
    """Fernet usa nonce aleatorio — mismo input produce tokens distintos."""
    from app.crypto import encrypt
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    data = {"password": "pw"}
    assert encrypt(data, key) != encrypt(data, key)
