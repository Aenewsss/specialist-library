import { useCallback, useEffect, useState } from 'react'
import { listPendingVoices } from './api'
import { SearchPage } from './components/SearchPage'
import { VideosPage } from './components/VideosPage'
import { VoiceReview } from './components/VoiceReview'

type Tab = 'buscar' | 'videos' | 'vozes'

const TAB_HASH: Record<Tab, string> = { buscar: '', videos: '#videos', vozes: '#vozes' }

function tabFromHash(): Tab {
  const match = (Object.keys(TAB_HASH) as Tab[]).find((tab) => TAB_HASH[tab] && TAB_HASH[tab] === window.location.hash)
  return match ?? 'buscar'
}

export default function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash)
  const [pendingCount, setPendingCount] = useState<number | null>(null)

  useEffect(() => {
    const onHashChange = () => setTab(tabFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    listPendingVoices()
      .then((pending) => setPendingCount(pending.length))
      .catch(() => setPendingCount(null)) // o contador é só um aviso; a aba funciona sem ele
  }, [])

  const updatePendingCount = useCallback((count: number) => setPendingCount(count), [])

  function openTab(next: Tab) {
    window.history.replaceState(null, '', TAB_HASH[next] || window.location.pathname)
    setTab(next)
  }

  return (
    <div className="page">
      <header className="masthead">
        <p className="masthead__eyebrow">Biblioteca de Especialistas</p>
        <h1>Quem disse o quê — e onde.</h1>
        <p className="masthead__lede">
          Pergunte em linguagem natural. A resposta é sempre o trecho literal de quem falou, com o link para o momento exato.
        </p>
      </header>

      <nav className="tabs" aria-label="Seções">
        <button type="button" className="tab" aria-current={tab === 'buscar' ? 'page' : undefined} onClick={() => openTab('buscar')}>
          Buscar
        </button>
        <button type="button" className="tab" aria-current={tab === 'videos' ? 'page' : undefined} onClick={() => openTab('videos')}>
          Vídeos
        </button>
        <button type="button" className="tab" aria-current={tab === 'vozes' ? 'page' : undefined} onClick={() => openTab('vozes')}>
          Vozes sem autor
          {pendingCount !== null && pendingCount > 0 && <span className="tab__badge">{pendingCount}</span>}
        </button>
      </nav>

      <main>
        {tab === 'buscar' && <SearchPage />}
        {tab === 'videos' && <VideosPage />}
        {tab === 'vozes' && <VoiceReview onPendingCountChange={updatePendingCount} />}
      </main>

      <footer className="footer">Nenhum texto é escrito por IA: cada trecho é a transcrição literal da fala, com link para conferir na fonte.</footer>
    </div>
  )
}
