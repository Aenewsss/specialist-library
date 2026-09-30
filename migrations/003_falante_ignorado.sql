-- Voz revisada e descartada (ex.: apresentador): não gera trechos de busca.
ALTER TABLE falante_conteudo ADD COLUMN ignorado boolean NOT NULL DEFAULT false;
