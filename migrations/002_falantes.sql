-- Diarização entra no MVP: o vídeo do debate tem mais de um falante.

-- O vetor só existe depois da etapa de embeddings; o chunking cria o trecho antes.
ALTER TABLE trecho ALTER COLUMN modelo_embedding DROP NOT NULL;
-- Rótulo anônimo do falante (SPEAKER_00…): permite atribuir a pessoa sem re-fatiar.
ALTER TABLE trecho ADD COLUMN falante_rotulo text;

ALTER TABLE conteudo ADD COLUMN transcricao_origem text
  CHECK (transcricao_origem IN ('legenda_youtube', 'whisper'));
-- Turnos de fala sem sobreposição: [{start, end, speaker}]
ALTER TABLE conteudo ADD COLUMN diarizacao jsonb;

-- Um falante anônimo de um conteúdo e para quem ele foi atribuído.
CREATE TABLE falante_conteudo (
  conteudo_id           uuid NOT NULL REFERENCES conteudo(id) ON DELETE CASCADE,
  rotulo                text NOT NULL,
  embedding_voz         vector(256),
  segundos_fala         real NOT NULL,
  pessoa_id             uuid REFERENCES pessoa(id),
  confianca_atribuicao  real,
  confirmado            boolean NOT NULL DEFAULT false,
  PRIMARY KEY (conteudo_id, rotulo)
);

-- A amostra de voz nasce de um falante confirmado por humano, não de um trecho.
ALTER TABLE amostra_voz ADD COLUMN origem_conteudo_id uuid REFERENCES conteudo(id) ON DELETE SET NULL;
ALTER TABLE amostra_voz ADD COLUMN origem_rotulo text;
ALTER TABLE amostra_voz ADD CONSTRAINT amostra_voz_origem_unica UNIQUE (origem_conteudo_id, origem_rotulo);
