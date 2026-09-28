import json
import os

PARES = [("validación", "val_def_ml", "val_def_en"), ("issues 2026", "reciente_final", "reciente_def_en")]
PARES += [(f"traducido {l}", f"ml_nuevo_{l}", f"ml_def_en_{l}") for l in ["es", "pt", "fr", "de", "id", "vi", "tr"]]


def leer(nombre):
    ruta = f"bench/resultados/{nombre}.json"
    return json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else None


def main():
    print(f"{'examen':16} {'exactitud ml':>13} {'en':>7} {'F1 ml':>7} {'en':>7} {'al inglés ml':>13} {'en':>6}")
    for nombre, a, b in PARES:
        ml, en = leer(a), leer(b)
        if not ml or not en:
            print(f"{nombre:16} falta el resultado")
            continue
        print(f"{nombre:16} {ml['exactitud']:13.3f} {en['exactitud']:7.3f} {ml['f1_macro']:7.3f} {en['f1_macro']:7.3f} "
              f"{ml['rutas'].get('english', 0):13d} {en['rutas'].get('english', 0):6d}")
    for nombre in ("val_def_ml", "val_def_en"):
        d = leer(nombre)
        if d:
            print(f"{nombre}: cobertura {d['cobertura_con_umbral']} con precisión {d['exactitud_con_umbral']} | por ruta {d['por_ruta']}")


if __name__ == "__main__":
    main()