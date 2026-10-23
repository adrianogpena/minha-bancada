"""Monta ZIPs no formato do TSE (CSV em latin-1, separado por ';') para os testes."""
import zipfile


def zip_csv(caminho, arquivos):
    """arquivos: {nome do csv: lista de dicts}; grava um ZIP com CSV latin-1 separado por ';'."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(caminho, "w") as z:
        for nome, linhas in arquivos.items():
            cols = list(linhas[0])
            texto = ";".join(cols) + "\n" + "\n".join(";".join(str(lin[c]) for c in cols) for lin in linhas) + "\n"
            z.writestr(nome, texto.encode("latin-1"))
