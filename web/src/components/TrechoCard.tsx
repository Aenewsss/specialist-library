import { useState } from 'react'
import type { Trecho } from '../api'
import { formatDate, formatTimestamp, parseYoutubeLink } from '../format'
import { YoutubePlayer } from './YoutubePlayer'

export function TrechoCard({ trecho, lowConfidence = false }: { trecho: Trecho; lowConfidence?: boolean }) {
  const [isPlayerOpen, setPlayerOpen] = useState(false)
  const youtube = parseYoutubeLink(trecho.link)
  const timestamp = trecho.inicio_s !== null ? formatTimestamp(trecho.inicio_s) : null

  return (
    <article className={`trecho${lowConfidence ? ' trecho--low' : ''}`}>
      <blockquote className="trecho__quote">
        <p>“{trecho.texto}”</p>
      </blockquote>

      <div className="trecho__meta">
        <span className="trecho__source">{trecho.conteudo_titulo ?? 'Fonte sem título'}</span>
        {trecho.publicado_em && <time dateTime={trecho.publicado_em}>{formatDate(trecho.publicado_em)}</time>}
        <Relevance score={trecho.nota_reranker} />
      </div>

      <div className="trecho__actions">
        <a className="link-button" href={trecho.link} target="_blank" rel="noreferrer">
          {timestamp ? `Abrir no YouTube em ${timestamp}` : 'Abrir a fonte'} ↗
        </a>
        {youtube && (
          <button type="button" className="link-button link-button--ghost" onClick={() => setPlayerOpen((open) => !open)}>
            {isPlayerOpen ? 'Fechar vídeo' : 'Assistir aqui'}
          </button>
        )}
      </div>

      {youtube && isPlayerOpen && (
        <YoutubePlayer position={youtube} title={`${trecho.conteudo_titulo ?? 'Vídeo'} a partir de ${timestamp}`} />
      )}
    </article>
  )
}

function Relevance({ score }: { score: number }) {
  const percent = Math.round(score * 100)
  return (
    <span className="relevance" title="Nota do reranker: o quanto o trecho responde à pergunta">
      <span className="relevance__bar" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </span>
      {percent}% relevante
    </span>
  )
}
