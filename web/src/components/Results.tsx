import type { Resposta } from '../api'
import { TrechoCard } from './TrechoCard'

export function Results({ resposta }: { resposta: Resposta }) {
  if (!resposta.encontrado) {
    return (
      <div className="notice">
        <p className="notice__title">Ninguém na biblioteca falou sobre isso.</p>
        <p>A biblioteca só mostra trechos em que alguém realmente fala do assunto. Tente perguntar de outro jeito.</p>
      </div>
    )
  }

  const total = resposta.resultados.reduce((sum, group) => sum + group.trechos.length, 0)
  return (
    <div className="results">
      <p className="results__summary">
        {total} {total === 1 ? 'trecho' : 'trechos'} de {resposta.resultados.length}{' '}
        {resposta.resultados.length === 1 ? 'pessoa' : 'pessoas'}
      </p>
      {resposta.resultados.map((group) => (
        <section key={group.pessoa.id} className="person" aria-labelledby={`pessoa-${group.pessoa.id}`}>
          <header className="person__header">
            <span className="person__avatar" aria-hidden="true">
              {initials(group.pessoa.nome)}
            </span>
            <div>
              <h2 id={`pessoa-${group.pessoa.id}`}>{group.pessoa.nome}</h2>
              {group.pessoa.areas.length > 0 && <p className="person__areas">{group.pessoa.areas.join(' · ')}</p>}
            </div>
          </header>
          {group.trechos.map((trecho) => (
            <TrechoCard key={trecho.trecho_id} trecho={trecho} />
          ))}
        </section>
      ))}
    </div>
  )
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}
