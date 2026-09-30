import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { addVideo, InvalidRequestError, listVideos, retryVideo, type Video } from '../api'
import { formatDate } from '../format'

const POLL_WHILE_PROCESSING_MS = 3000

export function VideosPage() {
  const [videos, setVideos] = useState<Video[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [url, setUrl] = useState('')
  const [isAdding, setAdding] = useState(false)
  const [formMessage, setFormMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  const refresh = useCallback(async () => {
    try {
      setVideos(await listVideos())
      setLoadError(null)
    } catch {
      setLoadError('Não foi possível carregar os vídeos. Confira se a API está no ar.')
    }
  }, [])

  useEffect(() => {
    let isActive = true
    listVideos()
      .then((list) => isActive && setVideos(list))
      .catch(() => isActive && setLoadError('Não foi possível carregar os vídeos. Confira se a API está no ar.'))
    return () => {
      isActive = false
    }
  }, [])

  const isProcessing = videos?.some((video) => video.status === 'na_fila' || video.status === 'processando') ?? false

  useEffect(() => {
    if (!isProcessing) return
    const timer = window.setInterval(refresh, POLL_WHILE_PROCESSING_MS)
    return () => window.clearInterval(timer)
  }, [isProcessing, refresh])

  async function handleAdd(event: FormEvent) {
    event.preventDefault()
    const trimmed = url.trim()
    if (!trimmed) return
    setAdding(true)
    setFormMessage(null)
    try {
      const { novo } = await addVideo(trimmed)
      setUrl('')
      setFormMessage(
        novo
          ? { kind: 'ok', text: 'Vídeo adicionado. O processamento começa em instantes.' }
          : { kind: 'ok', text: 'Esse vídeo já estava na biblioteca.' },
      )
      await refresh()
    } catch (error) {
      const text = error instanceof InvalidRequestError ? error.message : 'Não foi possível adicionar. Tente de novo.'
      setFormMessage({ kind: 'error', text })
    } finally {
      setAdding(false)
    }
  }

  async function handleRetry(video: Video) {
    await retryVideo(video.conteudo_id).catch(() => undefined)
    await refresh()
  }

  return (
    <section className="videos" aria-labelledby="videos-title">
      <header className="review__intro">
        <h2 id="videos-title">Vídeos</h2>
        <p>
          Cole o link de um vídeo do YouTube. A biblioteca baixa a legenda, separa as vozes, reconhece quem já conhece e
          deixa os trechos prontos para a busca.
        </p>
      </header>

      <form className="add-video" onSubmit={handleAdd}>
        <label htmlFor="video-url" className="visually-hidden">
          Link do vídeo
        </label>
        <input
          id="video-url"
          type="url"
          inputMode="url"
          placeholder="https://www.youtube.com/watch?v=…"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          disabled={isAdding}
        />
        <button type="submit" className="button-primary" disabled={isAdding || !url.trim()}>
          {isAdding ? 'Adicionando…' : 'Adicionar vídeo'}
        </button>
      </form>
      <div aria-live="polite">
        {formMessage && (
          <p className={`form-message form-message--${formMessage.kind}`}>{formMessage.text}</p>
        )}
      </div>

      {loadError && (
        <div className="notice notice--error" role="alert">
          <p className="notice__title">{loadError}</p>
        </div>
      )}
      {videos === null && !loadError && <div className="skeleton"><div className="skeleton__card" /></div>}
      {videos?.length === 0 && (
        <div className="notice">
          <p className="notice__title">Nenhum vídeo ainda.</p>
          <p>Adicione o primeiro pelo campo acima.</p>
        </div>
      )}

      <ul className="video-list">
        {videos?.map((video) => (
          <VideoRow key={video.conteudo_id} video={video} onRetry={() => handleRetry(video)} />
        ))}
      </ul>
    </section>
  )
}

function VideoRow({ video, onRetry }: { video: Video; onRetry: () => void }) {
  return (
    <li className="video-row">
      <div className="video-row__main">
        <a className="video-row__title" href={video.url} target="_blank" rel="noreferrer">
          {video.titulo ?? video.url}
        </a>
        <p className="video-row__meta">
          {video.publicado_em ? `Publicado em ${formatDate(video.publicado_em)}` : 'Data ainda não disponível'}
        </p>
        {video.status === 'pronto' && <ReadySummary video={video} />}
        {video.status === 'erro' && (
          <p className="video-row__error">
            Falhou em “{video.etapa_atual_descricao}”: {video.erro}{' '}
            <button type="button" className="voice__ignore" onClick={onRetry}>
              Tentar de novo
            </button>
          </p>
        )}
      </div>
      <StatusBadge video={video} />
    </li>
  )
}

function ReadySummary({ video }: { video: Video }) {
  return (
    <p className="video-row__summary">
      {video.trechos} trechos
      {video.pessoas.length > 0 && <> · {video.pessoas.join(', ')}</>}
      {video.vozes_pendentes > 0 && (
        <>
          {' · '}
          <a href="#vozes" className="video-row__pending">
            {video.vozes_pendentes} {video.vozes_pendentes === 1 ? 'voz sem autor' : 'vozes sem autor'}
          </a>
        </>
      )}
    </p>
  )
}

function StatusBadge({ video }: { video: Video }) {
  if (video.status === 'pronto') return <span className="status status--ok">Pronto</span>
  if (video.status === 'erro') return <span className="status status--error">Erro</span>
  if (video.status === 'na_fila') return <span className="status">Na fila</span>
  return (
    <span className="status status--running" title={video.etapa_atual_descricao ?? undefined}>
      {video.etapa_atual_descricao}… {video.etapas_concluidas}/{video.total_etapas}
    </span>
  )
}
