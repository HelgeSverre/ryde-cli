import os
import socket

import pytest


@pytest.fixture(autouse=True)
def isolated_account(monkeypatch, tmp_path):
    """Never inherit a developer's login or accidentally contact the real API."""
    for key in list(os.environ):
        if key.startswith("RYDE_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("RYDE_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1"}:
            raise AssertionError("Tests may only connect to loopback servers")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
