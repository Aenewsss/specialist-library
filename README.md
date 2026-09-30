# Biblioteca de Especialistas

Buscador extrativo: "quem disse o quê sobre isso, e onde", sempre com o trecho literal
e o link para o momento exato da fonte. Nenhum texto exibido vem de geração de LLM.

## Rodando

```bash
docker compose up -d
python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev,ml]'
echo "HF_TOKEN=..." > .env              # pyannote exige token do Hugging Face
.venv/bin/biblioteca migrate
.venv/bin/biblioteca add-pessoa "Nome"
.venv/bin/biblioteca add-video "https://www.youtube.com/watch?v=..."
.venv/bin/biblioteca ingest             # coleta → transcrição → diarização → atribuição → chunking → embeddings
.venv/bin/biblioteca falantes <conteudo_id>                       # vozes + links para ouvir
.venv/bin/biblioteca rotular-falante <conteudo_id> SPEAKER_00 --pessoa <id>
.venv/bin/biblioteca ignorar-falante <conteudo_id> SPEAKER_01     # ex.: apresentador
.venv/bin/biblioteca ask "o dilúvio foi global ou local?"
.venv/bin/uvicorn app.api:app           # POST /ask {"pergunta": "..."}
.venv/bin/pytest
```

Postgres escuta em `localhost:5442`. Configuração em `config.yaml` (`DATABASE_URL` no ambiente sobrescreve).
