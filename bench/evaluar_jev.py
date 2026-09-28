import argparse
import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from typesafe_sdk import TypeSafeClient, TypeSafeError

from bench.evaluar import MAPA_ETIQUETAS, calcular_metricas
from bench.variantes import VARIANTES
from triage import UMBRAL_TIPO, limpiar_cuerpo

PRECIO_POR_MILLON = 0.042
UMBRALES = [round(0.40 + 0.05 * i, 2) for i in range(12)]


def leer_cache(ruta):
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as archivo:
        return {str(fila["id"]): fila for fila in map(json.loads, archivo) if fila.get("choice")}


def preguntar(cliente, pregunta, fila):
    estado = {"title": str(fila["title"]), "body": limpiar_cuerpo(str(fila["body"]))}
    inicio = time.perf_counter()
    respuesta = cliente.system_one(state=estado, questions={"tipo": pregunta})
    milisegundos = (time.perf_counter() - inicio) * 1000
    tipo = respuesta.choices["tipo"]
    return {
        "id": str(fila["id"]),
        "choice": tipo.choice,
        "confidence": tipo.confidence,
        "probabilities": dict(tipo.probabilities),
        "tokens": respuesta.usage.input_tokens or 0,
        "ms": round(milisegundos, 1),
        "modelo": respuesta.model,
    }


def curva(reales, predichas, confianzas):
    puntos = []
    for umbral in UMBRALES:
        elegidos = [(r, p) for r, p, c in zip(reales, predichas, confianzas) if c >= umbral]
        puntos.append({
            "umbral": umbral,
            "cobertura": round(len(elegidos) / len(reales), 3),
            "precision": round(sum(r == p for r, p in elegidos) / len(elegidos), 3) if elegidos else None,
        })
    return puntos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra")
    parser.add_argument("--nombre", default="jev")
    parser.add_argument("--variante", default="sin_other", choices=sorted(VARIANTES))
    parser.add_argument("--modelo", default="jev-latest")
    parser.add_argument("--limite", type=int, default=0)
    parser.add_argument("--hilos", type=int, default=4)
    parser.add_argument("--presupuesto", type=float, default=1.0)
    args = parser.parse_args()

    if not os.environ.get("TYPESAFE_API_KEY"):
        raise SystemExit("Falta TYPESAFE_API_KEY: ponla en la terminal con set TYPESAFE_API_KEY=...")

    datos = pd.read_csv(args.muestra).fillna("")
    if args.limite:
        datos = datos.head(args.limite)
    pregunta = VARIANTES[args.variante]
    ruta_cache = f"bench/resultados/{args.nombre}_respuestas.jsonl"
    os.makedirs("bench/resultados", exist_ok=True)
    cache = leer_cache(ruta_cache)
    pendientes = [fila for fila in datos.to_dict("records") if str(fila["id"]) not in cache]
    tokens_previos = sum(r["tokens"] for r in cache.values())
    print(f"{len(datos)} issues: {len(cache)} ya respondidos, {len(pendientes)} pendientes")

    tokens = tokens_previos
    errores = Counter()
    tanda = args.hilos * 16
    with TypeSafeClient(model=args.modelo) as cliente, open(ruta_cache, "a", encoding="utf-8") as salida:
        with ThreadPoolExecutor(max_workers=args.hilos) as grupo:
            for inicio in range(0, len(pendientes), tanda):
                if tokens * PRECIO_POR_MILLON / 1e6 >= args.presupuesto:
                    print(f"Presupuesto de ${args.presupuesto} alcanzado: me detengo")
                    break
                futuros = [grupo.submit(preguntar, cliente, pregunta, fila) for fila in pendientes[inicio:inicio + tanda]]
                for futuro in as_completed(futuros):
                    try:
                        respuesta = futuro.result()
                    except TypeSafeError as error:
                        errores[type(error).__name__] += 1
                        continue
                    cache[respuesta["id"]] = respuesta
                    tokens += respuesta["tokens"]
                    salida.write(json.dumps(respuesta, ensure_ascii=False) + "\n")
                salida.flush()
                print(f"  {len(cache)} respondidos · ${tokens * PRECIO_POR_MILLON / 1e6:.3f} · errores {dict(errores)}")

    filas = [fila for fila in datos.to_dict("records") if str(fila["id"]) in cache]
    if not filas:
        raise SystemExit(f"Ninguna respuesta de Jev. Errores: {dict(errores)}")
    respuestas = [cache[str(fila["id"])] for fila in filas]
    reales = [MAPA_ETIQUETAS[fila["labels"]] for fila in filas]
    predichas = [r["choice"] for r in respuestas]
    maximas = [max(r["probabilities"].values()) for r in respuestas]
    exactitud, f1_macro, por_clase = calcular_metricas(reales, predichas)
    latencias = sorted(r["ms"] for r in respuestas)

    informe = {
        "modelo": args.nombre,
        "modelo_jev": respuestas[0]["modelo"],
        "variante": args.variante,
        "issues": len(filas),
        "issues_sin_respuesta": len(datos) - len(filas),
        "errores": dict(errores),
        "exactitud": round(exactitud, 3),
        "f1_macro": round(f1_macro, 3),
        "umbral": UMBRAL_TIPO,
        "cobertura_con_umbral": round(sum(m >= UMBRAL_TIPO for m in maximas) / len(maximas), 3),
        "exactitud_con_umbral": round(
            sum(r == p for r, p, m in zip(reales, predichas, maximas) if m >= UMBRAL_TIPO)
            / max(1, sum(m >= UMBRAL_TIPO for m in maximas)), 3),
        "curva_prob_maxima": curva(reales, predichas, maximas),
        "latencia_ms": {"mediana": latencias[len(latencias) // 2], "p95": latencias[int(len(latencias) * 0.95)]},
        "tokens_entrada": tokens,
        "costo_usd": round(tokens * PRECIO_POR_MILLON / 1e6, 4),
        "por_clase": por_clase,
        "confusion": Counter(f"{r}->{p}" for r, p in zip(reales, predichas) if r != p).most_common(8),
    }
    with open(f"bench/resultados/{args.nombre}.json", "w", encoding="utf-8") as archivo:
        json.dump(informe, archivo, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in informe.items() if k != "curva_prob_maxima"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()