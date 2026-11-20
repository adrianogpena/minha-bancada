import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import glossario_candidatos as gc


def escrever(caminho, conteudo):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo), encoding="utf-8")


def montar(tmp_path):
    site = tmp_path / "site"
    escrever(site / "assets/js/glossario.js", 'x = { variantes: ["prejudicado", "RMCD"] }, { variantes: ["parecer"] }')
    escrever(site / "dados/nucleo/partidos.json", {"PT": {"sigla": "PT"}, "PL": {"sigla": "PL"}})
    escrever(site / "dados/proposicoes.json", [
        {"s": "Aguardando XYZ e apensada"}, {"s": "Aguardando XYZ"}, {"s": "PREJUDICADA"}, {"s": "RMCD enviada"},
        {"s": "Do PT em SP"}, {"s": "Sobrestado pelo QWER"},
    ])
    escrever(site / "dados/votacoes.json", [{"descricao": "Rejeitado o veto, com quórum de 300. Prejudicado o outro."}])
    escrever(site / "dados/tramitacao_senado/1.json", {
        "informes": [["2026-01-01", "PLEN", "Recebido o requerimento de CEAP"]],
        "situacoes": [["a", "b", "AGDESP", "AGUARDANDO DESPACHO", "PLEN"]],
    })
    escrever(site / "dados/tramitacao/2.json", {"eventos": [{"d": "Apensado ao projeto, obstrução"}]})
    escrever(site / "pagina.html", "<html><script>var ABCD=1</script><p>Texto com XYZ visível</p></html>")
    return site


def test_candidatos_listam_siglas_e_suspeitos_com_contagem_e_exemplo(tmp_path):
    achados = {t: (n, o, e) for n, t, o, e in gc.candidatos(montar(tmp_path))}
    assert achados["XYZ"][0] == 3
    assert "Aguardando XYZ" in achados["XYZ"][2]
    assert achados["QWER"][0] == 1
    assert achados["apensad"][0] == 2
    assert achados["veto"][0] == 1
    assert achados["quórum"][0] == 1
    assert achados["CEAP"][0] == 1
    assert achados["obstrução"][0] == 1
    assert achados["sobrestad"][0] == 1


def test_candidatos_ignoram_cobertos_ufs_partidos_scripts_e_texto_todo_em_caixa_alta(tmp_path):
    achados = {t for _, t, _, _ in gc.candidatos(montar(tmp_path))}
    assert not achados & {"RMCD", "PT", "SP", "PL", "ABCD", "AGUARDANDO", "PLEN", "prejudicad"}


def test_candidatos_ordenados_por_ocorrencias(tmp_path):
    contagens = [n for n, *_ in gc.candidatos(montar(tmp_path))]
    assert contagens == sorted(contagens, reverse=True)


def test_main_grava_relatorio(tmp_path, monkeypatch):
    site = montar(tmp_path)
    saida = tmp_path / "saida.txt"
    monkeypatch.setattr(sys, "argv", ["x", "--site", str(site), "--saida", str(saida)])
    gc.main()
    linhas = saida.read_text(encoding="utf-8").splitlines()
    assert linhas[0].startswith("ocorrências")
    assert linhas[1].split("\t")[1] == "XYZ"


def test_site_sem_dados_nao_quebra(tmp_path):
    assert gc.candidatos(tmp_path) == []
