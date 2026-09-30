import argparse
import gzip
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta

from scripts.recolectar_calidad import (
    ERRORES_RED, ETIQUETAS_DESCARTE, guardar, normalizar, parte_de_repo, repos_excluidos, tipo_de_etiqueta,
)

URL_HORA = "https://data.gharchive.org/{}.json.gz"


def horas_entre(desde, hasta):
    actual = datetime.strptime(desde, "%Y-%m-%d")
    fin = datetime.strptime(hasta, "%Y-%m-%d") + timedelta(days=1)
    horas = []
    while actual < fin:
        horas.append(f"{actual:%Y-%m-%d}-{actual.hour}")
        actual += timedelta(hours=1)
    return horas


def es_bot(usuario):
    usuario = usuario or {}
    return usuario.get("type") == "Bot" or usuario.get("login", "").endswith("[bot]")


def evaluar_evento(evento, args, excluidos):
    if evento.get("type") != "IssuesEvent":
        return None, None
    carga = evento.get("payload") or {}
    if carga.get("action") != "labeled" or not carga.get("label"):
        return None, None
    tipo = tipo_de_etiqueta(carga["label"].get("name", ""))
    if not tipo:
        return None, None
    repo = (evento.get("repo") or {}).get("name", "")
    if not repo or parte_de_repo(repo, args.porcentaje_examen) == "examen":
        return None, "examen"
    if repo.lower() in excluidos:
        return None, "excluido"
    issue = carga.get("issue") or {}
    if issue.get("pull_request") or not issue.get("id"):
        return None, "pull_request"
    if (issue.get("created_at") or "")[:10] < args.desde:
        return None, "antiguo"
    autor = issue.get("user") or {}
    if es_bot(autor):
        return None, "bot"
    actor = evento.get("actor") or {}
    if es_bot(actor):
        return None, "etiqueta_de_bot"
    if actor.get("login") and actor.get("login") == autor.get("login"):
        return None, "etiqueta_del_autor"
    nombres = [e.get("name", "") for e in issue.get("labels") or []]
    if any(normalizar(n) in ETIQUETAS_DESCARTE for n in nombres):
        return None, "descartado"
    tipos = {tipo_de_etiqueta(n) for n in nombres} - {None}
    if tipos != {tipo}:
        return None, "ambiguo"
    cuerpo = issue.get("body") or ""
    if len(re.sub(r"\s+", " ", cuerpo).strip()) < args.min_caracteres:
        return None, "cuerpo_corto"
    return {
        "id": issue["id"],
        "labels": tipo,
        "title": issue.get("title") or "",
        "body": cuerpo,
        "repo": repo,
        "numero": issue.get("number"),
        "created_at": issue.get("created_at") or "",
        "state_reason": issue.get("state_reason") or "",
        "author_association": issue.get("author_association") or "",
        "etiqueta_original": carga["label"].get("name", ""),
        "etiquetado_por": actor.get("login", ""),
    }, "ok"


def procesar_hora(hora, args, excluidos):
    motivos = Counter()
    filas = []
    for intento in range(4):
        try:
            peticion = urllib.request.Request(URL_HORA.format(hora), headers={"User-Agent": "laya-triage"})
            with urllib.request.urlopen(peticion, timeout=120) as respuesta:
                with gzip.GzipFile(fileobj=respuesta) as archivo:
                    for linea in archivo:
                        try:
                            evento = json.loads(linea)
                        except ValueError:
                            continue
                        fila, motivo = evaluar_evento(evento, args, excluidos)
                        if motivo:
                            motivos[motivo] += 1
                        if fila:
                            filas.append(fila)
            return hora, filas, motivos
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return hora, [], motivos
            time.sleep(10 * (intento + 1))
        except (ERRORES_RED + (EOFError, gzip.BadGzipFile)):
            filas, motivos = [], Counter()
            time.sleep(10 * (intento + 1))
    return None, [], motivos


def leer_avance(ruta):
    filas, hechas = [], set()
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as archivo:
            for linea in archivo:
                registro = json.loads(linea)
                hechas.add(registro["hora"])
                filas.extend(registro["issues"])
    return filas, hechas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta", type=int, required=True)
    parser.add_argument("--desde", default="2025-01-01")
    parser.add_argument("--hasta", default="2026-09-27")
    parser.add_argument("--porcentaje-examen", type=int, default=35)
    parser.add_argument("--min-caracteres", type=int, default=30)
    parser.add_argument("--max-por-repo", type=int, default=300)
    parser.add_argument("--hilos", type=int, default=4)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--excluir", nargs="*", default=[
        "datos/github_reciente.csv", "datos/calidad/examen.csv", "datos/calidad/entrenamiento.csv",
    ])
    parser.add_argument("--salida", default="datos/calidad/gharchive.csv")
    args = parser.parse_args()

    avance = args.salida.replace(".csv", "_avance.jsonl")
    os.makedirs(os.path.dirname(args.salida) or ".", exist_ok=True)
    excluidos = repos_excluidos(args.excluir)
    horas = horas_entre(args.desde, args.hasta)
    random.Random(args.semilla).shuffle(horas)
    filas, hechas = leer_avance(avance)
    vistos = {f["id"] for f in filas}
    por_repo = Counter(f["repo"] for f in filas)
    pendientes = iter([h for h in horas if h not in hechas])
    print(f"{len(horas)} horas en el rango, {len(hechas)} ya revisadas, {len(filas)} issues guardados")

    motivos = Counter()
    en_curso = set()
    grupo = ThreadPoolExecutor(max_workers=args.hilos)
    inicio = time.time()
    revisadas = 0

    def lanzar():
        while len(en_curso) < args.hilos:
            hora = next(pendientes, None)
            if hora is None:
                return
            en_curso.add(grupo.submit(procesar_hora, hora, args, excluidos))

    try:
        with open(avance, "a", encoding="utf-8") as archivo:
            lanzar()
            while en_curso and len(filas) < args.meta:
                listos, _ = wait(en_curso, return_when=FIRST_COMPLETED)
                for futuro in listos:
                    en_curso.discard(futuro)
                    hora, nuevas, motivos_hora = futuro.result()
                    if hora is None:
                        print("    Una hora no se pudo descargar, la salto por ahora")
                        continue
                    motivos.update(motivos_hora)
                    aceptadas = []
                    for fila in nuevas:
                        if fila["id"] in vistos or por_repo[fila["repo"]] >= args.max_por_repo:
                            continue
                        vistos.add(fila["id"])
                        por_repo[fila["repo"]] += 1
                        aceptadas.append(fila)
                    filas.extend(aceptadas)
                    revisadas += 1
                    archivo.write(json.dumps({"hora": hora, "issues": aceptadas}, ensure_ascii=False) + "\n")
                    archivo.flush()
                    ritmo = revisadas / max(time.time() - inicio, 1) * 3600
                    print(f"[{hora}] +{len(aceptadas)} · total {len(filas)}/{args.meta} · {ritmo:.0f} horas de archivo por hora")
                    if revisadas % 20 == 0:
                        print(f"  Motivos hasta ahora: {dict(motivos)}")
                if len(filas) < args.meta:
                    lanzar()
    except KeyboardInterrupt:
        print("Interrumpido: guardo lo recolectado. Si vuelves a correr el mismo comando, sigue donde quedó")
    finally:
        grupo.shutdown(wait=False, cancel_futures=True)

    if not filas:
        print("No se recolectó ningún issue")
        return
    guardar(filas, args.salida)
    print(f"Motivos: {dict(motivos)}")


if __name__ == "__main__":
    main()