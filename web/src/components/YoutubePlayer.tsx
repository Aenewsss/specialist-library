import type { YoutubePosition } from '../format'

export function YoutubePlayer({ position, title }: { position: YoutubePosition; title: string }) {
  return (
    <div className="player">
      <iframe
        src={`https://www.youtube-nocookie.com/embed/${position.videoId}?start=${position.startS}&autoplay=1`}
        title={title}
        allow="autoplay; encrypted-media; picture-in-picture"
        // O YouTube recusa embeds sem Referer (erro 153).
        referrerPolicy="strict-origin-when-cross-origin"
        allowFullScreen
      />
    </div>
  )
}
