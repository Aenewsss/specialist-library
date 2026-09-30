import pytest

from app import client


def test_clear_error_when_api_is_not_running():
    with pytest.raises(client.ApiUnavailable, match="biblioteca serve"):
        client.ask("http://127.0.0.1:1", "pergunta?", [])
