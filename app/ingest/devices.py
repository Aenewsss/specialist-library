import torch


def resolve_device(preference: str) -> str:
    """'auto' escolhe cuda > mps > cpu; qualquer outro valor é respeitado."""
    if preference != "auto":
        return preference
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
