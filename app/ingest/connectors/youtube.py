import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL

from app.ingest.models import ContentMetadata

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
SHORT_HOSTS = {"youtu.be"}
LONG_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
YDL_BASE_OPTIONS = {"quiet": True, "no_warnings": True}


class InvalidYoutubeUrl(ValueError):
    pass


def extract_video_id(url: str) -> str:
    """Aceita watch?v=, youtu.be/, /shorts/, /live/ e /embed/."""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    candidate = None
    if host in SHORT_HOSTS:
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in LONG_HOSTS:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
                candidate = parts[1]
    if not candidate or not VIDEO_ID_PATTERN.match(candidate):
        raise InvalidYoutubeUrl(f"URL de vídeo do YouTube inválida: {url}")
    return candidate


def canonical_video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


class YoutubeConnector:
    def fetch_metadata(self, external_id: str) -> ContentMetadata:
        info = self._extract_info(external_id)
        upload_date = info.get("upload_date")
        published_on = datetime.strptime(upload_date, "%Y%m%d").date() if upload_date else None
        return ContentMetadata(title=info["title"], published_on=published_on)

    def download_audio(self, external_id: str, target_dir: Path) -> Path:
        """Áudio em WAV mono 16 kHz, formato que diarização e Whisper consomem. Reaproveita se já existir."""
        target = target_dir / f"{external_id}.wav"
        if target.exists():
            return target
        target_dir.mkdir(parents=True, exist_ok=True)
        options = {
            **YDL_BASE_OPTIONS,
            "format": "bestaudio",
            "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
            "postprocessor_args": {"extractaudio": ["-ac", "1", "-ar", "16000"]},
        }
        with YoutubeDL(options) as ydl:
            ydl.download([canonical_video_url(external_id)])
        return target

    def _extract_info(self, external_id: str) -> dict:
        with YoutubeDL({**YDL_BASE_OPTIONS, "skip_download": True}) as ydl:
            return ydl.extract_info(canonical_video_url(external_id), download=False)
