export function formatTimestamp(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = Math.floor(totalSeconds % 60)
  const mmss = `${String(minutes).padStart(hours ? 2 : 1, '0')}:${String(seconds).padStart(2, '0')}`
  return hours ? `${hours}:${mmss}` : mmss
}

const DATE_FORMAT = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })

export function formatDate(isoDate: string): string {
  return DATE_FORMAT.format(new Date(`${isoDate}T00:00:00Z`))
}

export interface YoutubePosition {
  videoId: string
  startS: number
}

/** Extrai vídeo e segundo do link montado pela API, para abrir o player embutido. */
export function parseYoutubeLink(link: string): YoutubePosition | null {
  try {
    const url = new URL(link)
    const videoId = url.searchParams.get('v')
    if (!url.hostname.endsWith('youtube.com') || !videoId) return null
    const startS = Number.parseInt(url.searchParams.get('t') ?? '0', 10)
    return { videoId, startS: Number.isNaN(startS) ? 0 : startS }
  } catch {
    return null
  }
}
