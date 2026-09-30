import { useState, type FormEvent } from 'react'
import type { PessoaCadastro, VozPendente } from '../api'
import { formatDate, formatTimestamp, parseYoutubeLink } from '../format'
import { YoutubePlayer } from './YoutubePlayer'

const NEW_PESSOA = '__nova__'

export interface VoiceDecision {
  pessoaId: string | null
  newPessoaName: string | null
}

interface VoiceCardProps {
  voz: VozPendente
  pessoas: PessoaCadastro[]
  isBusy: boolean
  onConfirm: (decision: VoiceDecision) => void
  onIgnore: () => void
}

export function VoiceCard({ voz, pessoas, isBusy, onConfirm, onIgnore }: VoiceCardProps) {
  const [choice, setChoice] = useState('')
  const [newName, setNewName] = useState('')
  const [openSample, setOpenSample] = useState<number | null>(null)
  const idPrefix = `${voz.conteudo_id}-${voz.rotulo}`
  const isNew = choice === NEW_PESSOA
  const canConfirm = isNew ? newName.trim().length >= 2 : choice !== ''

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!canConfirm) return
    onConfirm({ pessoaId: isNew ? null : choice, newPessoaName: isNew ? newName.trim() : null })
  }

  return (
    <article className="voice">
      <header className="voice__header">
        <div className="voice__title">
          <h2>{voz.conteudo_titulo ?? 'Vídeo sem título'}</h2>
          <p>
            Voz <code>{voz.rotulo}</code> · {formatDuration(voz.segundos_fala)} de fala
            {voz.publicado_em && <> · {formatDate(voz.publicado_em)}</>}
          </p>
        </div>
      </header>

      <ol className="voice__samples">
        {voz.amostras.map((amostra, index) => {
          const youtube = parseYoutubeLink(amostra.link)
          const isOpen = openSample === index
          return (
            <li key={amostra.inicio_s} className="sample">
              <div className="sample__row">
                <span className="sample__time">{formatTimestamp(amostra.inicio_s)}</span>
                <p className="sample__text">“{amostra.texto}”</p>
                {youtube && (
                  <button
                    type="button"
                    className="link-button link-button--ghost sample__listen"
                    aria-expanded={isOpen}
                    onClick={() => setOpenSample(isOpen ? null : index)}
                  >
                    {isOpen ? 'Fechar' : 'Ouvir'}
                  </button>
                )}
              </div>
              {youtube && isOpen && (
                <YoutubePlayer position={youtube} title={`Amostra da voz ${voz.rotulo} em ${formatTimestamp(amostra.inicio_s)}`} />
              )}
            </li>
          )
        })}
      </ol>

      <form className="voice__form" onSubmit={handleSubmit}>
        <label htmlFor={`${idPrefix}-pessoa`}>De quem é esta voz?</label>
        <div className="voice__controls">
          <select
            id={`${idPrefix}-pessoa`}
            value={choice}
            onChange={(event) => setChoice(event.target.value)}
            disabled={isBusy}
          >
            <option value="">Escolha uma pessoa…</option>
            {pessoas.map((pessoa) => (
              <option key={pessoa.id} value={pessoa.id}>
                {pessoa.nome}
              </option>
            ))}
            <option value={NEW_PESSOA}>+ Cadastrar nova pessoa</option>
          </select>
          {isNew && (
            <input
              id={`${idPrefix}-nova`}
              aria-label="Nome da nova pessoa"
              placeholder="Nome da pessoa"
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              disabled={isBusy}
              autoFocus
            />
          )}
          <button type="submit" className="button-primary" disabled={!canConfirm || isBusy}>
            Confirmar
          </button>
        </div>
        <button type="button" className="voice__ignore" onClick={onIgnore} disabled={isBusy}>
          Não é ninguém da biblioteca (apresentador, narrador…): ignorar esta voz
        </button>
      </form>
    </article>
  )
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`
  return `${Math.floor(seconds / 60)} min ${String(Math.round(seconds % 60)).padStart(2, '0')} s`
}
