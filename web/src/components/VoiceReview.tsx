import { useCallback, useEffect, useState } from 'react'
import {
  confirmVoice,
  createPessoa,
  ignoreVoice,
  listAllPessoas,
  listPendingVoices,
  type PessoaCadastro,
  type VozPendente,
} from '../api'
import { VoiceCard, type VoiceDecision } from './VoiceCard'

const LOAD_ERROR = 'Não foi possível carregar as vozes. Confira se a API está no ar.'

interface ReviewData {
  pending: VozPendente[]
  cadastro: PessoaCadastro[]
}

async function fetchReviewData(): Promise<ReviewData> {
  const [pending, cadastro] = await Promise.all([listPendingVoices(), listAllPessoas()])
  return { pending, cadastro }
}

type LoadState = { status: 'loading' } | { status: 'ready' } | { status: 'error'; message: string }

interface VoiceReviewProps {
  onPendingCountChange: (count: number) => void
}

export function VoiceReview({ onPendingCountChange }: VoiceReviewProps) {
  const [vozes, setVozes] = useState<VozPendente[]>([])
  const [pessoas, setPessoas] = useState<PessoaCadastro[]>([])
  const [load, setLoad] = useState<LoadState>({ status: 'loading' })
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)

  const apply = useCallback(
    ({ pending, cadastro }: ReviewData) => {
      setVozes(pending)
      setPessoas(cadastro)
      onPendingCountChange(pending.length)
      setLoad({ status: 'ready' })
    },
    [onPendingCountChange],
  )

  useEffect(() => {
    let isActive = true
    fetchReviewData()
      .then((data) => isActive && apply(data))
      .catch(() => isActive && setLoad({ status: 'error', message: LOAD_ERROR }))
    return () => {
      isActive = false
    }
  }, [apply])

  async function refresh() {
    try {
      apply(await fetchReviewData())
    } catch {
      setLoad({ status: 'error', message: LOAD_ERROR })
    }
  }

  async function run(voz: VozPendente, action: () => Promise<string>) {
    setBusyKey(keyOf(voz))
    setFeedback(null)
    try {
      setFeedback(await action())
      await refresh()
    } catch {
      setFeedback('Não foi possível salvar. Tente de novo.')
    } finally {
      setBusyKey(null)
    }
  }

  function handleConfirm(voz: VozPendente, decision: VoiceDecision) {
    run(voz, async () => {
      const pessoa = decision.newPessoaName
        ? await createPessoa(decision.newPessoaName, null)
        : pessoas.find((candidate) => candidate.id === decision.pessoaId)!
      const { outras_vozes_reconhecidas: recognized } = await confirmVoice(voz, pessoa.id)
      const extra = recognized > 0 ? ` A amostra nova reconheceu mais ${recognized} ${recognized === 1 ? 'voz' : 'vozes'}.` : ''
      return `Voz atribuída a ${pessoa.nome}.${extra}`
    })
  }

  function handleIgnore(voz: VozPendente) {
    run(voz, async () => {
      const { trechos_removidos: removed } = await ignoreVoice(voz)
      return `Voz ignorada: ${removed} ${removed === 1 ? 'trecho saiu' : 'trechos saíram'} da busca.`
    })
  }

  return (
    <section className="review" aria-labelledby="review-title">
      <header className="review__intro">
        <h2 id="review-title">Vozes sem autor</h2>
        <p>
          Estes trechos não aparecem na busca porque o sistema não teve certeza de quem fala. Ouça as amostras e diga de
          quem é a voz: ela vira referência para reconhecer a pessoa sozinha nos próximos vídeos.
        </p>
      </header>

      <div aria-live="polite">
        {feedback && <p className="review__feedback">{feedback}</p>}
      </div>

      {load.status === 'loading' && <div className="skeleton"><div className="skeleton__card" /></div>}
      {load.status === 'error' && (
        <div className="notice notice--error" role="alert">
          <p className="notice__title">{load.message}</p>
        </div>
      )}
      {load.status === 'ready' && vozes.length === 0 && (
        <div className="notice">
          <p className="notice__title">Nenhuma voz pendente.</p>
          <p>Todas as vozes dos vídeos já têm autor ou foram ignoradas.</p>
        </div>
      )}
      {vozes.map((voz) => (
        <VoiceCard
          key={keyOf(voz)}
          voz={voz}
          pessoas={pessoas}
          isBusy={busyKey === keyOf(voz)}
          onConfirm={(decision) => handleConfirm(voz, decision)}
          onIgnore={() => handleIgnore(voz)}
        />
      ))}
    </section>
  )
}

function keyOf(voz: VozPendente): string {
  return `${voz.conteudo_id}/${voz.rotulo}`
}
