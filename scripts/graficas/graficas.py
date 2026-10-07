import json, sys
from pathlib import Path

TEMAS = {
    "light": dict(fondo="#FBFAFD", tinta="#16141F", suave="#5D596E", tenue="#8E8AA0", rejilla="#E9E6F0",
                  laya="#6B3FE7", coral="#F2644B", neutro="#8A8699", pill="#EFEAFD", laya2="#B9A6F4", rival2="#13968A"),
    "dark": dict(fondo="#16141F", tinta="#F4F2FA", suave="#B9B5C8", tenue="#8C889C", rejilla="#2A2736",
                 laya="#8B67F5", coral="#E85A42", neutro="#6E6A80", pill="#2A2240", laya2="#56449A", rival2="#2FB3A3"),
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
        dict(nombre="laya-triage v1.2", detalle="your runner · no API key", valor=88.8, destacar=True),
        dict(nombre="FastText", detalle="NLBSE'23 baseline", valor=85.1),
        dict(nombre="Jev", detalle="TypeSafe · hosted API · measured by us", valor=84.4),
        dict(nombre="OpenAI Decisions", detalle="gpt-6-luna · hosted API · measured by us", valor=83.7),
        dict(nombre="Laya base", detalle="same router, not fine-tuned", valor=75.9),
        dict(nombre="laya-issue-triage", detalle="other Laya fine-tune · measured by us", valor=64.5),
    ]
    cuerpo = barras_h(t, filas, 100, lambda v: f"{v:.1f}%" if v not in (0, 25, 50, 75, 100) else f"{v:.0f}%")
    cuerpo += f'''<div style="display:flex;gap:28px;margin-top:40px">
{"".join(f'<div style="flex:1;background:{t["pill"]};border-radius:18px;padding:26px 30px"><div style="font-family:Mono;font-size:17px;color:{t["suave"]}">{a}</div><div style="font-size:52px;font-weight:700;margin-top:8px;letter-spacing:-.02em">{b}</div><div style="font-size:19px;color:{t["suave"]};margin-top:4px">{c}</div></div>' for a,b,c in [
("issues labeled automatically","91.0%","vs 57.1% for Laya base"),
("precision on those labels","92.3%","it abstains when unsure"),
("time per run","< 40 s","on a free GitHub runner")])}
</div>'''
    return marco(t, "Issue type accuracy", "Bug · feature · question · docs on NLBSE'23 issues, 4 classes.", cuerpo, 1240,
                 "laya-triage: fresh random 5,000-issue sample of the NLBSE'23 test set, measured once (±0.9 pts, 95%). Jev, OpenAI Decisions, Laya base, laya-issue-triage: another 5,000-issue sample of the same test set. RoBERTa / FastText: published results on the full test set. laya-triage v1.2 runs the v1.1 models.")

def g_2026(t):
    clases = [("Macro F1", .523, .660, .602, .758), ("Bug", .615, .773, .785, .792), ("Feature", .593, .699, .634, .806), ("Question", .221, .387, .349, .626), ("Docs", .665, .781, .641, .807)]
    ancho = W - 176; alto = 470; x0 = 60; paso = (ancho - x0) / len(clases); bw = 54; esc = lambda v: 400 - 380 * v
    series = [(t["neutro"], 400), (t["coral"], 400), (t["rival2"], 400), (t["laya"], 700)]
    s = [f'<svg width="{ancho}" height="{alto+40}" style="margin-top:34px">']
    for v in [0, .25, .5, .75, 1]:
        s.append(f'<line x1="{x0}" y1="{esc(v)}" x2="{ancho}" y2="{esc(v)}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="{x0-14}" y="{esc(v)+6}" fill="{t["tenue"]}" font-size="17" text-anchor="end" style="font-family:Mono">{v:.2f}</text>')
    for i, (n, *valores) in enumerate(clases):
        cx = x0 + paso * i + paso / 2
        for j, (v, (c, peso)) in enumerate(zip(valores, series)):
            x = cx + (j - 1.5) * (bw + 6) - bw / 2; y = esc(v)
            s.append(f'<path d="M{x},{esc(0)} V{y+6} Q{x},{y} {x+6},{y} H{x+bw-6} Q{x+bw},{y} {x+bw},{y+6} V{esc(0)} Z" fill="{c}"/>')
            s.append(f'<text x="{x+bw/2}" y="{y-12}" fill="{t["tinta"]}" font-size="17" font-weight="{peso}" text-anchor="middle" style="font-family:Mono">{v:.2f}</text>')
        s.append(f'<text x="{cx}" y="{esc(0)+40}" fill="{t["tinta"]}" font-size="24" font-weight="{700 if i==0 else 400}" text-anchor="middle">{n}</text>')
    s.append("</svg>")
    leyenda = f'<div style="display:flex;gap:32px;margin-top:30px;font-size:21px;color:{t["suave"]}">' + "".join(
        f'<span><i style="display:inline-block;width:16px;height:16px;border-radius:4px;background:{c};margin-right:10px;vertical-align:-2px"></i>{e}</span>'
        for c, e in [(t["neutro"], "Laya base"), (t["coral"], "Jev (TypeSafe)"), (t["rival2"], "OpenAI Decisions"), (t["laya"], f'<b style="color:{t["tinta"]}">laya-triage v1.2</b>, adapted to the repo')]) + "</div>"
    return marco(t, "Issues it has never seen", "2,000 issues opened in 2026 across 1,145 repositories. F1 per class, higher is better.", leyenda + "".join(s), 900,
                 "Closed issues with a single type label, created since 2026-01-01, max 15 per repo, 500 per class. Same question and text for every model; Jev and OpenAI without priors. laya-triage: class priors set to this set's mix, 25% each, as class-priors would do on a repository like this. laya-triage v1.2 runs the v1.1 models.")

def g_curva(t):
    puntos = [("40k", "balanced + priors", 85.6), ("150k", "balanced + priors", 86.8), ("500k", "natural mix", 88.5),
              ("1M", "v1.0 model", 88.7), ("1.13M", "v1.1 model · 1M + 127k recent", 88.8)]
    ancho = W - 176; alto = 560; x0, x1 = 110, ancho - 150; lo, hi = 82, 90
    ex = lambda i: x0 + (x1 - x0) * i / (len(puntos) - 1); ey = lambda v: 500 - 470 * (v - lo) / (hi - lo)
    s = [f'<svg width="{ancho}" height="{alto+40}" style="margin-top:36px">']
    for v in range(lo, hi + 1, 1):
        s.append(f'<line x1="{x0-30}" y1="{ey(v)}" x2="{x1+60}" y2="{ey(v)}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="{x0-44}" y="{ey(v)+6}" fill="{t["tenue"]}" font-size="17" text-anchor="end" style="font-family:Mono">{v}%</text>')
    for v, texto, color, dy in [(84.4, "Jev · 84.4%", t["coral"], -12), (83.7, "OpenAI Decisions · 83.7%", t["rival2"], 28)]:
        s.append(f'<line x1="{x0-30}" y1="{ey(v)}" x2="{x1+60}" y2="{ey(v)}" stroke="{color}" stroke-width="2" stroke-dasharray="8 8"/>')
        s.append(f'<text x="{x1+60}" y="{ey(v)+dy}" fill="{color}" font-size="19" font-weight="700" text-anchor="end">{texto}</text>')
    pts = " ".join(f"{ex(i)},{ey(p[2])}" for i, p in enumerate(puntos))
    s.append(f'<polyline points="{pts}" fill="none" stroke="{t["laya"]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    for i, (n, d, v) in enumerate(puntos):
        final = i == len(puntos) - 1
        s.append(f'<circle cx="{ex(i)}" cy="{ey(v)}" r="{10 if final else 8}" fill="{t["laya"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<text x="{ex(i)}" y="{ey(v)-22}" fill="{t["tinta"]}" font-size="22" font-weight="{700 if final else 400}" text-anchor="middle" style="font-family:Mono">{v:.1f}%</text>')
        s.append(f'<text x="{ex(i)}" y="{alto+2}" fill="{t["tinta"]}" font-size="24" font-weight="{700 if final else 400}" text-anchor="middle" style="font-family:Mono">{n}</text>')
        s.append(f'<text x="{ex(i)}" y="{alto+30}" fill="{t["tenue"]}" font-size="17" text-anchor="middle">{d}</text>')
    s.append("</svg>")
    leyenda = f'<div style="display:flex;gap:32px;margin-top:30px;font-size:21px;color:{t["suave"]}">' + "".join(
        f'<span><i style="display:inline-block;width:26px;height:4px;border-radius:2px;background:{c};margin-right:10px;vertical-align:5px"></i>{e}</span>'
        for c, e in [(t["laya"], f'<b style="color:{t["tinta"]}">laya-triage</b>, one English model per training size'), (t["coral"], "Jev, hosted API"), (t["rival2"], "OpenAI Decisions, hosted API")]) + "</div>"
    return marco(t, "More data, better triage", "NLBSE'23 accuracy of every laya-triage English model, by the number of issues it was trained on.", leyenda + "".join(s), 1080,
                 "laya-triage: 2,500 NLBSE'23 validation issues held out from calibration, with the class priors each model needs. Jev and OpenAI Decisions: the same 5,000-issue test sample. laya-triage v1.2 runs the 1.13M model. One epoch each on a single RTX 5070; the 1.13M model took 15.5 hours. Recent issues are compared in a separate chart.")

def g_curva_reciente(t):
    puntos = [("1M", "v1.0 model · NLBSE'23 only", 79.8), ("1.13M", "v1.1 model · 1M + 127k recent", 82.3)]
    ancho = W - 176; alto = 560; x0, x1 = 360, ancho - 360; lo, hi = 76, 84
    ex = lambda i: x0 + (x1 - x0) * i / (len(puntos) - 1); ey = lambda v: 500 - 470 * (v - lo) / (hi - lo)
    s = [f'<svg width="{ancho}" height="{alto+40}" style="margin-top:36px">']
    for v in range(lo, hi + 1, 1):
        s.append(f'<line x1="110" y1="{ey(v)}" x2="{ancho-60}" y2="{ey(v)}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="96" y="{ey(v)+6}" fill="{t["tenue"]}" font-size="17" text-anchor="end" style="font-family:Mono">{v}%</text>')
    for k, c in enumerate([t["coral"], t["rival2"]]):
        s.append(f'<line x1="110" y1="{ey(78.1)}" x2="{ancho-60}" y2="{ey(78.1)}" stroke="{c}" stroke-width="2" stroke-dasharray="8 24" stroke-dashoffset="{-16 * k}"/>')
    s.append(f'<text x="{ancho-60}" y="{ey(78.1)+28}" fill="{t["suave"]}" font-size="19" font-weight="700" text-anchor="end">Jev and OpenAI Decisions · 78.1%</text>')
    pts = " ".join(f"{ex(i)},{ey(p[2])}" for i, p in enumerate(puntos))
    s.append(f'<polyline points="{pts}" fill="none" stroke="{t["laya"]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    xd, yd = ex(1), ey(81.9)
    s.append(f'<line x1="{ex(0)}" y1="{ey(79.8)}" x2="{xd}" y2="{yd}" stroke="{t["tenue"]}" stroke-width="2" stroke-dasharray="4 6"/>')
    s.append(f'<circle cx="{xd}" cy="{yd}" r="8" fill="{t["fondo"]}" stroke="{t["tenue"]}" stroke-width="3"/>')
    s.append(f'<text x="{xd+22}" y="{yd-4}" fill="{t["suave"]}" font-size="19">v1.0 fine-tuned on recent issues<tspan x="{xd+22}" dy="26">discarded · <tspan style="font-family:Mono">81.9%</tspan></tspan></text>')
    for i, (n, d, v) in enumerate(puntos):
        final = i == len(puntos) - 1
        s.append(f'<circle cx="{ex(i)}" cy="{ey(v)}" r="{10 if final else 8}" fill="{t["laya"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<text x="{ex(i)}" y="{ey(v)-22}" fill="{t["tinta"]}" font-size="22" font-weight="{700 if final else 400}" text-anchor="middle" style="font-family:Mono">{v:.1f}%</text>')
        s.append(f'<text x="{ex(i)}" y="{alto+2}" fill="{t["tinta"]}" font-size="24" font-weight="{700 if final else 400}" text-anchor="middle" style="font-family:Mono">{n}</text>')
        s.append(f'<text x="{ex(i)}" y="{alto+30}" fill="{t["tenue"]}" font-size="17" text-anchor="middle">{d}</text>')
    s.append("</svg>")
    leyenda = f'<div style="display:flex;gap:32px;margin-top:30px;font-size:21px;color:{t["suave"]}">' + "".join(
        f'<span><i style="display:inline-block;width:26px;height:4px;border-radius:2px;background:{c};margin-right:10px;vertical-align:5px"></i>{e}</span>'
        for c, e in [(t["laya"], f'<b style="color:{t["tinta"]}">laya-triage</b>, released English models'), (t["coral"], "Jev, hosted API"), (t["rival2"], "OpenAI Decisions, hosted API")]) + "</div>"
    return marco(t, "Recent issues need recent data", "Accuracy on 10,026 issues from 2025-2026 in 288 active repositories, by training data.", leyenda + "".join(s), 1080,
                 "Issues from repositories never used for training, labeled by a maintainer. laya-triage adapted to each repository as class-priors: auto does; Jev and OpenAI Decisions without priors. Smaller models were not measured on this set. Fine-tuning v1.0 on recent issues lost almost a point on NLBSE'23, so v1.1 was trained from scratch on both. laya-triage v1.2 runs the v1.1 models.")

def g_idiomas(t):
    datos = [("English", 89.2, 88.2, 84.2, 92.4), ("Vietnamese", 71.2, 84.4, 83.2, 87.6), ("German", 74.6, 85.8, 83.0, 86.4), ("Turkish", 68.2, 85.0, 83.4, 86.4),
             ("Portuguese", 74.0, 86.6, 83.2, 86.4), ("Indonesian", 73.8, 86.0, 83.4, 86.2), ("Spanish", 73.8, 85.6, 81.4, 86.2), ("Russian", 70.8, 85.8, 81.4, 85.6),
             ("French", 71.6, 85.2, 83.4, 85.4), ("Hindi", 66.2, 85.4, 84.6, 85.2), ("Arabic", 67.4, 84.8, 81.8, 85.0), ("Chinese", 68.2, 83.8, 80.2, 84.8),
             ("Japanese", 67.8, 84.4, 83.6, 84.8), ("Korean", 64.2, 83.8, 82.4, 84.8)]
    ancho = W - 176; fila = 50; x0, x1 = 230, ancho - 120; lo, hi = 60, 95
    ex = lambda v: x0 + (x1 - x0) * (v - lo) / (hi - lo)
    alto = len(datos) * fila + 50
    s = [f'<svg width="{ancho}" height="{alto}" style="margin-top:36px">']
    for v in range(lo, hi + 1, 5):
        s.append(f'<line x1="{ex(v)}" y1="0" x2="{ex(v)}" y2="{alto-40}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        s.append(f'<text x="{ex(v)}" y="{alto-12}" fill="{t["tenue"]}" font-size="17" text-anchor="middle" style="font-family:Mono">{v}%</text>')
    for i, (n, a, j, o, b) in enumerate(datos):
        y = i * fila + 22
        s.append(f'<text x="0" y="{y+8}" fill="{t["tinta"]}" font-size="23" font-weight="{700 if i==0 else 400}">{n}</text>')
        s.append(f'<line x1="{ex(min(a, j, o, b))}" y1="{y}" x2="{ex(max(a, j, o, b))}" y2="{y}" stroke="{t["rejilla"]}" stroke-width="3" stroke-linecap="round"/>')
        s.append(f'<circle cx="{ex(a)}" cy="{y}" r="8" fill="{t["neutro"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<rect x="{ex(o)-8}" y="{y-8}" width="16" height="16" rx="2" fill="{t["rival2"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<rect x="{ex(j)-8}" y="{y-8}" width="16" height="16" rx="3" transform="rotate(45 {ex(j)} {y})" fill="{t["coral"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<circle cx="{ex(b)}" cy="{y}" r="9" fill="{t["laya"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        s.append(f'<text x="{ex(max(a, j, o, b))+24}" y="{y+7}" fill="{t["tinta"]}" font-size="20" font-weight="700" style="font-family:Mono">{b:.1f}%</text>')
        if a <= min(j, o, b):
            s.append(f'<text x="{ex(a)-20}" y="{y+7}" fill="{t["suave"]}" font-size="18" text-anchor="end" style="font-family:Mono">{a:.1f}</text>')
    s.append("</svg>")
    marca = lambda forma, c: (f'<i style="display:inline-block;width:14px;height:14px;background:{c};margin-right:10px;vertical-align:-1px;'
                             + {"rombo": "transform:rotate(45deg);border-radius:3px", "cuadro": "border-radius:2px"}.get(forma, "border-radius:50%") + '"></i>')
    leyenda = f'<div style="display:flex;gap:32px;margin-top:30px;font-size:21px;color:{t["suave"]}">' + "".join(
        f'<span>{marca(f, c)}{e}</span>' for f, c, e in [("c", t["neutro"], "Laya base"), ("rombo", t["coral"], "Jev (TypeSafe, hosted)"), ("cuadro", t["rival2"], "OpenAI Decisions (hosted)"),
                                                       ("c", t["laya"], f'<b style="color:{t["tinta"]}">laya-triage v1.2</b> (value shown)')]) + "</div>"
    return marco(t, "Every language, not just English", "The same 500 issues in 14 languages. Accuracy, higher is better.", leyenda + "".join(s), 1180,
                 "Machine-translated with NLLB-200; training used different issues. ±3 pts per language (500 issues). laya-triage v1.2 (v1.1 models) is ahead of Jev in 11 of 14 languages and of OpenAI Decisions in all 14; most gaps with Jev are within noise.")

def g_comparativa(t):
    ok = lambda x: f'<span style="color:{t["tinta"]};font-weight:700">{x}</span>'
    no = lambda x: f'<span style="color:{t["tenue"]}">{x}</span>'
    filas = [
        ("laya-triage", "Laya fine-tuned · Action", ok("88.8%"), ok("82.3%"), ok("$0"), ok("stays in your runner"), ok("none"), ok("14 measured"), ok("calibrated, abstains")),
        ("Jev", "TypeSafe · hosted decision API", "84.4%", "78.1%", "~$0.03 per 1k issues", "TypeSafe's servers", "key", "14 measured by us", "probabilities"),
        ("OpenAI Decisions", "gpt-6-luna · hosted API", "83.7%", "78.1%", "~$0.05 per 1k issues", "OpenAI's servers", "paid key", "14 measured by us", "probabilities"),
        ("laya-issue-triage", "other Laya fine-tune · Action", "64.5%", no("—"), "$0", "stays in your runner", "none", "English", "min-confidence"),
        ("NLBSE'23 research", "RoBERTa · FastText", "85.1–89.1%", no("—"), no("not a GitHub tool"), "local", "none", "English", no("—")),
        ("ai-assessment-comment-labeler", "GitHub · GitHub Models", no("not published"), no("—"), "$0 up to 150 req/day*", "GitHub Models", "none", no("—"), no("—")),
        ("ai-labeler", "jlowin · OpenAI / Anthropic", no("not published"), no("—"), "~$5 per 10k PRs†", "OpenAI or Anthropic", "paid key", no("—"), no("—")),
        ("Dosu", "hosted service", no("not published"), no("—"), "free tier · Pro $16/mo", "Dosu's servers", "none (app)", no("—"), no("—")),
        ("issue-labeler", "GitHub · regex rules", no("n/a, rules"), no("—"), "$0", "stays in your runner", "none", "rule-based", no("—")),
    ]
    cab = ["Accuracy<br>NLBSE'23 test", "Accuracy<br>recent repos", "Cost<br>public repo", "Where issue<br>text goes", "Extra<br>API key", "Languages", "Confidence"]
    th = "".join(f'<th style="text-align:left;font-family:Mono;font-weight:400;font-size:16px;color:{t["suave"]};padding:0 14px 18px;line-height:1.35">{c}</th>' for c in cab)
    trs = []
    for i, f in enumerate(filas):
        fondo = t["pill"] if i == 0 else "transparent"
        borde = "none" if i == 0 else f"1px solid {t['rejilla']}"
        celdas = "".join(f'<td style="padding:22px 12px;font-size:19px;vertical-align:middle">{c}</td>' for c in f[2:])
        marca = f'<i style="display:inline-block;width:12px;height:12px;border-radius:3px;background:{t["laya"]};margin-right:10px"></i>' if i == 0 else ""
        trs.append(f'<tr style="background:{fondo};border-top:{borde}"><td style="padding:22px 14px 22px 24px;border-radius:16px 0 0 16px"><div style="font-size:23px;font-weight:{700 if i==0 else 400}">{marca}{f[0]}</div><div style="font-family:Mono;font-size:15px;color:{t["tenue"]};margin-top:6px">{f[1]}</div></td>{celdas}</tr>')
    tabla = f'<table style="width:100%;border-collapse:collapse;margin-top:44px;color:{t["tinta"]}"><tr><th></th>{th}</tr>{"".join(trs)}</table>'
    return marco(t, "Why laya-triage", "Issue triage for GitHub, compared on what maintainers actually care about.", tabla, 1420,
                 "Accuracy for laya-triage v1.2 (v1.1 models), Jev, OpenAI Decisions and laya-issue-triage measured by us on random 5,000-issue samples of the NLBSE'23 test set; recent repos: 10,026 issues from 288 active repositories, laya-triage adapted to each. Figures as of Oct 2026, from each project's docs. * GitHub Models free tier, low-tier models. † the project's own gpt-4o-mini estimate. — not published.")

def g_cien(t):
    grupos = [
        ("NLBSE'23 test", [("Laya base", 50.9, 6.2, 42.9), ("Jev", 82.4, 12.7, 4.9), ("OpenAI Decisions", 82.54, 15.26, 2.2), ("laya-triage v1.2", 84.0, 7.0, 9.0)]),
        ("Recent issues from active repositories", [("Jev", 76.6, 20.0, 3.4), ("OpenAI Decisions", 77.34, 21.06, 1.6), ("laya-triage v1.2", 76.6, 12.2, 11.2)]),
    ]
    ancho = W - 176; x0 = 330; x1 = ancho - 20; esc = lambda v: (x1 - x0) * v / 100
    filas = sum(len(g[1]) for g in grupos)
    alto = filas * 104 + len(grupos) * 70 + 10
    s = [f'<svg width="{ancho}" height="{alto}" style="margin-top:40px">']
    y = 0
    for titulo, modelos in grupos:
        s.append(f'<text x="0" y="{y+26}" fill="{t["suave"]}" font-size="20" style="font-family:Mono">{titulo}</text>')
        s.append(f'<line x1="0" y1="{y+44}" x2="{ancho}" y2="{y+44}" stroke="{t["rejilla"]}" stroke-width="1"/>')
        y += 70
        for n, bien, mal, humano in modelos:
            nuestro = n.startswith("laya-triage")
            s.append(f'<text x="0" y="{y+36}" fill="{t["tinta"]}" font-size="27" font-weight="{700 if nuestro else 400}">{n}</text>')
            x = x0
            for v, c in [(bien, t["laya"]), (mal, t["coral"]), (humano, t["rejilla"])]:
                w = esc(v) - 2
                s.append(f'<rect x="{x}" y="{y}" width="{w}" height="54" rx="6" fill="{c}"/>')
                if v >= 4.5:
                    color_txt = "#FFFFFF" if c in (t["laya"], t["coral"]) else t["tinta"]
                    s.append(f'<text x="{x+16}" y="{y+36}" fill="{color_txt}" font-size="24" font-weight="700" style="font-family:Mono">{v:.0f}</text>')
                x += esc(v)
            y += 104
    s.append("</svg>")
    leyenda = f'<div style="display:flex;gap:36px;margin-top:6px;font-size:21px;color:{t["suave"]}">' + "".join(
        f'<span><i style="display:inline-block;width:16px;height:16px;border-radius:4px;background:{c};margin-right:10px;vertical-align:-2px"></i>{e}</span>'
        for c, e in [(t["laya"], "labeled right, automatically"), (t["coral"], "labeled wrong"), (t["rejilla"], "left for a maintainer (needs-triage)")]) + "</div>"
    return marco(t, "Out of every 100 new issues", "What happens when each issue arrives. Same data, same threshold (confidence ≥ 0.60).", "".join(s) + leyenda, 1360,
                 "laya-triage v1.2 runs the v1.1 models. NLBSE'23: 5,000-issue test samples; laya-triage labels 91.0% at 92.3% precision, Jev 95.1% at 86.6%, OpenAI Decisions 97.8% at 84.4%, Laya base 57.1% at 89.1%. Recent: 10,026 issues from 288 repositories never used for training; laya-triage adapted to each repository labels 88.8% at 86.3%, Jev 96.6% at 79.3%, OpenAI Decisions 98.4% at 78.6%.")

def g_tradeoff(t):
    curva = [(0.6, 89.1), (1.5, 89.4), (3.7, 90.4), (6.4, 91.4), (8.8, 92.1), (12.1, 93.1), (16.2, 94.3), (21.0, 95.2),
             (28.4, 96.5), (40.2, 97.9)]
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
    px, py = ex(8.8), ey(92.1)
    s.append(f'<circle cx="{px}" cy="{py}" r="10" fill="{t["laya"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
    s.append(f'<text x="{px+22}" y="{py+36}" fill="{t["tinta"]}" font-size="20" font-weight="700">default threshold</text>')
    s.append(f'<text x="{px+22}" y="{py+62}" fill="{t["suave"]}" font-size="18" style="font-family:Mono">skips 8.8% · 92.1% right</text>')
    s.append(f'<text x="{ex(40.2)-16}" y="{ey(97.9)-18}" fill="{t["suave"]}" font-size="18" text-anchor="end">threshold 0.85: 97.9% right</text>')
    for nombre, x, y, dx in [("RoBERTa", 0, 89.1, 1), ("FastText", 0, 85.1, 1), ("Laya base", 42.9, 89.1, 1)]:
        s.append(f'<rect x="{ex(x)-8}" y="{ey(y)-8}" width="16" height="16" rx="3" fill="{t["neutro"]}" stroke="{t["fondo"]}" stroke-width="3"/>')
        if x == 0:
            s.append(f'<text x="{ex(x)-82}" y="{ey(y)+7}" fill="{t["tinta"]}" font-size="20" text-anchor="end">{nombre} <tspan fill="{t["suave"]}" style="font-family:Mono">{y:.1f}%</tspan></text>')
            s.append(f'<line x1="{ex(x)-74}" y1="{ey(y)}" x2="{ex(x)-12}" y2="{ey(y)}" stroke="{t["tenue"]}" stroke-width="1"/>')
        else:
            s.append(f'<text x="{ex(x)+20}" y="{ey(y)+7}" fill="{t["tinta"]}" font-size="20">{nombre} <tspan fill="{t["suave"]}" style="font-family:Mono">{y:.1f}%</tspan></text>')
    s.append("</svg>")
    leyenda = f'<div style="display:flex;gap:32px;margin-top:30px;font-size:21px;color:{t["suave"]}"><span><i style="display:inline-block;width:26px;height:4px;border-radius:2px;background:{t["laya"]};margin-right:10px;vertical-align:5px"></i><b style="color:{t["tinta"]}">laya-triage v1.2</b>, one point per confidence threshold</span><span><i style="display:inline-block;width:14px;height:14px;border-radius:3px;background:{t["neutro"]};margin-right:10px;vertical-align:-1px"></i>others, a single operating point</span></div>'
    return marco(t, "It knows when it is unsure", "Precision of the labels it applies. The more careful it is allowed to be, the more accurate it gets.", leyenda + "".join(s), 1060,
                 "laya-triage v1.2 curve (v1.1 models): 2,500 NLBSE'23 validation issues, English model with the confidence the action uses. Points: test results; RoBERTa / FastText label every issue.")

def g_repos(t):
    filas = [
        dict(nombre="laya-triage v1.2", detalle="v1.1 models · class-priors: auto · $0", valor=82.3, destacar=True),
        dict(nombre="laya-triage v1.0", detalle="v1.0 models · class-priors: auto", valor=79.8),
        dict(nombre="Jev", detalle="TypeSafe · hosted API · $0.30", valor=78.1),
        dict(nombre="OpenAI Decisions", detalle="gpt-6-luna · hosted API · $0.46", valor=78.1),
        dict(nombre="Always bug", detalle="the most common label", valor=57.6),
    ]
    cuerpo = barras_h(t, filas, 100, lambda v: f"{v:.1f}%" if v not in (0, 25, 50, 75, 100) else f"{v:.0f}%")
    fichas = [
        ("macro F1", "0.742", "vs 0.660 Jev · 0.658 OpenAI"),
        ("questions recognized", "58.3%", "vs 29.6% Jev · 33.5% OpenAI"),
        ("wrong labels per 100", "12.2", "vs 20.0 Jev · 21.1 OpenAI"),
    ]
    html = "".join(
        f'<div style="flex:1;background:{t["pill"]};border-radius:18px;padding:26px 30px"><div style="font-family:Mono;font-size:17px;color:{t["suave"]}">{a}</div><div style="font-size:52px;font-weight:700;margin-top:8px;letter-spacing:-.02em">{b}</div><div style="font-size:19px;color:{t["suave"]};margin-top:4px">{c}</div></div>'
        for a, b, c in fichas
    )
    cuerpo += f'<div style="display:flex;gap:28px;margin-top:40px">{html}</div>'
    return marco(t, "Today's issues, today's repositories", "10,026 issues from 2025-2026 in 288 active repositories with 1,000+ stars. Accuracy.", cuerpo, 1100,
                 "Labels set by a maintainer, not by an issue template. No repository in this set was used for training. laya-triage adapts to each repository's mix, estimated from its other labeled issues as class-priors: auto does. Wrong labels counted at confidence 0.60.")

def g_versiones(t):
    filas = [
        ("NLBSE'23 test", "accuracy", 88.8, 88.8, "{:.1f}%", 1),
        ("Recent issues", "accuracy, adapted to each repo", 79.8, 82.3, "{:.1f}%", 1),
        ("Recent issues", "macro F1", 0.690, 0.742, "{:.3f}", 1),
        ("Questions recognized", "recent issues", 43.7, 58.3, "{:.1f}%", 1),
        ("Wrong labels per 100", "recent issues, lower is better", 16.9, 12.2, "{:.1f}", -1),
        ("Issues from 2026", "macro F1, adapted", 0.734, 0.758, "{:.3f}", 1),
        ("Real non-English issues", "recent issues, multilingual route", 74.0, 77.6, "{:.1f}%", 1),
        ("14 languages", "average accuracy, translated", 85.7, 86.2, "{:.1f}%", 1),
        ("Labeled automatically", "recent issues · the rest goes to needs-triage", 93.7, 88.8, "{:.1f}%", 0),
    ]
    ancho = W - 176; fila = 84
    cab = f'''<div style="display:grid;grid-template-columns:1fr 200px 200px 220px;margin-top:44px;font-family:Mono;font-size:17px;color:{t["suave"]};padding:0 24px 14px">
<span></span><span style="text-align:right">v1.0</span><span style="text-align:right">v1.1</span><span style="text-align:right">change</span></div>'''
    cuerpo = [cab]
    for i, (nombre, detalle, a, b, fmt, signo) in enumerate(filas):
        d = b - a
        if signo == 0:
            color, txt = t["tenue"], "trade-off"
        elif d == 0:
            color, txt = t["tenue"], "same"
        else:
            mejor = d * signo > 0
            color = t["laya"] if mejor else t["coral"]
            txt = ("+" if d > 0 else "−") + (fmt.replace("%", "").format(abs(d)) + (" pts" if "%" in fmt else ""))
        pastilla = (f'<span style="display:inline-block;background:{color};color:#FFFFFF;border-radius:999px;padding:6px 16px;font-family:Mono;font-size:19px;font-weight:700">{txt}</span>'
                    if color == t["laya"] else f'<span style="font-family:Mono;font-size:18px;color:{color}">{txt}</span>')
        fondo = t["pill"] if i % 2 == 0 else "transparent"
        cuerpo.append(f'''<div style="display:grid;grid-template-columns:1fr 200px 200px 220px;align-items:center;height:{fila}px;padding:0 24px;background:{fondo};border-radius:14px">
<div><div style="font-size:25px">{nombre}</div><div style="font-family:Mono;font-size:16px;color:{t["tenue"]};margin-top:4px">{detalle}</div></div>
<div style="text-align:right;font-family:Mono;font-size:24px;color:{t["suave"]}">{fmt.format(a)}</div>
<div style="text-align:right;font-family:Mono;font-size:26px;font-weight:700">{fmt.format(b)}</div>
<div style="text-align:right">{pastilla}</div></div>''')
    return marco(t, "What changed from v1.0 to v1.1", "Same tests, same threshold. v1.1 added 127,140 recent issues to the training data.", "".join(cuerpo), 1220,
                 "NLBSE'23: fresh 5,000-issue test sample. Recent: 10,026 issues from 288 repositories never used for training. 2026: 2,000 issues, 500 per class. Languages: 500 NLBSE'23 validation issues translated with NLLB-200. v1.1 is more careful: it leaves more issues to a maintainer and gets fewer wrong.")

GRAFICAS = {"repos-actuales": g_repos, "exactitud": g_exactitud, "issues-2026": g_2026, "curva": g_curva, "curva-recientes": g_curva_reciente, "idiomas": g_idiomas, "comparativa": g_comparativa, "cien-issues": g_cien, "confianza": g_tradeoff, "versiones": g_versiones}
for nombre, f in GRAFICAS.items():
    for tema, t in TEMAS.items():
        Path(f"{nombre}-{tema}.html").write_text(f(t), encoding="utf-8")
print("ok")