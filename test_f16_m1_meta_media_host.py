"""F16-M1 regression: Meta media download must hit the real Graph API host.

Prior bug: get_meta_media_download_url() built its URL against
graph.instagram.com, which is not a valid host for the WhatsApp Business
Cloud API and caused 100% Meta media ingestion failure. This test mocks only
the network call (requests.get), not get_meta_media_download_url() itself,
so it fails again if the wrong host is reintroduced.
"""

from unittest.mock import MagicMock, patch

from meta_whatsapp_media_adapter import get_meta_media_download_url


def test_get_meta_media_download_url_uses_graph_facebook_host():
    mock_response = MagicMock()
    mock_response.json.return_value = {"url": "https://lookaside.example/media"}
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response) as mock_get:
        result = get_meta_media_download_url("media-123", "token-abc")

    assert result == "https://lookaside.example/media"
    assert mock_get.call_count == 1
    called_url = mock_get.call_args.args[0]
    assert called_url.startswith("https://graph.facebook.com/")
    assert "graph.instagram.com" not in called_url
    assert "/v19." in called_url
    assert called_url.endswith("/media-123")


def test_get_meta_media_download_url_returns_none_on_request_failure():
    with patch("requests.get", side_effect=RuntimeError("network down")):
        result = get_meta_media_download_url("media-123", "token-abc")

    assert result is None


if __name__ == "__main__":
    test_get_meta_media_download_url_uses_graph_facebook_host()
    test_get_meta_media_download_url_returns_none_on_request_failure()
    print("test_f16_m1_meta_media_host.py self-test OK")
