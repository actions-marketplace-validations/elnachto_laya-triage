import argparse
import json
import os
import random
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from openai import OpenAI

from bench.evaluar import CLASES, MAPA_ETIQUETAS, calcular_metricas
from bench.variantes import VARIANTES
from triage import UMBRAL_TIPO, limpiar_cuerpo

MODELO = "gpt-6-luna"
PRECIO_POR_MILLON = 0.10
CARACTERES_POR_TOKEN = 4
TOKENS_PREGUNTA = 150
UMBRALES = [round(0.40 + 0.05 * i, 2) for i in range(12)]


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


def pregunta_openai(variante):
    pregunta = VARIANTES[variante]
    return {
        "type": "choice",
        "name": "tipo",
        "instructions": pregunta["instructions"],
        "choices": [{"value": clase, "description": descripcion} for clase, descripcion in pregunta["criteria"].items()],
    }


def texto_issue(titulo, cuerpo):
    return f"Title: {titulo}\n\nBody:\n{cuerpo}"


def estimar_tokens(texto):
    return len(texto) / CARACTERES_POR_TOKEN + TOKENS_PREGUNTA


def tokens_de(fila):
    usados = (fila.get("usage") or {}).get("input_tokens")
    return usados if usados else fila.get("tokens_estimados", 0)


def costo(tokens):
    return tokens * PRECIO_POR_MILLON / 1e6


def leer_cache(ruta):
    guardadas = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as archivo:
            for linea in archivo:
                fila = json.loads(linea)
                guardadas[str(fila["id"])] = fila
    return guardadas


def preguntar(cliente, pregunta, identificador, texto, intentos=6):
    for intento in range(intentos):
        try:
            inicio = time.perf_counter()
            decision = cliente.decisions.create(model=MODELO, input=texto, questions=[pregunta])
            milisegundos = (time.perf_counter() - inicio) * 1000
            datos = decision.model_dump()
            respuesta = datos["answers"][0]
            return {
                "id": identificador,
                "tipo": respuesta.get("type"),
                "choice": respuesta.get("choice"),
                "confidence": respuesta.get("confidence"),
                "probabilities": {p["value"]: p["probability"] for p in respuesta.get("probabilities") or []},
                "usage": datos.get("usage"),
                "tokens_estimados": round(estimar_tokens(texto)),
                "ms": round(milisegundos, 1),
            }
        except Exception as error:
            espera = min(60, 2 ** intento) + random.random()
            print(f"  Issue {identificador}: {type(error).__name__} ({error}); reintento en {espera:.0f} s")
            time.sleep(espera)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra")
    parser.add_argument("--nombre", default="openai_validacion")
    parser.add_argument("--variante", default="sin_other", choices=sorted(VARIANTES))
    parser.add_argument("--limite", type=int, default=0)
    parser.add_argument("--hilos", type=int, default=8)
    parser.add_argument("--largo-cuerpo", type=int, default=1500)
    parser.add_argument("--presupuesto", type=float, default=2.0)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    datos = pd.read_csv(args.muestra).fillna("")
    if args.limite:
        datos = datos.head(args.limite)
    reales = [MAPA_ETIQUETAS[e] for e in datos["labels"]]
    ids = [str(i) for i in datos["id"]]
    textos = [texto_issue(str(t), limpiar_cuerpo(str(b))[: args.largo_cuerpo]) for t, b in zip(datos["title"], datos["body"])]

    ruta_cache = f"datos/openai_cache/{args.nombre}.jsonl"
    os.makedirs(os.path.dirname(ruta_cache), exist_ok=True)
    guardadas = leer_cache(ruta_cache)
    pendientes = [(i, t) for i, t in zip(ids, textos) if i not in guardadas]
    estimados = sum(estimar_tokens(t) for _, t in pendientes)
    print(f"{len(datos)} issues · {len(guardadas)} ya respondidas · {len(pendientes)} por preguntar")
    print(f"Costo estimado de lo pendiente: ~{estimados / 1e6:.2f} M tokens de entrada · ~${costo(estimados):.2f}")
    if pendientes and not args.confirmar:
        print("Nada enviado. Vuelve a correrlo con --confirmar para preguntarle a la API.")
        return

    if pendientes:
        cliente = OpenAI()
        pregunta = pregunta_openai(args.variante)
        tokens = sum(tokens_de(f) for f in guardadas.values())
        tanda = args.hilos * 16
        with open(ruta_cache, "a", encoding="utf-8") as cache, ThreadPoolExecutor(args.hilos) as grupo:
            for inicio in range(0, len(pendientes), tanda):
                if costo(tokens) >= args.presupuesto:
                    print(f"Presupuesto de ${args.presupuesto} alcanzado: me detengo")
                    break
                tareas = [grupo.submit(preguntar, cliente, pregunta, i, t) for i, t in pendientes[inicio:inicio + tanda]]
                for tarea in as_completed(tareas):
                    fila = tarea.result()
                    if fila is None:
                        continue
                    cache.write(json.dumps(fila, ensure_ascii=False) + "\n")
                    guardadas[fila["id"]] = fila
                    tokens += tokens_de(fila)
                cache.flush()
                print(f"  {len(guardadas)} respondidas · ${costo(tokens):.3f}")

    faltan = [i for i in ids if i not in guardadas]
    if faltan:
        print(f"Faltan {len(faltan)} respuestas. Vuelve a correrlo con --confirmar para completarlas.")
        return

    filas = [guardadas[i] for i in ids]
    validas = [f["tipo"] == "choice" and f["choice"] in CLASES for f in filas]
    predichas = [f["choice"] if v else "refusal" for f, v in zip(filas, validas)]
    maximas = [max(f["probabilities"].values()) if v and f["probabilities"] else 0.0 for f, v in zip(filas, validas)]
    exactitud, f1_macro, por_clase = calcular_metricas(reales, predichas)
    cubiertos = [(r, p) for r, p, m in zip(reales, predichas, maximas) if m >= UMBRAL_TIPO]
    tokens = sum(tokens_de(f) for f in filas)
    latencias = sorted(f["ms"] for f in filas)

    informe = {
        "modelo": args.nombre,
        "modelo_openai": MODELO,
        "muestra": args.muestra,
        "variante": args.variante,
        "issues": len(filas),
        "issues_sin_respuesta": 0,
        "rechazos": len(filas) - sum(validas),
        "exactitud": round(exactitud, 3),
        "f1_macro": round(f1_macro, 3),
        "umbral": UMBRAL_TIPO,
        "cobertura_con_umbral": round(len(cubiertos) / len(filas), 3),
        "exactitud_con_umbral": round(sum(r == p for r, p in cubiertos) / max(1, len(cubiertos)), 3),
        "curva_prob_maxima": curva(reales, predichas, maximas),
        "latencia_ms": {"mediana": latencias[len(latencias) // 2], "p95": latencias[int(len(latencias) * 0.95)]},
        "tokens_entrada": round(tokens),
        "tokens_reales": all((f.get("usage") or {}).get("input_tokens") for f in filas),
        "costo_usd": round(costo(tokens), 4),
        "por_clase": por_clase,
        "confusion": Counter(f"{r}->{p}" for r, p in zip(reales, predichas) if r != p).most_common(8),
    }
    os.makedirs("bench/resultados", exist_ok=True)
    with open(f"bench/resultados/{args.nombre}.json", "w", encoding="utf-8") as archivo:
        json.dump(informe, archivo, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in informe.items() if k != "curva_prob_maxima"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()