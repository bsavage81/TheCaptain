import socket
import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    original = socket.socket.connect
    def guarded(sock, address):
        # Windows asyncio constructs a local socketpair; allow only loopback.
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original(sock, address)
        raise AssertionError("External network prohibited in offline tests")
    monkeypatch.setattr(socket.socket, "connect", guarded)
    def denied(*args, **kwargs):
        raise AssertionError("External network prohibited in offline tests")
    monkeypatch.setattr(socket, "create_connection", denied)
