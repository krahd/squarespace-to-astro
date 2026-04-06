import s2a.net as net


def test_build_client_passes_verify_setting(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class DummyClient:
        def __init__(self, **kwargs) -> None:
            calls.update(kwargs)

    monkeypatch.setattr(net.httpx, "Client", DummyClient)

    client = net.build_client(5.0, verify=False)

    assert isinstance(client, DummyClient)
    assert calls["verify"] is False
    assert calls["follow_redirects"] is True