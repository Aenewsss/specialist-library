import pytest

from app.ingest.connectors.youtube import InvalidYoutubeUrl, extract_video_id


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=qgikRaQkPGU",
        "https://youtube.com/watch?v=qgikRaQkPGU&t=42s",
        "https://youtu.be/qgikRaQkPGU?si=abc",
        "https://www.youtube.com/shorts/qgikRaQkPGU",
        "https://www.youtube.com/live/qgikRaQkPGU",
        "https://m.youtube.com/watch?v=qgikRaQkPGU",
    ],
)
def test_extracts_video_id_from_supported_formats(url):
    assert extract_video_id(url) == "qgikRaQkPGU"


@pytest.mark.parametrize(
    "url",
    ["https://vimeo.com/123", "https://www.youtube.com/watch?v=curto", "https://www.youtube.com/@canal", ""],
)
def test_rejects_invalid_urls(url):
    with pytest.raises(InvalidYoutubeUrl):
        extract_video_id(url)
