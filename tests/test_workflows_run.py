import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parent.parent
WORKFLOWS = RAIZ / ".github" / "workflows"


def _achar_bash():
    candidatos = []
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), os.environ.get("LOCALAPPDATA")):
        if base:
            candidatos.append(Path(base) / "Git" / "bin" / "bash.exe")
            candidatos.append(Path(base) / "Programs" / "Git" / "bin" / "bash.exe")
    for c in candidatos:
        if c.exists():
            return str(c)
    achado = shutil.which("bash")
    if achado and "system32" not in achado.lower():
        return achado
    return None


def _posix(caminho):
    texto = Path(caminho).as_posix()
    m = re.match(r"^([A-Za-z]):/(.*)$", texto)
    return f"/{m.group(1).lower()}/{m.group(2)}" if m else texto


BASH = _achar_bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="bash (Git Bash) não encontrado")

SHIMS = {
    "git": r'''#!/bin/bash
echo "git $*" >> "$LOG"
case "$*" in
  ls-remote*) exit "${LSREMOTE_RC:-0}";;
  "diff --cached --quiet"*) exit "${DIFF_RC:-0}";;
  *"merge --no-edit"*)
    case "$MERGE_FAIL" in
      always) exit 1;;
      raso) grep -q unshallow "$LOG" || exit 1;;
    esac
    exit 0;;
  *"--shallow-since"*) [ -n "$FETCH_RASO_FALHA" ] && exit 1; exit 0;;
  "log -1 --format=%cd"*) echo "$COMMIT_DATE"; exit 0;;
  "log -1 --grep"*|"log --grep"*) echo "$DEPOIS_HASH"; exit 0;;
esac
exit 0
''',
    "gh": r'''#!/bin/bash
echo "gh $*" >> "$LOG"
case "$*" in
  "run view"*startedAt*) [ -n "$GH_VIEW_FALHA" ] && exit 1; echo "2026-11-02T12:00:00Z";;
  "run view"*jobs*) var="SENT_$3"; echo "${!var:-0}";;
  "run list"*conclusion*) printf '%s\n' $RUNS;;
  "run list"*databaseId*) echo "$RUN_ID";;
  "issue list"*) echo "$ISSUE";;
esac
exit 0
''',
    "python": r'''#!/bin/bash
echo "python $* COLETA_INICIO=${COLETA_INICIO-unset}" >> "$LOG"
[ -n "$PY_OUT" ] && printf '%b' "$PY_OUT"
exit 0
''',
    "tar": '#!/bin/bash\necho "tar $*" >> "$LOG"\nexit 0\n',
    "curl": '#!/bin/bash\necho "curl $*" >> "$LOG"\nexit 0\n',
    "date": '''#!/bin/bash
if [ "$1 $2" = "-u +%H" ]; then echo "$FAKE_HORA"; exit 0; fi
exec /usr/bin/date "$@"
''',
}


def _passo(arquivo, prefixo, substituicoes=None):
    dados = yaml.safe_load((WORKFLOWS / arquivo).read_text(encoding="utf-8"))
    achados = []
    for job in dados["jobs"].values():
        for passo in job["steps"]:
            if passo.get("name", "").startswith(prefixo) and "run" in passo:
                achados.append(passo["run"])
    assert len(achados) == 1, (arquivo, prefixo, len(achados))
    corpo = achados[0]
    for chave, valor in (substituicoes or {}).items():
        corpo = corpo.replace(chave, valor)
    assert "${{" not in corpo
    return corpo


class Ambiente:
    def __init__(self, tmp_path):
        self.dir = tmp_path
        self.trab = tmp_path / "trab"
        self.rt = tmp_path / "rt"
        self.bin = tmp_path / "bin"
        for d in (self.trab, self.rt, self.bin):
            d.mkdir()
        for nome, texto in SHIMS.items():
            (self.bin / nome).write_bytes(texto.encode("utf-8"))
        self.log = tmp_path / "log.txt"
        self.log.write_text("")
        self.saida = tmp_path / "output.txt"
        self.saida.write_text("")

    def rodar(self, corpo, **env):
        e = dict(os.environ)
        e.update({
            "LOG": self.log.as_posix(),
            "RUNNER_TEMP": self.rt.as_posix(),
            "GITHUB_OUTPUT": self.saida.as_posix(),
            "GITHUB_RUN_ID": "99",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "o/r",
        })
        for chave in ("SMTP_HOST", "ASSINANTES_URL", "DIA", "DIFF_RC", "MERGE_FAIL", "ISSUE"):
            e.pop(chave, None)
        e.update({k: str(v) for k, v in env.items()})
        return subprocess.run(
            [BASH, "-e", "-c", f'export PATH="{_posix(self.bin)}:$PATH"; ' + corpo], cwd=self.trab, env=e,
            capture_output=True, text=True, encoding="utf-8",
        )

    def linhas(self):
        return self.log.read_text(encoding="utf-8").splitlines()

    def texto(self):
        return self.log.read_text(encoding="utf-8")

    def comandos(self, prefixo):
        return [l for l in self.linhas() if l.startswith(prefixo)]


@pytest.fixture
def amb(tmp_path):
    return Ambiente(tmp_path)


def _hoje():
    return subprocess.run(
        [BASH, "-c", "TZ=America/Sao_Paulo date +%F"], capture_output=True, text=True
    ).stdout.strip()


def test_juntar_coletas_extrai_pacotes_existentes(amb):
    pacotes = amb.rt / "pacotes"
    pacotes.mkdir()
    (pacotes / "a.tgz").write_text("x")
    (pacotes / "b.tgz").write_text("x")
    r = amb.rodar(_passo("atualizar.yml", "Juntar o resultado"))
    assert r.returncode == 0, r.stderr
    assert len(amb.comandos("tar xzf")) == 2


def test_juntar_coletas_sem_pacote_nao_falha(amb):
    (amb.rt / "pacotes").mkdir()
    r = amb.rodar(_passo("atualizar.yml", "Juntar o resultado"))
    assert r.returncode == 0, r.stderr
    assert amb.comandos("tar") == []


def _salvar_historico(amb, diff_rc):
    (amb.trab / "dados" / "votacoes").mkdir(parents=True)
    return amb.rodar(_passo("atualizar.yml", "Salvar histórico"), DIFF_RC=diff_rc)


def test_salvar_historico_adiciona_so_caminhos_existentes(amb):
    r = _salvar_historico(amb, 0)
    assert r.returncode == 0, r.stderr
    adds = amb.comandos("git add")
    assert adds == ["git add dados/votacoes"]


def test_salvar_historico_sem_diferenca_nao_comita_mas_sincroniza(amb):
    _salvar_historico(amb, 0)
    assert amb.comandos("git commit") == []
    assert "git pull --rebase -q origin master" in amb.linhas()
    assert "git push" in amb.linhas()


def test_salvar_historico_com_diferenca_comita_antes_do_push(amb):
    _salvar_historico(amb, 1)
    comandos = [l for l in amb.linhas() if l.startswith(("git commit", "git pull", "git push"))]
    assert comandos[0].startswith("git commit -m Dados atualizados em ")
    assert comandos[1].startswith("git pull")
    assert comandos[2] == "git push"


def test_historico_diario_exporta_inicio_da_coleta(amb):
    r = amb.rodar(_passo("atualizar.yml", "Registrar o histórico diário"))
    assert r.returncode == 0, r.stderr
    py = amb.comandos("python")
    assert len(py) == 1
    assert re.fullmatch(r"python scripts/historico\.py COLETA_INICIO=2026-11-02T\d\d:00:00[+-]\d\d:\d\d", py[0])


def test_historico_diario_sem_gh_segue_sem_inicio(amb):
    r = amb.rodar(_passo("atualizar.yml", "Registrar o histórico diário"), GH_VIEW_FALHA=1)
    assert r.returncode == 0, r.stderr
    assert amb.comandos("python") == ["python scripts/historico.py COLETA_INICIO=unset"]


@pytest.mark.parametrize("diff_rc,comita", [(0, False), (1, True)])
def test_historico_diario_comita_so_com_diferenca(amb, diff_rc, comita):
    amb.rodar(_passo("atualizar.yml", "Registrar o histórico diário"), DIFF_RC=diff_rc)
    assert "git add dados/historico" in amb.linhas()
    commits = amb.comandos("git commit")
    assert bool(commits) is comita
    if comita:
        assert commits[0].startswith("git commit -m Histórico diário de ")
    assert "git push" in amb.linhas()


SINC = "Sincronizar a develop"


def test_sincronizar_sem_develop_pula(amb):
    r = amb.rodar(_passo("atualizar.yml", SINC), LSREMOTE_RC=2)
    assert r.returncode == 0, r.stderr
    assert "Sem develop no remoto" in r.stdout
    assert amb.comandos("git fetch") == []
    assert amb.comandos("gh") == []


def test_sincronizar_com_sucesso_empurra_a_develop(amb):
    r = amb.rodar(_passo("atualizar.yml", SINC))
    assert r.returncode == 0, r.stderr
    assert any("push -q origin develop" in l for l in amb.linhas())
    assert not any("unshallow" in l for l in amb.linhas())
    assert amb.comandos("gh issue create") == []
    assert amb.comandos("gh issue close") == []


def test_sincronizar_historico_raso_tenta_de_novo_com_unshallow(amb):
    r = amb.rodar(_passo("atualizar.yml", SINC), MERGE_FAIL="raso")
    assert r.returncode == 0, r.stderr
    assert any("fetch -q --unshallow origin" in l for l in amb.linhas())
    assert len([l for l in amb.linhas() if "merge --no-edit" in l]) == 2
    assert any("push -q origin develop" in l for l in amb.linhas())
    assert amb.comandos("gh issue create") == []


def test_sincronizar_conflito_aborta_e_abre_issue(amb):
    r = amb.rodar(_passo("atualizar.yml", SINC), MERGE_FAIL="always")
    assert r.returncode == 1
    assert any("merge --abort" in l for l in amb.linhas())
    assert not any("push -q origin develop" in l for l in amb.linhas())
    assert "::warning::" in r.stdout
    criar = amb.comandos("gh issue create --title A develop não sincronizou com a master")
    assert len(criar) == 1
    assert amb.comandos("gh issue comment") == []


def test_sincronizar_conflito_com_issue_aberta_comenta(amb):
    r = amb.rodar(_passo("atualizar.yml", SINC), MERGE_FAIL="always", ISSUE=7)
    assert r.returncode == 1
    assert amb.comandos("gh issue comment 7")
    assert amb.comandos("gh issue create") == []


def test_sincronizar_restabelecida_fecha_a_issue(amb):
    r = amb.rodar(_passo("atualizar.yml", SINC), ISSUE=7)
    assert r.returncode == 0, r.stderr
    assert amb.comandos("gh issue close 7 --comment Sincronização restabelecida.")


@pytest.mark.parametrize("arquivo,prefixo,script", [
    ("atualizar.yml", "Enviar resumo do que mudou", "resumo_email.py"),
    ("atualizar.yml", "Enviar avisos aos assinantes", "assinaturas.py"),
])
class TestEnvioDiario:
    def _rodar(self, amb, arquivo, prefixo, **env):
        return amb.rodar(_passo(arquivo, prefixo), **env)

    def test_sem_segredos_pula(self, amb, arquivo, prefixo, script):
        r = self._rodar(amb, arquivo, prefixo)
        assert r.returncode == 0, r.stderr
        assert "pulando" in r.stdout
        assert amb.comandos("python") == []

    def test_commit_de_ontem_nao_envia(self, amb, arquivo, prefixo, script):
        self._rodar(amb, arquivo, prefixo, SMTP_HOST="h", ASSINANTES_URL="u",
                    DEPOIS_HASH="abc", COMMIT_DATE="2000-01-01")
        assert amb.comandos("python") == []

    def test_sem_commit_de_dados_nao_envia(self, amb, arquivo, prefixo, script):
        self._rodar(amb, arquivo, prefixo, SMTP_HOST="h", ASSINANTES_URL="u", DEPOIS_HASH="")
        assert amb.comandos("python") == []

    def test_commit_de_hoje_envia(self, amb, arquivo, prefixo, script):
        r = self._rodar(amb, arquivo, prefixo, SMTP_HOST="h", ASSINANTES_URL="u",
                        DEPOIS_HASH="abc", COMMIT_DATE=_hoje())
        assert r.returncode == 0, r.stderr
        py = amb.comandos("python")
        assert len(py) == 1
        assert py[0].startswith(f"python scripts/{script} abc~1 abc --enviar")


CONF = "Mandar as confirmações pendentes"


def test_confirmacoes_sem_segredos_pula(amb):
    r = amb.rodar(_passo("confirmacoes.yml", CONF))
    assert r.returncode == 0, r.stderr
    assert "pulando" in r.stdout
    assert amb.comandos("python") == []
    assert amb.saida.read_text() == ""


def test_confirmacoes_enviadas_marcam_a_saida(amb):
    r = amb.rodar(_passo("confirmacoes.yml", CONF), SMTP_HOST="h", ASSINANTES_URL="u",
                  PY_OUT="Enviados: 3\n")
    assert r.returncode == 0, r.stderr
    assert amb.comandos("python") == ["python scripts/assinaturas.py --so-confirmacoes --enviar COLETA_INICIO=unset"]
    assert amb.saida.read_text().strip() == "enviou=sim"


def test_confirmacoes_nenhuma_enviada_nao_marca(amb):
    r = amb.rodar(_passo("confirmacoes.yml", CONF), SMTP_HOST="h", ASSINANTES_URL="u",
                  PY_OUT="Enviados: 0\n")
    assert r.returncode == 0, r.stderr
    assert amb.saida.read_text() == ""


APAGAR = "Apagar as execuções sem envio"


def test_apagar_fora_das_23h_nao_consulta_nada(amb):
    r = amb.rodar(_passo("confirmacoes.yml", APAGAR), FAKE_HORA="10", RUNS="1 2")
    assert r.returncode == 0, r.stderr
    assert amb.comandos("gh") == []


def test_apagar_remove_so_execucoes_sem_envio(amb):
    r = amb.rodar(_passo("confirmacoes.yml", APAGAR), FAKE_HORA="23", RUNS="1 2", SENT_2=1)
    assert r.returncode == 0, r.stderr
    assert amb.comandos("gh run delete") == ["gh run delete 1"]


ISSUE_PASSO = "Abrir ou atualizar issue"


def test_issue_contrato_sem_resumo_usa_texto_padrao_e_cria(amb):
    r = amb.rodar(_passo("contratos.yml", ISSUE_PASSO), RESUMO=amb.rt / "nao-existe.md")
    assert r.returncode == 0, r.stderr
    texto = amb.texto()
    assert "gh issue create --title Contrato de API externa quebrou" in texto
    assert "A verificação falhou antes de gerar o resumo" in texto
    assert "https://github.com/o/r/actions/runs/99" in texto
    assert amb.comandos("gh issue comment") == []


def test_issue_contrato_existente_recebe_comentario_com_o_resumo(amb):
    resumo = amb.rt / "contrato.md"
    resumo.write_text("API X mudou", encoding="utf-8")
    r = amb.rodar(_passo("contratos.yml", ISSUE_PASSO), RESUMO=resumo, ISSUE=5)
    assert r.returncode == 0, r.stderr
    texto = amb.texto()
    assert "gh issue comment 5 --body API X mudou" in texto
    assert "A verificação falhou" not in texto
    assert amb.comandos("gh issue create") == []


BAIXAR = "Baixar os pacotes de dados"


@pytest.mark.parametrize("run_id", ["", "null"])
def test_republicar_sem_execucao_bem_sucedida_falha(amb, run_id):
    r = amb.rodar(_passo("republicar.yml", BAIXAR), RUN_ID=run_id)
    assert r.returncode == 1
    assert "Nenhuma execução bem-sucedida" in r.stderr
    assert amb.comandos("gh run download") == []


def test_republicar_baixa_e_extrai_os_pacotes(amb):
    pacotes = amb.rt / "pacotes"
    pacotes.mkdir()
    (pacotes / "a.tgz").write_text("x")
    (pacotes / "b.txt").write_text("x")
    r = amb.rodar(_passo("republicar.yml", BAIXAR), RUN_ID=1234)
    assert r.returncode == 0, r.stderr
    assert "Pacotes da execução 1234" in r.stdout
    baixar = amb.comandos("gh run download 1234 --pattern pacote-*")
    assert len(baixar) == 1
    tars = amb.comandos("tar xzf")
    assert len(tars) == 1 and tars[0].endswith("a.tgz")


ESCOLHER = "Escolher o commit diário"


def test_escolher_commit_sem_dia_usa_o_mais_recente(amb):
    r = amb.rodar(_passo("testar-avisos.yml", ESCOLHER), DEPOIS_HASH="abc", COMMIT_DATE="2026-11-02")
    assert r.returncode == 0, r.stderr
    assert amb.saida.read_text().strip() == "depois=abc"
    assert "Commit: abc (2026-11-02)" in r.stdout
    assert not any("--since" in l for l in amb.linhas())


def test_escolher_commit_com_dia_busca_o_dia_seguinte(amb):
    r = amb.rodar(_passo("testar-avisos.yml", ESCOLHER), DIA="2026-11-01",
                  DEPOIS_HASH="def", COMMIT_DATE="2026-11-02")
    assert r.returncode == 0, r.stderr
    assert amb.saida.read_text().strip() == "depois=def"
    busca = [l for l in amb.linhas() if "--since" in l]
    assert len(busca) == 1
    assert "--since=2026-11-02 00:00 -0300" in busca[0]
    assert "--until=2026-11-02 23:59:59 -0300" in busca[0]


def test_escolher_commit_inexistente_falha(amb):
    r = amb.rodar(_passo("testar-avisos.yml", ESCOLHER), DIA="2026-11-01", DEPOIS_HASH="")
    assert r.returncode == 1
    assert "Sem commit diário para '2026-11-01'" in r.stdout
    assert amb.saida.read_text() == ""


def test_escolher_commit_inexistente_sem_dia_cita_o_mais_recente(amb):
    r = amb.rodar(_passo("testar-avisos.yml", ESCOLHER), DEPOIS_HASH="")
    assert r.returncode == 1
    assert "o mais recente" in r.stdout


AVISOS = "Avisos aos assinantes (sem enviar"
SUBST = {"${{ steps.commit.outputs.depois }}": "abc"}


def test_avisos_sem_enviar_sem_segredo_pula(amb):
    r = amb.rodar(_passo("testar-avisos.yml", AVISOS, SUBST))
    assert r.returncode == 0, r.stderr
    assert "pulando" in r.stdout
    assert amb.comandos("python") == []


def test_avisos_sem_enviar_conta_sem_flag_de_envio(amb):
    r = amb.rodar(_passo("testar-avisos.yml", AVISOS, SUBST), ASSINANTES_URL="u")
    assert r.returncode == 0, r.stderr
    py = amb.comandos("python")
    assert len(py) == 1
    assert py[0].startswith("python scripts/assinaturas.py abc~1 abc ")
    assert "--enviar" not in py[0]
