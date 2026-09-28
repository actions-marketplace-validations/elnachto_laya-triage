import json
import os

IDIOMAS = ["en", "de", "pt", "es", "id", "fr", "vi", "ru", "tr", "zh", "ja", "ar", "hi", "ko"]
EXAMENES = [
    ("Test sellado NLBSE'23", [("laya-triage", "TEST_FINAL"), ("Jev", "jev_test"), ("laya-issue-triage", "rival_en_nuestro_test")], "rival_1"),
    ("Issues reales 2026", [("laya-triage", "reciente_final"), ("Jev", "jev_reciente"), ("laya-issue-triage", "rival_reciente")], "rival_2"),
    ("Test del rival", [("laya-triage con priores", "nuestro_en_rival"), ("laya-triage sin priores", "nuestro_en_rival_sin_priores")], "rival_3"),
]


def leer(nombre):
    ruta = f"bench/resultados/{nombre}.json"
    return json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else None


def ultimas_lineas(log, n=6):
    ruta = f"logs/{log}.txt"
    if not os.path.exists(ruta):
        return "  (sin log)"
    with open(ruta, encoding="utf-8", errors="replace") as archivo:
        return "".join("  | " + linea for linea in archivo.readlines()[-n:])


def main():
    for titulo, filas, log in EXAMENES:
        print(f"\n== {titulo} ==")
        for nombre, archivo in filas:
            d = leer(archivo)
            if not d:
                print(f"{nombre:26} falta {archivo}")
                continue
            extra = ""
            if "costo_usd" in d:
                extra = f" · ${d['costo_usd']} · latencia mediana {d['latencia_ms']['mediana']} ms"
            elif "ms_por_issue" in d:
                extra = f" · {d['ms_por_issue']} ms/issue"
            print(f"{nombre:26} exactitud {d['exactitud']:.3f} · F1 macro {d['f1_macro']:.3f} · "
                  f"cubre {d['cobertura_con_umbral']:.3f} con {d['exactitud_con_umbral']:.3f}{extra}")
            clases = ", ".join(f"{k}: {v['f1']}" for k, v in d["por_clase"].items())
            print(f"{'':26} F1 por clase {clases}")
        if any(leer(a) is None for _, a in filas):
            print(f"  log {log}:\n{ultimas_lineas(log)}")

    print("\n== 14 idiomas (exactitud) ==")
    print(f"{'idioma':7} {'Laya base':>10} {'Jev':>7} {'laya-triage':>12}")
    for idioma in IDIOMAS:
        base, jev, nuestro = leer(f"ml_actual_{idioma}"), leer(f"jev_{idioma}"), leer(f"ml_nuevo_{idioma}")
        valor = lambda d: f"{d['exactitud']:.3f}" if d else "falta"
        print(f"{idioma:7} {valor(base):>10} {valor(jev):>7} {valor(nuestro):>12}")


if __name__ == "__main__":
    main()