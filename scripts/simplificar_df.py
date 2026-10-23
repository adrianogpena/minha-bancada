"""Baixa as Regiões Administrativas do DF (camada geonode:regioes_administrativas do catálogo do
IPE-DF, via WFS) e grava um GeoJSON leve em site/geo/df_ras.json.

Uso: python scripts/simplificar_df.py [arquivo_baixado.json]   (sem argumento, baixa da fonte)

Fonte: https://catalogo.ipe.df.gov.br/layers/geonode_data:geonode:regioes_administrativas
"""
import json
import sys
import urllib.request
from pathlib import Path

FONTE = ("https://catalogo.ipe.df.gov.br/geoserver/ows?service=WFS&version=1.0.0&request=GetFeature"
         "&typeName=geonode:regioes_administrativas&outputFormat=application/json&srsName=EPSG:4326")

TOLERANCIA = 0.0006   # graus (~65 m)

# a camada do IPE-DF perde os acentos dos nomes; os nomes certos vêm do código da RA
NOMES = ["Plano Piloto", "Gama", "Taguatinga", "Brazlândia", "Sobradinho", "Planaltina", "Paranoá", "Núcleo Bandeirante", "Ceilândia", "Guará",
         "Cruzeiro", "Samambaia", "Santa Maria", "São Sebastião", "Recanto das Emas", "Lago Sul", "Riacho Fundo", "Lago Norte", "Candangolândia",
         "Águas Claras", "Riacho Fundo II", "Sudoeste e Octogonal", "Varjão", "Park Way", "SCIA/Estrutural", "Sobradinho II", "Jardim Botânico",
         "Itapoã", "SIA", "Vicente Pires", "Fercal", "Sol Nascente e Pôr do Sol", "Arniqueira", "Arapoanga", "Água Quente"]
ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50}


def romano(r):
    n = 0
    for a, b in zip(r, r[1:] + " ", strict=True):
        n += -ROMANOS[a] if ROMANOS.get(b, 0) > ROMANOS[a] else ROMANOS[a]
    return n


def dist2(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return (x - x1) ** 2 + (y - y1) ** 2
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return (x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2


def douglas(pts, tol2):
    if len(pts) < 3:
        return pts
    maior, ind = 0, 0
    for i in range(1, len(pts) - 1):
        d = dist2(pts[i], pts[0], pts[-1])
        if d > maior:
            maior, ind = d, i
    if maior <= tol2:
        return [pts[0], pts[-1]]
    return douglas(pts[:ind + 1], tol2)[:-1] + douglas(pts[ind:], tol2)


def anel(a):
    r = douglas([tuple(p[:2]) for p in a], TOLERANCIA ** 2)
    return [[round(x, 4), round(y, 4)] for x, y in r] if len(r) >= 4 else None


def main(origem: str | None) -> None:
    if origem:
        dados = json.loads(Path(origem).read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(urllib.request.Request(FONTE, headers={"User-Agent": "minha-bancada"}), timeout=120) as r:
            dados = json.load(r)
    saida = []
    for f in dados["features"]:
        g = f["geometry"]
        polis = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        novos = [[a for a in (anel(r) for r in poli) if a] for poli in polis]
        novos = [p for p in novos if p]
        props = f["properties"]
        saida.append({"type": "Feature", "properties": {"nome": NOMES[romano(props["ra_codigo"].removeprefix("RA-")) - 1], "codigo": props["ra_codigo"]},
                      "geometry": {"type": "MultiPolygon", "coordinates": novos}})
    destino = Path(__file__).resolve().parent.parent / "site" / "geo" / "df_ras.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps({"type": "FeatureCollection", "features": saida}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(len(saida), "RAs,", destino.stat().st_size // 1024, "KB")


main(sys.argv[1] if len(sys.argv) > 1 else None)
