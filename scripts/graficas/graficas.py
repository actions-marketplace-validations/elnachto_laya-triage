import json, sys
from pathlib import Path

TEMAS = {
    "light": dict(fondo="#FBFAFD", tinta="#16141F", suave="#5D596E", tenue="#8E8AA0", rejilla="#E9E6F0",
                  laya="#6B3FE7", coral="#F2644B", neutro="#8A8699", pill="#EFEAFD"),
    "dark": dict(fondo="#16141F", tinta="#F4F2FA", suave="#B9B5C8", tenue="#8C889C", rejilla="#2A2736",
                 laya="#8B67F5", coral="#E85A42", neutro="#6E6A80", pill="#2A2240"),
}
W = 1600

def marco(t, titulo, subtitulo, cuerpo, alto, nota):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:Bri;src:url(BricolageGrotesque-Regular.ttf);font-weight:400}}
@font-face{{font-family:Bri;src:url(BricolageGrotesque-Bold.ttf);font-weight:700}}
@font-face{{font-family:Mono;src:url(JetBrainsMono-Regular.ttf);font-weight:400}}
@font-face{{font-family:Mono;src:url(JetBrainsMono-Bold.ttf);font-weight:700}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:{t['fondo']};width:{W}px}}
#c{{width:{W}px;height:{alto}px;padding:72px 88px 60px;background:{t['fondo']};color:{t['tinta']};font-family:Bri;position:relative}}
.marca{{font-family:Mono;font-size:20px;color:{t['suave']};display:flex;align-items:center;gap:12px;letter-spacing:.02em}}
.marca i{{width:14px;height:14px;border-radius:4px;background:{t['laya']};display:inline-block}}
h1{{font-size:56px;font-weight:700;letter-spacing:-.02em;margin-top:22px;line-height:1.05}}
h2{{font-size:24px;font-weight:400;color:{t['suave']};margin-top:14px;line-height:1.35}}
.nota{{position:absolute;left:88px;right:88px;bottom:44px;font-family:Mono;font-size:15px;color:{t['tenue']};line-height:1.5}}
svg text{{font-family:Bri}}
</style></head><body><div id="c"><div class="marca"><i></i>laya-triage · benchmark</div>
<h1>{titulo}</h1><h2>{subtitulo}</h2>{cuerpo}<div class="nota">{nota}</div></div></body></html>"""

def barras_h(t, filas, maximo, formato, ancho=W - 176, alto_fila=78, etiqueta_ancho=430):
    alto = len(filas) * alto_fila + 40
    x0, x1 = etiqueta_ancho, ancho - 150
    esc = lambda v: x0 + (x1 - x0) * v / maximo
    s = [f'<svg width="{ancho}" height="{alto}" style="margin-top:48px">']
    for v in [0, maximo * .25, maximo * .5, maximo * .75, maximo]:
        x = esc(v)
        s.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{alto-34}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="{x}" y="{alto-8}" fill="{t["tenue"]}" font-size="17" text-anchor="middle" style="font-family:Mono">{formato(v)}</text>')
    for i, f in enumerate(filas):
        y = i * alto_fila + 14
        color = t["laya"] if f.get("destacar") else t["neutro"]
        peso = 700 if f.get("destacar") else 400
        s.append(f'<text x="0" y="{y+22}" fill="{t["tinta"]}" font-size="26" font-weight="{peso}">{f["nombre"]}</text>')
        s.append(f'<text x="0" y="{y+50}" fill="{t["tenue"]}" font-size="17" style="font-family:Mono">{f["detalle"]}</text>')
        xe = esc(f["valor"]); h = 28; yb = y + 12
        s.append(f'<path d="M{x0},{yb} H{xe-6} Q{xe},{yb} {xe},{yb+6} V{yb+h-6} Q{xe},{yb+h} {xe-6},{yb+h} H{x0} Z" fill="{color}"/>')
        s.append(f'<text x="{xe+16}" y="{yb+22}" fill="{t["tinta"]}" font-size="26" font-weight="{peso}" style="font-family:Mono">{formato(f["valor"])}</text>')
    s.append("</svg>")
    return "".join(s)

def g_exactitud(t):
    filas = [
        dict(nombre="RoBERTa", detalle="NLBSE'23 baseline · trained on 1.27M issues", valor=89.1),
        dict(nombre="laya-triage", detalle="your runner · no API key", valor=88.8, destacar=True),
        dict(nombre="FastText", detalle="NLBSE'23 baseline", valor=85.1),
        dict(nombre="Jev", detalle="TypeSafe · hosted API · measured by us", valor=84.4),
        dict(nombre="Laya base", detalle="same router, not fine-tuned", valor=75.9),
        dict(nombre="laya-issue-triage", detalle="other Laya fine-tune · measured by us", valor=64.5),
    ]
    cuerpo = barras_h(t, filas, 100, lambda v: f"{v:.1f}%" if v not in (0, 25, 50, 75, 100) else f"{v:.0f}%")
    cuerpo += f'''<div style="display:flex;gap:28px;margin-top:40px">
{"".join(f'<div style="flex:1;background:{t["pill"]};border-radius:18px;padding:26px 30px"><div style="font-family:Mono;font-size:17px;color:{t["suave"]}">{a}</div><div style="font-size:52px;font-weight:700;margin-top:8px;letter-spacing:-.02em">{b}</div><div style="font-size:19px;color:{t["suave"]};margin-top:4px">{c}</div></div>' for a,b,c in [
("issues labeled automatically","94.1%","vs 57.1% for Laya base"),
("precision on those labels","91.1%","it abstains when unsure"),
("time per run","< 40 s","on a free GitHub runner")])}
</div>'''
    return marco(t, "Issue type accuracy", "Bug · feature · question · docs on NLBSE'23 issues, 4 classes.", cuerpo, 1160,
                 "laya-triage: fresh random 5,000-issue sample of the NLBSE'23 test set, measured once (±0.9 pts, 95%). Jev, Laya base, laya-issue-triage: another 5,000-issue sample of the same test set. RoBERTa / FastText: published results on the full test set.")

def g_2026(t):
    clases = [("Macro F1", .523, .660, .662), ("Bug", .615, .773, .692), ("Feature", .593, .699, .745), ("Question", .221, .387, .420), ("Docs", .665, .781, .791)]
    ancho = W - 176; alto = 470; x0 = 60; paso = (ancho - x0) / len(clases); bw = 46; esc = lambda v: 400 - 380 * v
    series = [(t["neutro"], 400), (t["coral"], 400), (t["laya"], 700)]
    s = [f'<svg width="{ancho}" height="{alto+40}" style="margin-top:34px">']
    for v in [0, .25, .5, .75, 1]:
        s.append(f'<line x1="{x0}" y1="{esc(v)}" x2="{ancho}" y2="{esc(v)}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="{x0-14}" y="{esc(v)+6}" fill="{t["tenue"]}" font-size="17" text-anchor="end" style="font-family:Mono">{v:.2f}</text>')
    for i, (n, *valores) in enumerate(clases):
        cx = x0 + paso * i + paso / 2
        for j, (v, (c, peso)) in enumerate(zip(valores, series)):
            x = cx + (j - 1.5) * (bw + 4); y = esc(v)
            s.append(f'<path d="M{x},{esc(0)} V{y+6} Q{x},{y} {x+6},{y} H{x+bw-6} Q{x+bw},{y} {x+bw},{y+6} V{esc(0)} Z" fill="{c}"/>')
            s.append(f'<text x="{x+bw/2}" y="{y-12}" fill="{t["tinta"]}" font-size="18" font-weight="{peso}" text-anchor="middle" style="font-family:Mono">{v:.2f}</text>')
        s.append(f'<text x="{cx}" y="{esc(0)+40}" fill="{t["tinta"]}" font-size="24" font-weight="{700 if i==0 else 400}" text-anchor="middle">{n}</text>')
    s.append("</svg>")
    leyenda = f'<div style="display:flex;gap:32px;margin-top:30px;font-size:21px;color:{t["suave"]}">' + "".join(
        f'<span><i style="display:inline-block;width:16px;height:16px;border-radius:4px;background:{c};margin-right:10px;vertical-align:-2px"></i>{e}</span>'
        for c, e in [(t["neutro"], "Laya base"), (t["coral"], "Jev (TypeSafe)"), (t["laya"], f'<b style="color:{t["tinta"]}">laya-triage</b>')]) + "</div>"
    return marco(t, "Issues it has never seen", "2,000 issues opened in 2026 across 1,145 repositories. F1 per class, higher is better.", leyenda + "".join(s), 900,
                 "Closed issues with a single type label, created since 2026-01-01, max 15 per repo, 500 per class. Same question and text for every model; laya-triage exactly as the action ships it.")


def g_curva(t):
    puntos = [("40k", 85.6, "balanced + priors"), ("150k", 86.8, "balanced + priors"), ("500k", 88.1, "natural mix"), ("1M", 88.4, "natural mix")]
    ancho = W - 176; alto = 520; x0, x1 = 90, ancho - 120; lo, hi = 84, 90
    ex = lambda i: x0 + (x1 - x0) * i / 3; ey = lambda v: 470 - 440 * (v - lo) / (hi - lo)
    s = [f'<svg width="{ancho}" height="{alto+30}" style="margin-top:40px">']
    for v in range(lo, hi + 1, 1):
        s.append(f'<line x1="{x0-20}" y1="{ey(v)}" x2="{x1+20}" y2="{ey(v)}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="{x0-34}" y="{ey(v)+6}" fill="{t["tenue"]}" font-size="17" text-anchor="end" style="font-family:Mono">{v}%</text>')
    s.append(f'<line x1="{x0-20}" y1="{ey(89.1)}" x2="{x1+20}" y2="{ey(89.1)}" stroke="{t["neutro"]}" stroke-width="2" stroke-dasharray="8 8"/>')
    s.append(f'<text x="{x0-10}" y="{ey(89.1)-14}" fill="{t["suave"]}" font-size="19">RoBERTa, NLBSE\'23 baseline · 89.1%</text>')
    pts = " ".join(f"{ex(i)},{ey(v)}" for i, (_, v, _) in enumerate(puntos))
    s.append(f'<polyline points="{pts}" fill="none" stroke="{t["laya"]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    for i, (n, v, d) in enumerate(puntos):
        s.append(f'<circle cx="{ex(i)}" cy="{ey(v)}" r="8" fill="{t["laya"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<text x="{ex(i)}" y="{ey(v)+40}" fill="{t["tinta"]}" font-size="22" font-weight="{700 if i == 3 else 400}" text-anchor="middle" style="font-family:Mono">{v:.1f}%</text>')
        s.append(f'<text x="{ex(i)}" y="{alto-2}" fill="{t["tinta"]}" font-size="22" text-anchor="middle" style="font-family:Mono">{n}</text>')
        s.append(f'<text x="{ex(i)}" y="{alto+24}" fill="{t["tenue"]}" font-size="17" text-anchor="middle">{d}</text>')
    s.append("</svg>")
    return marco(t, "More data, closer to the baseline", "Validation accuracy of the English model by number of training issues.", "".join(s), 960,
                 "5,000 NLBSE'23 validation issues, natural class mix. One epoch each on a single RTX 5070; 1M issues took 12 hours.")

def g_idiomas(t):
    datos = [("English", 89.2, 88.2, 90.6), ("German", 74.6, 85.8, 87.4), ("Vietnamese", 71.2, 84.4, 86.6), ("Chinese", 68.2, 83.8, 86.2),
             ("Japanese", 67.8, 84.4, 86.0), ("Turkish", 68.2, 85.0, 85.8), ("Indonesian", 73.8, 86.0, 85.6), ("Spanish", 73.8, 85.6, 85.2),
             ("Hindi", 66.2, 85.4, 85.0), ("Portuguese", 74.0, 86.6, 84.8), ("Russian", 70.8, 85.8, 84.6), ("Korean", 64.2, 83.8, 84.4),
             ("French", 71.6, 85.2, 84.2), ("Arabic", 67.4, 84.8, 84.0)]
    ancho = W - 176; fila = 50; x0, x1 = 230, ancho - 120; lo, hi = 60, 95
    ex = lambda v: x0 + (x1 - x0) * (v - lo) / (hi - lo)
    alto = len(datos) * fila + 50
    s = [f'<svg width="{ancho}" height="{alto}" style="margin-top:36px">']
    for v in range(lo, hi + 1, 5):
        s.append(f'<line x1="{ex(v)}" y1="0" x2="{ex(v)}" y2="{alto-40}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="{ex(v)}" y="{alto-12}" fill="{t["tenue"]}" font-size="17" text-anchor="middle" style="font-family:Mono">{v}%</text>')
    for i, (n, a, j, b) in enumerate(datos):
        y = i * fila + 22
        s.append(f'<text x="0" y="{y+8}" fill="{t["tinta"]}" font-size="23" font-weight="{700 if i==0 else 400}">{n}</text>')
        s.append(f'<line x1="{ex(min(a, j))}" y1="{y}" x2="{ex(max(j, b))}" y2="{y}" stroke="{t["rejilla"]}" stroke-width="3" stroke-linecap="round"/>')
        s.append(f'<circle cx="{ex(a)}" cy="{y}" r="8" fill="{t["neutro"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<rect x="{ex(j)-8}" y="{y-8}" width="16" height="16" rx="3" transform="rotate(45 {ex(j)} {y})" fill="{t["coral"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<circle cx="{ex(b)}" cy="{y}" r="9" fill="{t["laya"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<text x="{ex(max(j, b))+24}" y="{y+7}" fill="{t["tinta"]}" font-size="20" font-weight="700" style="font-family:Mono">{b:.1f}%</text>')
        s.append(f'<text x="{ex(min(a, j))-20}" y="{y+7}" fill="{t["suave"]}" font-size="18" text-anchor="end" style="font-family:Mono">{a:.1f}</text>')
    s.append("</svg>")
    marca = lambda forma, c: (f'<i style="display:inline-block;width:14px;height:14px;background:{c};margin-right:10px;vertical-align:-1px;'
                             + ("transform:rotate(45deg);border-radius:3px" if forma == "rombo" else "border-radius:50%") + '"></i>')
    leyenda = f'<div style="display:flex;gap:32px;margin-top:30px;font-size:21px;color:{t["suave"]}">' + "".join(
        f'<span>{marca(f, c)}{e}</span>' for f, c, e in [("c", t["neutro"], "Laya base"), ("rombo", t["coral"], "Jev (TypeSafe, hosted)"),
                                                       ("c", t["laya"], f'<b style="color:{t["tinta"]}">laya-triage</b> (value shown)')]) + "</div>"
    return marco(t, "Every language, not just English", "The same 500 issues in 14 languages. Accuracy, higher is better.", leyenda + "".join(s), 1180,
                 "Machine-translated with NLLB-200; training used different issues. ±3 pts per language (500 issues). laya-triage and Jev are within noise of each other.")


def g_comparativa(t):
    ok = lambda x: f'<span style="color:{t["tinta"]};font-weight:700">{x}</span>'
    no = lambda x: f'<span style="color:{t["tenue"]}">{x}</span>'
    filas = [
        ("laya-triage", "Laya fine-tuned · Action", ok("88.8%"), ok("$0"), ok("stays in your runner"), ok("none"), ok("14 measured"), ok("calibrated, abstains")),
        ("Jev", "TypeSafe · hosted decision API", "84.4%", "~$0.024 per 1k issues", "TypeSafe's servers", "key (waitlist)", "14 measured by us", "probabilities"),
        ("laya-issue-triage", "other Laya fine-tune · Action", "64.5%", "$0", "stays in your runner", "none", "English", "min-confidence"),
        ("NLBSE'23 research", "RoBERTa · FastText", "85.1–89.1%", no("not a GitHub tool"), "local", "none", "English", no("—")),
        ("ai-assessment-comment-labeler", "GitHub · GitHub Models", no("not published"), "$0 up to 150 req/day*", "GitHub Models", "none", no("—"), no("—")),
        ("ai-labeler", "jlowin · OpenAI / Anthropic", no("not published"), "~$5 per 10k PRs†", "OpenAI or Anthropic", "paid key", no("—"), no("—")),
        ("Dosu", "hosted service", no("not published"), "free tier · Pro $16/mo", "Dosu's servers", "none (app)", no("—"), no("—")),
        ("issue-labeler", "GitHub · regex rules", no("n/a, rules"), "$0", "stays in your runner", "none", "rule-based", no("—")),
    ]
    cab = ["Accuracy<br>NLBSE'23 test", "Cost<br>public repo", "Where issue<br>text goes", "Extra<br>API key", "Languages", "Confidence"]
    th = "".join(f'<th style="text-align:left;font-family:Mono;font-weight:400;font-size:16px;color:{t["suave"]};padding:0 14px 18px;line-height:1.35">{c}</th>' for c in cab)
    trs = []
    for i, f in enumerate(filas):
        fondo = t["pill"] if i == 0 else "transparent"
        borde = "none" if i == 0 else f"1px solid {t['rejilla']}"
        celdas = "".join(f'<td style="padding:22px 14px;font-size:20px;vertical-align:middle">{c}</td>' for c in f[2:])
        marca = f'<i style="display:inline-block;width:12px;height:12px;border-radius:3px;background:{t["laya"]};margin-right:10px"></i>' if i == 0 else ""
        trs.append(f'<tr style="background:{fondo};border-top:{borde}"><td style="padding:22px 14px 22px 24px;border-radius:16px 0 0 16px"><div style="font-size:23px;font-weight:{700 if i==0 else 400}">{marca}{f[0]}</div><div style="font-family:Mono;font-size:15px;color:{t["tenue"]};margin-top:6px">{f[1]}</div></td>{celdas}</tr>')
    tabla = f'<table style="width:100%;border-collapse:collapse;margin-top:44px;color:{t["tinta"]}"><tr><th></th>{th}</tr>{"".join(trs)}</table>'
    return marco(t, "Why laya-triage", "Issue triage for GitHub, compared on what maintainers actually care about.", tabla, 1330,
                 "Accuracy for laya-triage, Jev and laya-issue-triage measured by us on random 5,000-issue samples of the NLBSE'23 test set. Figures as of Sep 2026, from each project's docs. * GitHub Models free tier, low-tier models. † the project's own gpt-4o-mini estimate. — not published.")

def g_cien(t):
    modelos = [("Laya base", 50.9, 6.2, 42.9), ("Jev", 82.4, 12.7, 4.9), ("laya-triage", 85.7, 8.4, 5.9)]
    ancho = W - 176; x0 = 250; x1 = ancho - 20; esc = lambda v: (x1 - x0) * v / 100
    s = [f'<svg width="{ancho}" height="470" style="margin-top:56px">']
    for i, (n, bien, mal, humano) in enumerate(modelos):
        y = i * 150 + 20
        s.append(f'<text x="0" y="{y+38}" fill="{t["tinta"]}" font-size="28" font-weight="{700 if i == 2 else 400}">{n}</text>')
        x = x0
        for v, c, etiqueta in [(bien, t["laya"], "labeled right"), (mal, t["coral"], "labeled wrong"), (humano, t["rejilla"], "left for a human")]:
            w = esc(v) - 2
            s.append(f'<rect x="{x}" y="{y}" width="{w}" height="56" rx="6" fill="{c}"/>')
            if v >= 4.5:
                color_txt = "#FFFFFF" if c in (t["laya"], t["coral"], t["neutro"]) else t["tinta"]
                s.append(f'<text x="{x+16}" y="{y+37}" fill="{color_txt}" font-size="24" font-weight="700" style="font-family:Mono">{v:.0f}</text>')
            x += esc(v)
    s.append("</svg>")
    leyenda = f'<div style="display:flex;gap:36px;margin-top:10px;font-size:21px;color:{t["suave"]}">' + "".join(
        f'<span><i style="display:inline-block;width:16px;height:16px;border-radius:4px;background:{c};margin-right:10px;vertical-align:-2px"></i>{e}</span>'
        for c, e in [(t["laya"], "labeled right, automatically"), (t["coral"], "labeled wrong"), (t["rejilla"], "left for a maintainer (needs-triage)")]) + "</div>"
    return marco(t, "Out of every 100 new issues", "What happens when each issue arrives. Same data, same threshold (confidence ≥ 0.60).", s and "".join(s) + leyenda, 900,
                 "NLBSE'23 test samples, 5,000 issues each. laya-triage: 94.1% labeled at 91.1% precision · Jev: 95.1% at 86.6% · Laya base: 57.1% at 89.1%.")

def g_tradeoff(t):
    curva = [(0.0, 88.7), (0.6, 88.9), (1.8, 89.5), (3.6, 90.3), (4.9, 90.8), (7.1, 91.6), (9.3, 92.4), (11.8, 93.3),
             (14.6, 93.9), (19.1, 94.7), (26.0, 95.7), (45.3, 98.2)]
    ancho = W - 176; alto = 560; x0, x1 = 300, ancho - 90; lo_x, hi_x, lo_y, hi_y = 0, 50, 84, 100
    ex = lambda v: x0 + (x1 - x0) * (v - lo_x) / (hi_x - lo_x); ey = lambda v: 510 - 480 * (v - lo_y) / (hi_y - lo_y)
    s = [f'<svg width="{ancho}" height="{alto+40}" style="margin-top:36px">']
    for v in range(lo_y, hi_y + 1, 2):
        s.append(f'<line x1="{x0}" y1="{ey(v)}" x2="{x1+24}" y2="{ey(v)}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="{x1+34}" y="{ey(v)+6}" fill="{t["tenue"]}" font-size="17" text-anchor="start" style="font-family:Mono">{v}%</text>')
    for v in range(lo_x, hi_x + 1, 10):
        s.append(f'<text x="{ex(v)}" y="{alto+4}" fill="{t["tenue"]}" font-size="17" text-anchor="middle" style="font-family:Mono">{v}%</text>')
    s.append(f'<text x="{(x0+x1)/2}" y="{alto+36}" fill="{t["suave"]}" font-size="19" text-anchor="middle">issues it leaves for a maintainer when unsure</text>')
    pts = " ".join(f"{ex(a)},{ey(b)}" for a, b in curva)
    s.append(f'<polygon points="{ex(0)},{ey(lo_y)} {pts} {ex(curva[-1][0])},{ey(lo_y)}" fill="{t["laya"]}" fill-opacity=".08"/>')
    s.append(f'<polyline points="{pts}" fill="none" stroke="{t["laya"]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    for a, b in curva:
        s.append(f'<circle cx="{ex(a)}" cy="{ey(b)}" r="5" fill="{t["laya"]}" stroke="{t["fondo"]}" stroke-width="2"/>')
    px, py = ex(4.9), ey(90.8)
    s.append(f'<circle cx="{px}" cy="{py}" r="10" fill="{t["laya"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
    s.append(f'<text x="{px+22}" y="{py+36}" fill="{t["tinta"]}" font-size="20" font-weight="700">default threshold</text>')
    s.append(f'<text x="{px+22}" y="{py+62}" fill="{t["suave"]}" font-size="18" style="font-family:Mono">skips 4.9% · 90.8% right</text>')
    s.append(f'<text x="{ex(45.3)-16}" y="{ey(98.2)-18}" fill="{t["suave"]}" font-size="18" text-anchor="end">strict mode: 98% right</text>')
    for nombre, x, y, dx in [("RoBERTa", 0, 89.1, 1), ("FastText", 0, 85.1, 1), ("Laya base", 42.9, 89.1, 1)]:
        s.append(f'<rect x="{ex(x)-8}" y="{ey(y)-8}" width="16" height="16" rx="3" fill="{t["neutro"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        if x == 0:
            s.append(f'<text x="{ex(x)-82}" y="{ey(y)+7}" fill="{t["tinta"]}" font-size="20" text-anchor="end">{nombre} <tspan fill="{t["suave"]}" style="font-family:Mono">{y:.1f}%</tspan></text>')
            s.append(f'<line x1="{ex(x)-74}" y1="{ey(y)}" x2="{ex(x)-12}" y2="{ey(y)}" stroke="{t["tenue"]}" stroke-width="1"/>')
        else:
            s.append(f'<text x="{ex(x)+20}" y="{ey(y)+7}" fill="{t["tinta"]}" font-size="20">{nombre} <tspan fill="{t["suave"]}" style="font-family:Mono">{y:.1f}%</tspan></text>')
    s.append("</svg>")
    leyenda = f'<div style="display:flex;gap:32px;margin-top:30px;font-size:21px;color:{t["suave"]}"><span><i style="display:inline-block;width:26px;height:4px;border-radius:2px;background:{t["laya"]};margin-right:10px;vertical-align:5px"></i><b style="color:{t["tinta"]}">laya-triage</b>, one point per confidence threshold</span><span><i style="display:inline-block;width:14px;height:14px;border-radius:3px;background:{t["neutro"]};margin-right:10px;vertical-align:-1px"></i>others, a single operating point</span></div>'
    return marco(t, "It knows when it is unsure", "Precision of the labels it applies. The more careful it is allowed to be, the more accurate it gets.", leyenda + "".join(s), 1060,
                 "laya-triage curve: NLBSE'23 validation (English model, calibrated). Points: test results; RoBERTa / FastText label every issue.")

GRAFICAS = {"exactitud": g_exactitud, "issues-2026": g_2026, "curva": g_curva, "idiomas": g_idiomas, "comparativa": g_comparativa, "cien-issues": g_cien, "confianza": g_tradeoff}
for nombre, f in GRAFICAS.items():
    for tema, t in TEMAS.items():
        Path(f"{nombre}-{tema}.html").write_text(f(t), encoding="utf-8")
print("ok")
