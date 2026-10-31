"""
Ids que o projeto gera (pessoa, mandato, candidatura, disputa, fornecedor sem CNPJ): um só jeito de fazer, para o id não mudar quando
os dados são processados de novo.

    gerar_id(prefixo, fonte, id_original) -> "<prefixo>_<12 hex>"   (sha1 de "fonte|id_original")

`fonte` diz de onde vem o id original e `id_original` é o que a fonte publica, como ela publica: ("camara", 204554), ("senado", 5012),
("tse:2022", sequencial), ("estadual:SP", id da Assembleia). Depende só desses dois textos: não entra posição na lista, ordem de arquivo,
contador, data da coleta nem id que o próprio projeto gerou. O registro guarda a fonte e o id original (`fontes`, `eleicao` +
`sequencial`...), então o id se refaz a qualquer momento. `gerar_id` recusa fonte ou id vazio, para não nascer id de "None".

Prefixos: pes (pessoa), man (mandato), can (candidatura), dsp (disputa), for_pf e for_n (fornecedor sem CNPJ), vot (votação nominal de Assembleia sem id
próprio na fonte: `alep_pr`, sessão e id do item).

Ficam fora, de propósito:
  - ids que a própria fonte publica e o projeto só repassa (id do deputado na Casa, do projeto, do CNPJ base em `for_<8 dígitos>`);
  - vocabulários fechados que o projeto mantém, com chave legível: `par_<sigla>` e `fed_<partidos>` (identidades.PARTIDOS).
  - `pes_` de quem só tem nome e nascimento (TSE e Câmara): a fonte de identidade é "nn" e o id original é "nome|nascimento" (nome sem
    acento nem apelido). Se o TSE corrigir o nome, o id muda; é o que há enquanto o TSE não publicar CPF.
  - `pes_` de quem só tem id de uma fonte (senador ou deputado estadual sem ligação) usa esse id; se a ligação com o TSE aparecer
    depois, o id passa a ser o de nome e nascimento.
"""

import hashlib


def gerar_id(prefixo: str, fonte: str, id_original, tamanho: int = 12) -> str:
    original = str(id_original).strip() if id_original is not None else ""
    if not prefixo or not fonte or not original or original.lower() in ("none", "nan"):
        raise ValueError(f"id sem fonte ou sem id original: {prefixo!r}, {fonte!r}, {id_original!r}")
    return f"{prefixo}_" + hashlib.sha1(f"{fonte}|{original}".encode("utf-8")).hexdigest()[:tamanho]
