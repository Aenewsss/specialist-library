import { useState, type FormEvent } from 'react'
import type { Pessoa } from '../api'

const MIN_QUESTION_LENGTH = 3

interface SearchFormProps {
  pessoas: Pessoa[]
  selectedPessoaIds: string[]
  onTogglePessoa: (id: string) => void
  onSearch: (question: string) => void
  isSearching: boolean
  question: string
  onQuestionChange: (question: string) => void
}

export function SearchForm({
  pessoas,
  selectedPessoaIds,
  onTogglePessoa,
  onSearch,
  isSearching,
  question,
  onQuestionChange,
}: SearchFormProps) {
  const [touched, setTouched] = useState(false)
  const isTooShort = question.trim().length < MIN_QUESTION_LENGTH

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setTouched(true)
    if (!isTooShort) onSearch(question.trim())
  }

  return (
    <form className="search" onSubmit={handleSubmit} role="search">
      <label htmlFor="question" className="visually-hidden">
        Sua pergunta
      </label>
      <div className="search__box">
        <input
          id="question"
          className="search__input"
          type="search"
          placeholder="Pergunte algo, ex.: o dilúvio foi global ou local?"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          autoComplete="off"
          autoFocus
        />
        <button className="search__button" type="submit" disabled={isSearching}>
          {isSearching ? 'Buscando…' : 'Buscar'}
        </button>
      </div>
      {touched && isTooShort && <p className="search__hint">Escreva uma pergunta com pelo menos {MIN_QUESTION_LENGTH} letras.</p>}

      {pessoas.length > 0 && (
        <fieldset className="filters">
          <legend>Quem pode responder</legend>
          {pessoas.map((pessoa) => {
            const isSelected = selectedPessoaIds.includes(pessoa.id)
            return (
              <button
                key={pessoa.id}
                type="button"
                className={`chip${isSelected ? ' chip--selected' : ''}`}
                aria-pressed={isSelected}
                onClick={() => onTogglePessoa(pessoa.id)}
              >
                {pessoa.nome}
              </button>
            )
          })}
          {selectedPessoaIds.length === 0 && <span className="filters__all">todas as pessoas</span>}
        </fieldset>
      )}
    </form>
  )
}
