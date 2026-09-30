import { useEffect, useRef, useState } from 'react'
import { ApiUnavailableError, ask, listPessoas, type Pessoa, type Resposta } from '../api'
import { Results } from './Results'
import { SearchForm } from './SearchForm'

const EXAMPLE_QUESTIONS = [
  'O dilúvio foi global ou local?',
  'De onde veio a água da Terra?',
  'A Bíblia plagiou os mitos do dilúvio?',
]

type SearchState =
  | { status: 'idle' }
  | { status: 'searching' }
  | { status: 'done'; resposta: Resposta }
  | { status: 'error'; message: string }

export function SearchPage() {
  const [pessoas, setPessoas] = useState<Pessoa[]>([])
  const [selectedPessoaIds, setSelectedPessoaIds] = useState<string[]>([])
  const [question, setQuestion] = useState('')
  const [state, setState] = useState<SearchState>({ status: 'idle' })
  const latestSearch = useRef(0)

  useEffect(() => {
    listPessoas()
      .then(setPessoas)
      .catch(() => setPessoas([])) // sem filtro, a busca continua funcionando
  }, [])

  async function search(text: string) {
    const searchId = ++latestSearch.current
    setState({ status: 'searching' })
    try {
      const resposta = await ask(text, selectedPessoaIds)
      if (searchId === latestSearch.current) setState({ status: 'done', resposta })
    } catch (error) {
      if (searchId !== latestSearch.current) return
      const message =
        error instanceof ApiUnavailableError
          ? 'A API está fora do ar. Suba com `biblioteca serve` e tente de novo.'
          : 'Algo deu errado na busca. Tente de novo.'
      setState({ status: 'error', message })
    }
  }

  function togglePessoa(id: string) {
    setSelectedPessoaIds((ids) => (ids.includes(id) ? ids.filter((other) => other !== id) : [...ids, id]))
  }

  function searchExample(example: string) {
    setQuestion(example)
    search(example)
  }

  return (
    <>
      <SearchForm
        pessoas={pessoas}
        selectedPessoaIds={selectedPessoaIds}
        onTogglePessoa={togglePessoa}
        onSearch={search}
        isSearching={state.status === 'searching'}
        question={question}
        onQuestionChange={setQuestion}
      />

      <div aria-live="polite" aria-busy={state.status === 'searching'}>
        {state.status === 'idle' && (
          <div className="examples">
            <p>Experimente:</p>
            {EXAMPLE_QUESTIONS.map((example) => (
              <button key={example} type="button" className="example" onClick={() => searchExample(example)}>
                {example}
              </button>
            ))}
          </div>
        )}
        {state.status === 'searching' && <LoadingSkeleton />}
        {state.status === 'error' && (
          <div className="notice notice--error" role="alert">
            <p className="notice__title">{state.message}</p>
          </div>
        )}
        {state.status === 'done' && <Results resposta={state.resposta} />}
      </div>
    </>
  )
}

function LoadingSkeleton() {
  return (
    <div className="skeleton" aria-label="Buscando trechos">
      {[0, 1, 2].map((index) => (
        <div key={index} className="skeleton__card" />
      ))}
    </div>
  )
}
