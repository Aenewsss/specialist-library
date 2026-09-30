import subprocess
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000


def load_mono_16k(path: Path) -> np.ndarray:
    """Decodifica com ffmpeg direto para float32 mono 16 kHz (evita depender do torchcodec)."""
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"]
    raw = subprocess.run(command, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()
