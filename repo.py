import json
import re
import urllib.error
import urllib.parse
import urllib.request

MEZCLA_NATURAL = {"bug": 0.526, "feature": 0.370, "question": 0.060, "docs": 0.044}
PESO_NATURAL = 50
MINIMO_ETIQUETADOS = 30

SINONIMOS = {
    "bug": ["bug", "type bug", "kind bug", "t bug", "bug report", "confirmed bug"],
    "feature": [
        "enhancement", "feature", "feature request", "new feature", "type feature",
        "type enhancement", "kind feature", "kind enhancement", "t feature", "t enhancement",
    ],
    "question": ["question", "type question", "kind question", "support", "type support", "t question"],
    "docs": [
        "documentation", "docs", "doc", "type docs", "type documentation",
        "kind documentation", "kind docs", "area docs", "t docs",
    ],
}


def normalizar(nombre):
    return re.sub(r"[^a-z0-9]+", " ", nombre.lower()).strip()


NORMALIZADA_A_TIPO = {normalizar(s): tipo for tipo, lista in SINONIMOS.items() for s in lista}


def consultar(ruta, token):
    peticion = urllib.request.Request(
        f"https://api.github.com{ruta}",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "User-Agent": "laya-triage"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            return json.load(respuesta)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def etiquetas_del_repo(repo, token):
    nombres = []
    for pagina in range(1, 4):
        datos = consultar(f"/repos/{repo}/labels?per_page=100&page={pagina}", token)
        if not datos:
            break
        nombres.extend(e["name"] for e in datos)
        if len(datos) < 100:
            break
    return nombres


def mapear_etiquetas(nombres):
    mapa = {}
    for tipo, lista in SINONIMOS.items():
        orden = {normalizar(s): i for i, s in enumerate(lista)}
        candidatas = [n for n in nombres if NORMALIZADA_A_TIPO.get(normalizar(n)) == tipo]
        if candidatas:
            mapa[tipo] = min(candidatas, key=lambda n: orden[normalizar(n)])
    return mapa


def leer_pares(texto):
    pares = {}
    for parte in texto.split(","):
        if "=" in parte:
            clave, valor = parte.split("=", 1)
            pares[clave.strip()] = valor.strip()
    return pares


def contar_issues(repo, token, mapa):
    conteos = {}
    for tipo, etiqueta in mapa.items():
        consulta = urllib.parse.quote(f'repo:{repo} is:issue label:"{etiqueta}"')
        datos = consultar(f"/search/issues?q={consulta}&per_page=1", token)
        if datos is None:
            return None
        conteos[tipo] = datos.get("total_count", 0)
    return conteos


def mezcla_desde_conteos(conteos):
    total = sum(conteos.values())
    if total < MINIMO_ETIQUETADOS:
        return None
    return {
        tipo: (conteos.get(tipo, 0) + PESO_NATURAL * natural) / (total + PESO_NATURAL)
        for tipo, natural in MEZCLA_NATURAL.items()
    }


def mezcla_manual(texto):
    valores = {tipo: float(valor) for tipo, valor in leer_pares(texto).items() if tipo in MEZCLA_NATURAL}
    total = sum(valores.values())
    if len(valores) != len(MEZCLA_NATURAL) or total <= 0:
        return None
    return {tipo: valor / total for tipo, valor in valores.items()}


def pesos_para_ruta(mezcla, priores_modelo):
    if not mezcla:
        return priores_modelo
    if priores_modelo:
        return mezcla
    return {tipo: mezcla[tipo] / MEZCLA_NATURAL[tipo] for tipo in MEZCLA_NATURAL}
