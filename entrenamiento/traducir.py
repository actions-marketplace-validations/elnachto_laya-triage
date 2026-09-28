import argparse
import os
import re
import time

import pandas as pd
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from triage import limpiar_cuerpo

IDIOMAS = {
    "zh": "zho_Hans",
    "es": "spa_Latn",
    "hi": "hin_Deva",
    "pt": "por_Latn",
    "ru": "rus_Cyrl",
    "ja": "jpn_Jpan",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "ko": "kor_Hang",
    "vi": "vie_Latn",
    "id": "ind_Latn",
    "tr": "tur_Latn",
    "ar": "arb_Arab",
}
VALLA = re.compile(r"^\s*(```|~~~)")
LETRAS = re.compile(r"[A-Za-z]")
MENSAJE_ERROR = re.compile(r"\b\w*(Error|Exception|Warning)\b\s*[:(]")


def es_codigo(linea):
    texto = linea.strip()
    if not texto:
        return True
    letras = len(LETRAS.findall(texto))
    return letras / len(texto) < 0.5 or texto.startswith(("at ", "File \"", "Traceback", "$ ", ">>> ")) or "`" in texto or bool(MENSAJE_ERROR.search(texto))


def segmentar(texto):
    partes = []
    en_codigo = False
    for linea in texto.splitlines():
        if VALLA.match(linea):
            en_codigo = not en_codigo
            partes.append((linea, False))
            continue
        partes.append((linea, not en_codigo and not es_codigo(linea)))
    return partes


def elegir(datos, por_clase, total, semilla):
    if por_clase:
        return pd.concat(
            grupo.sample(min(por_clase, len(grupo)), random_state=semilla)
            for _, grupo in datos.groupby("labels")
        ).sample(frac=1, random_state=semilla)
    return datos.sample(min(total, len(datos)), random_state=semilla)


class Traductor:
    def __init__(self, modelo, dispositivo, lote, max_tokens, haces):
        self.tok = AutoTokenizer.from_pretrained(modelo, src_lang="eng_Latn")
        tipo = torch.float16 if dispositivo == "cuda" else torch.float32
        self.modelo = AutoModelForSeq2SeqLM.from_pretrained(modelo, torch_dtype=tipo).to(dispositivo).eval()
        self.dispositivo = dispositivo
        self.lote = lote
        self.max_tokens = max_tokens
        self.haces = haces

    @torch.no_grad()
    def traducir(self, textos, codigo):
        destino = self.tok.convert_tokens_to_ids(codigo)
        orden = sorted(range(len(textos)), key=lambda i: len(textos[i]))
        salida = [""] * len(textos)
        for inicio in range(0, len(orden), self.lote):
            indices = orden[inicio:inicio + self.lote]
            entrada = self.tok(
                [textos[i] for i in indices], return_tensors="pt", padding=True,
                truncation=True, max_length=self.max_tokens,
            ).to(self.dispositivo)
            generado = self.modelo.generate(
                **entrada, forced_bos_token_id=destino,
                max_new_tokens=int(self.max_tokens * 1.5), num_beams=self.haces,
            )
            for i, texto in zip(indices, self.tok.batch_decode(generado, skip_special_tokens=True)):
                salida[i] = texto
        return salida


def traducir_filas(traductor, filas, codigo):
    segmentos = []
    planes = []
    for titulo, cuerpo in filas:
        segmentos.append(titulo)
        partes = segmentar(cuerpo)
        planes.append(partes)
        segmentos.extend(linea for linea, traducible in partes if traducible)
    traducidos = iter(traductor.traducir(segmentos, codigo))
    resultado = []
    for partes in planes:
        titulo = next(traducidos)
        lineas = [next(traducidos) if traducible else linea for linea, traducible in partes]
        resultado.append((titulo, "\n".join(lineas)))
    return resultado


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("entrada")
    parser.add_argument("--carpeta", required=True)
    parser.add_argument("--idiomas", default=",".join(IDIOMAS))
    parser.add_argument("--por-clase", type=int, default=0)
    parser.add_argument("--total", type=int, default=500)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--modelo", default="facebook/nllb-200-distilled-600M")
    parser.add_argument("--lote", type=int, default=32)
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--haces", type=int, default=1)
    parser.add_argument("--dispositivo", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    datos = pd.read_csv(args.entrada).fillna("")
    elegidos = elegir(datos, args.por_clase, args.total, args.semilla)
    filas = [(str(t), limpiar_cuerpo(str(c))) for t, c in zip(elegidos["title"], elegidos["body"])]
    os.makedirs(args.carpeta, exist_ok=True)
    elegidos.assign(title=[t for t, _ in filas], body=[c for _, c in filas], idioma="en")[
        ["id", "labels", "title", "body", "idioma"]
    ].to_csv(os.path.join(args.carpeta, "en.csv"), index=False)
    print(f"{len(filas)} issues elegidos; original en inglés guardado en {args.carpeta}\\en.csv")

    traductor = Traductor(args.modelo, args.dispositivo, args.lote, args.max_tokens, args.haces)
    for idioma in args.idiomas.split(","):
        ruta = os.path.join(args.carpeta, f"{idioma}.csv")
        if os.path.exists(ruta):
            print(f"{idioma}: ya existe, se salta")
            continue
        inicio = time.perf_counter()
        traducidas = traducir_filas(traductor, filas, IDIOMAS[idioma])
        elegidos.assign(
            title=[t for t, _ in traducidas], body=[c for _, c in traducidas], idioma=idioma
        )[["id", "labels", "title", "body", "idioma"]].to_csv(ruta, index=False)
        print(f"{idioma}: {len(traducidas)} issues en {time.perf_counter() - inicio:.0f} s")
        print(f"   ejemplo: {traducidas[0][0][:100]}")


if __name__ == "__main__":
    main()