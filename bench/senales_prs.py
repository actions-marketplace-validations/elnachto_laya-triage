import argparse
import json
import re
from itertools import combinations

import pandas as pd

from triage import limpiar_cuerpo

TITULO_POR_DEFECTO = re.compile(
    r"^(update|create|add|delete|rename)\s+[\w\-. /]+(\s+to\s+[\w\-. /]+)?$|^add files via upload$",
    re.IGNORECASE,
)
EXTENSIONES_TEXTO = (".md", ".txt", ".rst", ".html", ".json", ".yml", ".yaml")
PRIMERIZOS = {"FIRST_TIME_CONTRIBUTOR", "FIRST_TIMER", "NONE"}
REPO_PRACTICA = re.compile(r"hacktoberfest|first-contribution|beginner|practice|open-?source-?(?:practice|projects)", re.IGNORECASE)


def origen(fila):
    etiquetas = [e.lower() for e in json.loads(fila.get("etiquetas") or "[]")]
    if fila["labels"] != "spam":
        return "genuino"
    return "spam" if "spam" in etiquetas else "invalid"


def filtrar(datos, args):
    if args.origen != "todos":
        datos = datos[datos.apply(origen, axis=1).isin({args.origen, "genuino"})]
    if args.sin_practica:
        datos = datos[~datos["repo"].str.contains(REPO_PRACTICA)]
    if args.anio:
        datos = datos[datos["created_at"].str[:4] == args.anio]
    return datos.reset_index(drop=True)


def calcular_senales(fila):
    archivos = json.loads(fila["archivos"] or "[]")
    lineas = fila["additions"] + fila["deletions"]
    return {
        "titulo_por_defecto": bool(TITULO_POR_DEFECTO.match(fila["title"].strip())),
        "cuerpo_vacio": len(limpiar_cuerpo(fila["body"])) < 20,
        "un_archivo": fila["changed_files"] <= 1,
        "no_borra_nada": fila["deletions"] == 0,
        "pocas_lineas": lineas <= 30,
        "solo_texto": bool(archivos) and all(a.lower().endswith(EXTENSIONES_TEXTO) for a in archivos),
        "primerizo": fila["author_association"] in PRIMERIZOS,
    }


def medir(reales, marcados):
    vp = int((reales & marcados).sum())
    fp = int((~reales & marcados).sum())
    recall = vp / max(1, int(reales.sum()))
    precision = vp / (vp + fp) if vp + fp else 0.0
    return round(recall * 100, 1), round(fp / max(1, int((~reales).sum())) * 100, 1), round(precision * 100, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra", nargs="?", default="datos/prs_hacktoberfest.csv")
    parser.add_argument("--max-falsos", type=float, default=2.0)
    parser.add_argument("--excluir", default="")
    parser.add_argument("--origen", default="todos", choices=["todos", "spam", "invalid"])
    parser.add_argument("--sin-practica", action="store_true")
    parser.add_argument("--anio", default="")
    args = parser.parse_args()

    datos = filtrar(pd.read_csv(args.muestra).fillna(""), args)
    senales = pd.DataFrame([calcular_senales(fila) for fila in datos.to_dict("records")])
    senales = senales.drop(columns=[c for c in args.excluir.split(",") if c])
    reales = (datos["labels"] == "spam").to_numpy()

    print(f"{len(datos)} PRs: {int(reales.sum())} spam, {int((~reales).sum())} genuinos\n")
    print(f"{'señal':22} {'% en spam':>10} {'% en genuinos':>14} {'veces más en spam':>18}")
    for nombre in senales.columns:
        en_spam = senales[nombre][reales].mean() * 100
        en_genuino = senales[nombre][~reales].mean() * 100
        print(f"{nombre:22} {en_spam:10.1f} {en_genuino:14.1f} {en_spam / max(en_genuino, 0.1):18.1f}")

    candidatas = []
    for tamano in (2, 3, 4):
        for combo in combinations(senales.columns, tamano):
            marcados = senales[list(combo)].all(axis=1).to_numpy()
            recall, falsos, precision = medir(reales, marcados)
            candidatas.append((recall, falsos, precision, " + ".join(combo)))

    seguras = sorted((c for c in candidatas if c[1] <= args.max_falsos), reverse=True)[:10]
    print(f"\nMejores combinaciones con genuinos acusados <= {args.max_falsos}%")
    print(f"{'spam detectado %':>17} {'genuinos acusados %':>20} {'precisión %':>12}  combinación")
    for recall, falsos, precision, nombre in seguras:
        print(f"{recall:17.1f} {falsos:20.1f} {precision:12.1f}  {nombre}")

    puntaje = senales.sum(axis=1).to_numpy()
    print(f"\nPuntaje = cuántas señales cumple (0 a {len(senales.columns)})")
    for minimo in range(2, len(senales.columns) + 1):
        recall, falsos, precision = medir(reales, puntaje >= minimo)
        print(f"  >= {minimo}: detecta {recall:5.1f}% del spam, acusa {falsos:5.1f}% de genuinos, precisión {precision:5.1f}%")


if __name__ == "__main__":
    main()