import type { ResultadoPessoa, Resposta } from '../api'
import { TrechoCard } from './TrechoCard'

export function Results({ resposta }: { resposta: Resposta }) {
  if (resposta.encontrado) {
    return (
      <div className="results">
        <p className="results__summary">{summary(resposta.resultados)}</p>
        <PersonGroups groups={resposta.resultados} />
      </div>
    )
  }

  if (resposta.relacionados?.length) {
    return (
      <div className="results results--related">
        <div className="notice notice--related">
          <p className="notice__title">Nenhuma resposta direta para essa pergunta.</p>
          <p>
            Estes trechos podem estar relacionados, mas a confiança é baixa. Confira no vídeo antes de concluir o que a pessoa
            pensa, ou tente perguntar com outras palavras.
          </p>
        </div>
        <PersonGroups groups={resposta.relacionados} lowConfidence />
      </div>
    )
  }

  return (
    <div className="notice">
      <p className="notice__title">Ninguém na biblioteca falou sobre isso.</p>
      <p>A biblioteca só mostra trechos em que alguém realmente fala do assunto. Tente perguntar de outro jeito.</p>
    </div>
  )
}

function summary(groups: ResultadoPessoa[]): string {
  const total = groups.reduce((sum, group) => sum + group.trechos.length, 0)
  return `${total} ${total === 1 ? 'trecho' : 'trechos'} de ${groups.length} ${groups.length === 1 ? 'pessoa' : 'pessoas'}`
}

function PersonGroups({ groups, lowConfidence = false }: { groups: ResultadoPessoa[]; lowConfidence?: boolean }) {
  return (
    <>
      {groups.map((group) => (
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
            <TrechoCard key={trecho.trecho_id} trecho={trecho} lowConfidence={lowConfidence} />
          ))}
        </section>
      ))}
    </>
  )
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/)
  return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}
