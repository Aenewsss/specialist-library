-- Schema do MVP, copiado da seção "Modelo de dados" da especificação.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE pessoa (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome        text NOT NULL,
  bio_curta   text,
  verificado  boolean NOT NULL DEFAULT false,
  criado_em   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE area (
  id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome  text NOT NULL UNIQUE
);

CREATE TABLE pessoa_area (
  pessoa_id  uuid REFERENCES pessoa(id) ON DELETE CASCADE,
  area_id    uuid REFERENCES area(id) ON DELETE CASCADE,
  PRIMARY KEY (pessoa_id, area_id)
);

CREATE TABLE amostra_voz (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pessoa_id      uuid NOT NULL REFERENCES pessoa(id) ON DELETE CASCADE,
  embedding_voz  vector(256),  -- dimensão depende do modelo de voz escolhido
  origem_trecho  uuid          -- trecho de onde a amostra foi confirmada
);

CREATE TABLE fonte (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tipo            text NOT NULL CHECK (tipo IN ('youtube','podcast_rss','livro','web','instagram','tiktok')),
  url             text NOT NULL,
  dono_pessoa_id  uuid REFERENCES pessoa(id),
  UNIQUE (tipo, url)
);

CREATE TABLE conteudo (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fonte_id           uuid NOT NULL REFERENCES fonte(id) ON DELETE CASCADE,
  id_externo         text,          -- ex.: video_id do YouTube
  titulo             text,
  url_original       text NOT NULL,
  publicado_em       date,
  idioma             text DEFAULT 'pt',
  transcricao_bruta  jsonb,         -- segmentos com start/end/text/speaker
  UNIQUE (fonte_id, id_externo)
);

CREATE TABLE trecho (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conteudo_id           uuid NOT NULL REFERENCES conteudo(id) ON DELETE CASCADE,
  pessoa_id             uuid REFERENCES pessoa(id),   -- nulo = autoria incerta
  texto                 text NOT NULL,
  inicio_s              integer,   -- áudio/vídeo
  fim_s                 integer,
  pagina                integer,   -- livros/PDF
  embedding             vector(1024),
  modelo_embedding      text NOT NULL,
  busca_texto           tsvector GENERATED ALWAYS AS (to_tsvector('portuguese', texto)) STORED,
  confianca_atribuicao  real,
  revisado              boolean NOT NULL DEFAULT false
);

CREATE INDEX trecho_embedding_hnsw ON trecho USING hnsw (embedding vector_cosine_ops);
CREATE INDEX trecho_busca_gin      ON trecho USING gin (busca_texto);
CREATE INDEX trecho_pessoa_idx     ON trecho (pessoa_id);
CREATE INDEX trecho_conteudo_idx   ON trecho (conteudo_id);

CREATE TABLE job_ingestao (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conteudo_id  uuid NOT NULL REFERENCES conteudo(id) ON DELETE CASCADE,
  etapa        text NOT NULL CHECK (etapa IN ('coleta','transcricao','diarizacao','atribuicao','chunking','embeddings')),
  status       text NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','rodando','ok','erro')),
  tentativas   integer NOT NULL DEFAULT 0,
  erro         text,
  atualizado_em timestamptz NOT NULL DEFAULT now(),
  UNIQUE (conteudo_id, etapa)
);
