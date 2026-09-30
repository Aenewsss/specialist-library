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

export interface PessoaCadastro {
  id: string
  nome: string
  bio_curta: string | null
}

export interface AmostraVoz {
  inicio_s: number
  texto: string
  link: string
}

export interface VozPendente {
  conteudo_id: string
  rotulo: string
  segundos_fala: number
  conteudo_titulo: string | null
  publicado_em: string | null
  amostras: AmostraVoz[]
}

export function listAllPessoas(): Promise<PessoaCadastro[]> {
  return request<PessoaCadastro[]>('/pessoas?todas=true')
}

export function createPessoa(nome: string, bioCurta: string | null): Promise<PessoaCadastro> {
  return request<PessoaCadastro>('/pessoas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nome, bio_curta: bioCurta }),
  })
}

export function listPendingVoices(): Promise<VozPendente[]> {
  return request<VozPendente[]>('/falantes/pendentes')
}

function voicePath(voz: VozPendente, action: string): string {
  return `/falantes/${voz.conteudo_id}/${encodeURIComponent(voz.rotulo)}/${action}`
}

export function confirmVoice(voz: VozPendente, pessoaId: string): Promise<{ outras_vozes_reconhecidas: number }> {
  return request(voicePath(voz, 'confirmar'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pessoa_id: pessoaId }),
  })
}

export function ignoreVoice(voz: VozPendente): Promise<{ trechos_removidos: number }> {
  return request(voicePath(voz, 'ignorar'), { method: 'POST' })
}

export function ask(pergunta: string, pessoaIds: string[]): Promise<Resposta> {
  return request<Resposta>('/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pergunta, pessoa_ids: pessoaIds }),
  })
}

export type VideoStatus = 'na_fila' | 'processando' | 'pronto' | 'erro'

export interface Video {
  conteudo_id: string
  video_id: string | null
  titulo: string | null
  publicado_em: string | null
  url: string
  status: VideoStatus
  etapa_atual: string | null
  etapa_atual_descricao: string | null
  etapas_concluidas: number
  total_etapas: number
  erro: string | null
  trechos: number
  pessoas: string[]
  vozes_pendentes: number
}

export class InvalidRequestError extends Error {}

export function listVideos(): Promise<Video[]> {
  return request<Video[]>('/videos')
}

export async function addVideo(url: string): Promise<{ conteudo_id: string; novo: boolean }> {
  const response = await fetch(`${API_BASE}/videos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  }).catch(() => {
    throw new ApiUnavailableError('Não foi possível falar com a API.')
  })
  if (response.status === 400 || response.status === 422) {
    throw new InvalidRequestError('Esse link não parece ser de um vídeo do YouTube.')
  }
  if (!response.ok) throw new Error(`Erro ${response.status} ao adicionar o vídeo.`)
  return response.json()
}

export function retryVideo(conteudoId: string): Promise<{ reiniciado_em: string }> {
  return request(`/videos/${conteudoId}/tentar-de-novo`, { method: 'POST' })
}
