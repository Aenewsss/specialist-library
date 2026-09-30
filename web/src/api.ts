export interface Pessoa {
  id: string
  nome: string
  areas: string[]
}

export interface Trecho {
  trecho_id: string
  texto: string
  conteudo_titulo: string | null
  publicado_em: string | null
  inicio_s: number | null
  fim_s: number | null
  link: string
  nota_reranker: number
}

export interface ResultadoPessoa {
  pessoa: Pessoa
  trechos: Trecho[]
}

export interface Resposta {
  pergunta: string
  encontrado: boolean
  resultados: ResultadoPessoa[]
  /** Só vem preenchido quando não há resposta direta: trechos de baixa confiança. */
  relacionados: ResultadoPessoa[]
}

export class ApiUnavailableError extends Error {}

const API_BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiUnavailableError('Não foi possível falar com a API.')
  }
  if (response.status >= 502) {
    throw new ApiUnavailableError('A API não está respondendo.')
  }
  if (!response.ok) {
    throw new Error(`Erro ${response.status} ao consultar a API.`)
  }
  return response.json() as Promise<T>
}

export function listPessoas(): Promise<Pessoa[]> {
  return request<Pessoa[]>('/pessoas')
}

export function ask(pergunta: string, pessoaIds: string[]): Promise<Resposta> {
  return request<Resposta>('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pergunta, pessoa_ids: pessoaIds }),
  })
}
