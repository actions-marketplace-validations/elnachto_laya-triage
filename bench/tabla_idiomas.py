import json
import os

IDIOMAS = ["en", "de", "pt", "es", "id", "fr", "vi", "ru", "tr", "zh", "ja", "ar", "hi", "ko"]


def leer(nombre):
    ruta = f"bench/resultados/{nombre}.json"
    return json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else None


def main():
    print(f"{'idioma':7} {'exactitud antes':>16} {'ahora':>7} {'F1 antes':>9} {'ahora':>7} {'cambio F1':>10}")
    for idioma in IDIOMAS:
        antes, ahora = leer(f"ml_actual_{idioma}"), leer(f"ml_nuevo_{idioma}")
        if not antes or not ahora:
            print(f"{idioma:7} falta el resultado")
            continue
        cambio = ahora["f1_macro"] - antes["f1_macro"]
        print(f"{idioma:7} {antes['exactitud']:16.3f} {ahora['exactitud']:7.3f} {antes['f1_macro']:9.3f} {ahora['f1_macro']:7.3f} {cambio:+10.3f}")


if __name__ == "__main__":
    main()
    