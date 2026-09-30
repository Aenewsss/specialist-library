"""Cliente HTTP da API: o CLI pergunta ao servidor, que já está com os modelos carregados."""
from uuid import UUID

import httpx

ASK_TIMEOUT_S = 60


class ApiUnavailable(ConnectionError):
    pass


def ask(api_url: str, question: str, pessoa_ids: list[UUID]) -> dict:
    payload = {"pergunta": question, "pessoa_ids": [str(pessoa_id) for pessoa_id in pessoa_ids]}
    try:
        response = httpx.post(f"{api_url}/ask", json=payload, timeout=ASK_TIMEOUT_S)
    except httpx.ConnectError as error:
        raise ApiUnavailable(f"API fora do ar em {api_url}. Suba com `biblioteca serve`.") from error
    response.raise_for_status()
    return response.json()
