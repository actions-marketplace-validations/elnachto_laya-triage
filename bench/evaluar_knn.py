import argparse
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd
import torch
from laya import Router, embed_fn_from_agent

from bench.evaluar import CLASES, MAPA_ETIQUETAS, calcular_metricas, leer_config_triage
from bench.variantes import VARIANTES
from repo import mezcla_desde_conteos, pesos_para_ruta
from triage import UMBRAL_TIPO, limpiar_cuerpo


def ajustar(probabilidades, pesos):
    if not pesos:
        return dict(probabilidades)
    ajustadas = {c: probabilidades.get(c, 0.0) * pesos.get(c, 1.0) for c in CLASES}
    total = sum(ajustadas.values()) or 1.0
    return {c: v / total for c, v in ajustadas.items()}


def mezclas_por_repo(repos, reales):
    conteos = {}
    for repo, real in zip(repos, reales):
        conteos.setdefault(repo, {c: 0 for c in CLASES})[real] += 1
    mezclas = []
    for repo, real in zip(repos, reales):
        historial = dict(conteos[repo])
        historial[real] -= 1
        mezclas.append(mezcla_desde_conteos(historial))
    return mezclas


def vecinos_pasados(ids, repos, vectores, k_max):
    por_repo = defaultdict(list)
    for i, repo in enumerate(repos):
        por_repo[repo].append(i)
    vecinos = [[] for _ in ids]
    for indices in por_repo.values():
        indices = sorted(indices, key=lambda i: ids[i])
        bloque = vectores[indices]
        similitudes = bloque @ bloque.T
        for posicion, i in enumerate(indices):
            if posicion == 0:
                continue
            fila = similitudes[posicion, :posicion]
            orden = np.argsort(-fila)[:k_max]
            vecinos[i] = [(indices[j], float(fila[j])) for j in orden]
    return vecinos


def voto(vecinos, reales, k, minimo, temperatura):
    elegidos = vecinos[:k]
    if len(elegidos) < minimo:
        return None
    pesos = np.exp(np.array([s for _, s in elegidos]) / temperatura)
    conteo = {c: 0.0 for c in CLASES}
    for (j, _), peso in zip(elegidos, pesos):
        conteo[reales[j]] += float(peso)
    total = sum(conteo.values()) or 1.0
    return {c: v / total for c, v in conteo.items()}


def fusionar(m, v, w, fusion):
    if v is None or w == 0:
        return m
    if fusion == "lineal":
        return {c: (1 - w) * m[c] + w * v[c] for c in CLASES}
    crudas = {c: (m[c] ** (1 - w)) * ((v[c] + 0.02) ** w) for c in CLASES}
    total = sum(crudas.values()) or 1.0
    return {c: x / total for c, x in crudas.items()}


def precision_a_cobertura(reales, predichas, confianzas, cobertura):
    orden = sorted(range(len(reales)), key=lambda i: -confianzas[i])[: max(1, round(len(reales) * cobertura))]
    return sum(reales[i] == predichas[i] for i in orden) / len(orden)


def medir(reales, probabilidades, cobertura_base=None):
    predichas = [max(p, key=p.get) for p in probabilidades]
    confianzas = [max(p.values()) for p in probabilidades]
    exactitud, f1_macro, por_clase = calcular_metricas(reales, predichas)
    cubiertos = [(r, p) for r, p, c in zip(reales, predichas, confianzas) if c >= UMBRAL_TIPO]
    resultado = {
        "exactitud": round(exactitud, 4),
        "f1_macro": round(f1_macro, 4),
        "cobertura_con_umbral": round(len(cubiertos) / len(reales), 4),
        "exactitud_con_umbral": round(sum(r == p for r, p in cubiertos) / len(cubiertos), 4) if cubiertos else 0.0,
        "f1_question": por_clase["question"]["f1"],
        "f1_docs": por_clase["docs"]["f1"],
    }
    if cobertura_base:
        resultado["precision_misma_cobertura"] = round(precision_a_cobertura(reales, predichas, confianzas, cobertura_base), 4)
    return resultado


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("muestra", nargs="?", default="datos/calidad/validacion_conjunta.csv")
    parser.add_argument("--nombre", default="knn_validacion")
    parser.add_argument("--modelo-ingles", required=True)
    parser.add_argument("--modelo-multilingue", required=True)
    parser.add_argument("--codificador", default="english", choices=["english", "multilingual"])
    parser.add_argument("--largo", type=int, default=256)
    parser.add_argument("--lote", type=int, default=32)
    parser.add_argument("--ks", default="20")
    parser.add_argument("--mezclas", default="0.2,0.3,0.4")
    parser.add_argument("--umbrales-duda", default="siempre,0.6,0.4,0.2")
    parser.add_argument("--vectores", default="completo,titulo0.5,titulo0.7")
    parser.add_argument("--temperatura", type=float, default=0.05)
    parser.add_argument("--minimo", type=int, default=5)
    parser.add_argument("--fusiones", default="geometrica")
    parser.add_argument("--dispositivo", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    datos = pd.read_csv(args.muestra).fillna("")
    reales = [MAPA_ETIQUETAS[e] for e in datos["labels"]]
    repos = list(datos["repo"])
    ids = [int(i) for i in datos["id"]]
    cuerpos = [limpiar_cuerpo(str(b)) for b in datos["body"]]
    titulos = [str(t) for t in datos["title"]]

    rutas_modelo = {"english": args.modelo_ingles, "multilingual": args.modelo_multilingue}
    bases = {ruta: leer_config_triage(carpeta).get("mezcla_base") for ruta, carpeta in rutas_modelo.items()}
    router = Router(models=rutas_modelo, default="multilingual", device=args.dispositivo)
    pregunta = VARIANTES["sin_other"]
    peticiones = [{"state": {"title": t, "body": b}, "questions": {"tipo": pregunta}} for t, b in zip(titulos, cuerpos)]
    print(f"Clasificando {len(peticiones)} issues")
    resultados = router.predict_batch(peticiones, batch_size=args.lote)

    mezclas = mezclas_por_repo(repos, reales)
    modelo = []
    for r, mezcla in zip(resultados, mezclas):
        ruta = r["routing"]["model"]
        probabilidades = r["answers"]["tipo"]["probabilities"]
        pesos = pesos_para_ruta(mezcla, None, bases.get(ruta)) if mezcla else None
        modelo.append(ajustar(probabilidades, pesos))

    print(f"Calculando vectores con el codificador {args.codificador}")
    incrustar = embed_fn_from_agent(router.load(args.codificador), max_length=args.largo, batch_size=args.lote)
    normalizar_filas = lambda m: m / np.linalg.norm(m, axis=1, keepdims=True).clip(min=1e-9)
    completos = normalizar_filas(np.asarray(incrustar([f"{t}\n\n{b}"[:4000] for t, b in zip(titulos, cuerpos)]), dtype=np.float32))
    modos = args.vectores.split(",")
    if any(m != "completo" for m in modos):
        de_titulo = normalizar_filas(np.asarray(incrustar(titulos), dtype=np.float32))
        de_cuerpo = normalizar_filas(np.asarray(incrustar([b[:4000] or t for t, b in zip(titulos, cuerpos)]), dtype=np.float32))

    ks = [int(k) for k in args.ks.split(",")]
    pesos_mezcla = [float(w) for w in args.mezclas.split(",")]
    umbrales = [None if u == "siempre" else float(u) for u in args.umbrales_duda.split(",")]
    margenes = [sorted(m.values(), reverse=True)[0] - sorted(m.values(), reverse=True)[1] for m in modelo]

    base_total = medir(reales, modelo)
    cobertura_base = base_total["cobertura_con_umbral"]
    base_total = medir(reales, modelo, cobertura_base)
    print(f"\nSolo el modelo (como la v1.1): {base_total}")
    tabla = []
    for modo in modos:
        if modo == "completo":
            vectores = completos
        else:
            gamma = float(modo.replace("titulo", ""))
            vectores = normalizar_filas(gamma * de_titulo + (1 - gamma) * de_cuerpo)
        vecinos = vecinos_pasados(ids, repos, vectores, max(ks))
        for fusion in args.fusiones.split(","):
            for k in ks:
                votos = [voto(v, reales, k, args.minimo, args.temperatura) for v in vecinos]
                print(f"\nVectores {modo}, fusión {fusion}, k={k}")
                for umbral in umbrales:
                    activos = [v if (v is not None and (umbral is None or margen <= umbral)) else None for v, margen in zip(votos, margenes)]
                    usados = sum(v is not None for v in activos)
                    for w in pesos_mezcla:
                        mezcladas = [fusionar(m, v, w, fusion) for m, v in zip(modelo, activos)]
                        total = medir(reales, mezcladas, cobertura_base)
                        tabla.append({"vectores": modo, "fusion": fusion, "k": k, "umbral_duda": umbral, "peso_vecinos": w,
                                      "issues_con_vecinos": usados, "total": total})
                        etiqueta = "siempre" if umbral is None else f"margen<={umbral}"
                        print(f"  {etiqueta:12} peso {w:.1f} (usa vecinos en {usados:4d}): exactitud {total['exactitud']:.4f} · "
                              f"F1 {total['f1_macro']:.4f} · question {total['f1_question']:.3f} · "
                              f"cobertura {total['cobertura_con_umbral']:.3f} a {total['exactitud_con_umbral']:.3f} · "
                              f"misma cobertura {total['precision_misma_cobertura']:.4f}")

    mejor = max(tabla, key=lambda fila: (fila["total"]["f1_macro"], fila["total"]["exactitud"]))
    print(f"\nMejor combinación: vectores {mejor['vectores']}, fusión {mejor['fusion']}, k={mejor['k']}, "
          f"umbral de duda {mejor['umbral_duda']}, peso {mejor['peso_vecinos']} → {mejor['total']}")

    informe = {
        "modelo": args.nombre,
        "muestra": args.muestra,
        "codificador": args.codificador,
        "largo": args.largo,
        "temperatura": args.temperatura,
        "minimo": args.minimo,
        "cobertura_base": cobertura_base,
        "solo_modelo": base_total,
        "tabla": tabla,
        "mejor": mejor,
    }
    os.makedirs("bench/resultados", exist_ok=True)
    with open(f"bench/resultados/{args.nombre}.json", "w", encoding="utf-8") as archivo:
        json.dump(informe, archivo, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
