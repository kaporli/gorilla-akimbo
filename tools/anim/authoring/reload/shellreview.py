"""Review graphics of the shell-family drafts (TUBE tube1.py, BREAK-OPEN break1.py): frames with the rigid shells and
the simulated gun parts, dense sheets, strips, per-take videos, contact sheet, grid video, scored review page.
Blender runs one process at a time.

usage: shellreview.py <family module> frames [ids] | dense <id><take> | sheet | grid | page
The family module provides PICKS, DOC, TAKES (take letters), TAKE_NAME, stem(pick, take), key(spec, gate),
phase(spec, gate, f), objects(spec) (scene objects), numbers(spec, gate), INTRO (html), TITLE, SHEET_TITLE, FILE.
"""
import os, sys, json, subprocess, html, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import rrender3
from rrender import font, ffmpeg, SCENE, CAM
from PIL import Image, ImageDraw

FAM = importlib.import_module(sys.argv[1]) if __name__ == '__main__' else None
REV = renv.OUT + '/review'; CL = renv.OUT + '/clips/pma'; YEL = (255, 220, 0)


def spec_path(pt): return f'{CL}/{FAM.stem(pt[:-1], pt[-1])}.json'
def load(pt): p = spec_path(pt); return json.load(open(p)), json.load(open(p[:-5] + '_gate.json'))
def fdir(pt): return rrender3.fdir(spec_path(pt))


def render(pt, res=(640, 360)):
    p = spec_path(pt); spec = json.load(open(p)); d = fdir(pt); N = spec['frames']; gid = spec['_gun']; G0 = common.gun(gid); parts = G0.get('parts') or [G0['mesh'] + '__base1_01']
    for v in ('fpp', 'out'):
        if os.path.exists(f'{d}/{v}_{N - 1:03d}.png') and os.path.getmtime(f'{d}/{v}_{N - 1:03d}.png') > os.path.getmtime(spec['out']): continue
        cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': list(range(N)), 'out': f'{d}/{v}', 'body': spec['_body'], 'view': v, 'res': list(res),
               'right_gun': gid, 'left_gun': gid, 'right_parts': parts, 'left_parts': parts, 'right_mag_clip': spec['_gun_clip'], 'left_mag_clip': None,
               'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40], 'right_parts_anim': True, 'right_mag_track': spec['_track'],
               'right_parts_frames': spec['_part_frames'], 'objects': FAM.objects(spec)}
        cfg.update(CAM if v == 'fpp' else rrender3.OUTCAM['Right'])
        c = f'{d}/cfg_{v}.json'; json.dump(cfg, open(c, 'w'))
        r = subprocess.run([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', c], capture_output=True, text=True, errors='replace')
        if 'DONE' not in r.stdout: raise SystemExit(f'scene.py failed for {c}:\n' + '\n'.join((r.stdout + r.stderr).splitlines()[-15:]))
    return d


def key(pt): s, g = load(pt); return FAM.key(s, g)


def cell(pt, v, f, size, title, big=False, crop=None):
    s, g = load(pt); d = fdir(pt); ff = min(max(f, 0), s['frames'] - 1)
    im = Image.open(f'{d}/{v}_{ff:03d}.png').convert('RGB')
    if crop: im = im.crop((0, int(im.size[1] * crop[0]), im.size[0], int(im.size[1] * crop[1])))
    im = im.resize(size); dr = ImageDraw.Draw(im); W = size[0]; h = 30 if big else 22
    dr.rectangle((0, 0, W, h), fill=(0, 0, 0)); dr.text((6, 3), title, fill=YEL, font=font(19 if big else 14))
    sub = f'f{ff}/{s["frames"] - 1}  {FAM.phase(s, g, ff)}' + ('' if f == ff else '  (idle after the clip)'); fs = font(16 if big else 13, False)
    w = dr.textlength(sub, font=fs); dr.text((W - w - 6, 5 if big else 4), sub, fill=(255, 255, 255), font=fs)
    return im


def dense(pt, every=2):
    import motionstats
    s, g = load(pt); N = s['frames']; st = motionstats.stats(s['out'], s['clip'], 'Right', 0.55); fr = set()
    for m in st['moves']:
        for f in range(max(m['start'] - 3, 0), min(m['end'] + 4, N)): fr.add(f)
    ks = [x[1] for x in key(pt)]; fr |= set(ks) | {N - 1}
    fr = sorted(f for f in fr if f % every == 0 or f in ks or f == N - 1) + [N + 5]
    w, h = 480, 270; hf = 150; cols = 6; per = cols * 4; base = f'{REV}/dense/{pt}'; os.makedirs(os.path.dirname(base), exist_ok=True); outs = []
    for pg in range((len(fr) + per - 1) // per):
        part = fr[pg * per:(pg + 1) * per]; rows = (len(part) + cols - 1) // cols
        S = Image.new('RGB', (w * cols, 34 + rows * (h + hf)), (20, 20, 24)); dr = ImageDraw.Draw(S)
        dr.text((8, 6), f"{pt} {s['_name']}: every {every}nd frame while the gun moves, key frames, and the idle after the clip; first person (lower part) over outside (page {pg + 1})", fill=(255, 255, 255), font=font(18))
        for k, f in enumerate(part):
            x, y = (k % cols) * w, 34 + (k // cols) * (h + hf)
            S.paste(cell(pt, 'fpp', f, (w, hf), f'f{f}', crop=(0.44, 1.0)), (x, y)); S.paste(cell(pt, 'out', f, (w, h), f'f{f} outside'), (x, y + hf))
        S.save(f'{base}_p{pg + 1}.png'); outs.append(f'{base}_p{pg + 1}.png')
    print('wrote', outs)


def sheet(ids, out=None):
    out = out or f'{REV}/{FAM.FILE}_contact_sheet.png'; w, h = 384, 216; crop = (0.30, 1.0); nw = 380; top = 64; T = FAM.TAKES; rowh = len(T) * h + 10
    S = Image.new('RGB', (5 * w + nw, top + rowh * len(ids)), (20, 20, 24)); dr = ImageDraw.Draw(S)
    dr.text((10, 6), FAM.SHEET_TITLE, fill=(255, 255, 255), font=font(19))
    dr.text((10, 34), 'First person at the key moments; outside at the second. Gun: spring-damper mass on the hand; shells: rigid bodies driven by the gun (see the page).', fill=(180, 185, 195), font=font(16, False))
    for r, p in enumerate(ids):
        y0 = top + r * rowh
        for t, take in enumerate(T):
            pt = p + take; y = y0 + t * h; K = key(pt)
            for k, (lab, f) in enumerate(K[:4]): S.paste(cell(pt, 'fpp', f, (w, h), (f'{pt}: ' if k == 0 else '') + lab, crop=crop), (k * w, y))
            S.paste(cell(pt, 'out', K[1][1], (w, h), 'outside, ' + K[1][0]), (4 * w, y))
            s, g = load(pt); x = 5 * w + 10; dr.text((x, y + 4), f"{pt}  {FAM.PICKS[p][0]}", fill=YEL, font=font(18)); dr.text((x, y + 26), FAM.TAKE_NAME[take], fill=(200, 200, 200), font=font(14, False))
            for i, tx in enumerate(FAM.numbers(s, g)): dr.text((x, y + 46 + i * 19), tx, fill=(230, 230, 230) if not tx.startswith('gate: ') or tx == 'gate: pass' else (255, 120, 110), font=font(13, False))
    S.save(out); print('wrote', out, S.size)


def grid(ids, out=None, cols=5):
    out = out or f'{REV}/{FAM.FILE}_grid.mp4'; w, h = 384, 216; T = FAM.TAKES; rows = (len(ids) + cols - 1) // cols
    n = max(load(p + t)[0]['frames'] for p in ids for t in T); tmp = f'{REV}/frames_grid'; os.makedirs(tmp, exist_ok=True)
    for f in range(n + 20):
        G = Image.new('RGB', (w * cols, len(T) * h * rows), (20, 20, 24))
        for k, p in enumerate(ids):
            x, y = (k % cols) * w, (k // cols) * len(T) * h
            for t, take in enumerate(T): G.paste(cell(p + take, 'fpp', f, (w, h), f'{p}{take}'), (x, y + t * h))
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 20), '-vf', 'format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-crf', '23', out]); print('wrote', out)


def video(pt, out):
    s, g = load(pt); N = s['frames']; w, h = 640, 360; tmp = f'{REV}/frames_{pt}'; os.makedirs(tmp, exist_ok=True)
    for f in range(N + 15):
        G = Image.new('RGB', (2 * w, h)); nm = f'{pt} {FAM.PICKS[pt[:-1]][0]}'
        G.paste(cell(pt, 'fpp', f, (w, h), nm), (0, 0)); G.paste(cell(pt, 'out', f, (w, h), nm + ' (outside)'), (w, 0)); G.save(f'{tmp}/v_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/v_%03d.png', '-frames:v', str(N + 15), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '20', out])


def strip(pt, out):
    s, g = load(pt); L = g['layout']; fr = [0] + [f for _, f in key(pt)] + [max((L['hide_start'] or 1) - 1, 0), (L['hide_end'] or 0) + 1, s['frames'] - 1]; fr = sorted(set(fr))
    w, h = 480, 270; cols = 4; S = Image.new('RGB', (w * cols, h * ((len(fr) + cols - 1) // cols)), (20, 20, 24))
    for k, f in enumerate(fr): S.paste(cell(pt, 'fpp', f, (w, h), f'{pt} frame {f}'), ((k % cols) * w, (k // cols) * h))
    S.save(out)


STYLE_FROM = common.mp('C:/Modding/anim-work/long-partner/review/long-topmag.html')


def page(ids):
    SC = json.load(open(renv.OUT + '/scores.json')); W = SC['weights']; os.makedirs(REV, exist_ok=True); rows = []
    for p in ids:
        sc = SC['drafts'][p]; takes = []
        for take in FAM.TAKES:
            pt = p + take; s, g = load(pt); m = g['motion']; L = g['layout']; I = g['inertia']
            if not os.path.exists(f'{REV}/{pt}.mp4') or os.path.getmtime(f'{REV}/{pt}.mp4') < os.path.getmtime(s['out']): video(pt, f'{REV}/{pt}.mp4')
            strip(pt, f'{REV}/{pt}_strip.png')
            takes.append({'id': pt, 'gun': FAM.TAKE_NAME[take], 'm': [f"{m['peak_speed']}", f"{m['peak_at']}", f"{m['stop']}", f"{g['eye_cm'][0]} cm", f"{g['cover_peak'][0]}%",
                          f"f{L['hide_start']}-{L['hide_end']}", f"{g['wrist'][0]:.0f} deg", f"{g['reach'][0]:.3f}", f"{g['guns_gap_cm'][0]:.0f} cm", f"{max(g['end_cm'], g['start_cm']):.3f} cm",
                          f"{I['max_overshoot_cm']} cm / {I['max_overshoot_deg']} deg", f"{I['rotation_lag_f']} f", FAM.shell_cell(s, g)], 'fails': g['fails']})
        rows.append({'id': p, 'name': FAM.PICKS[p][0], 's': sc['s'], 'mech': html.escape(sc.get('mechanism', '')), 'concept': html.escape(FAM.DOC[p]), 'good': sc['good'], 'bad': sc['bad'], 'takes': takes})
    tot = lambda r: sum(a * b for a, b in zip(r['s'], W)); top = sorted(rows, key=lambda r: -tot(r))[:3]
    css = open(STYLE_FROM, encoding='utf-8').read(); css = css[css.index('<style>'):css.index('</style>') + 8]
    css = css.replace('</style>', '.takes{display:grid;gap:14px}.take h3{margin:6px 0 4px;font-size:15px}.player video{max-width:100%}.mech{font-weight:600}</style>')
    pg = f'''<title>{FAM.TITLE}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
{css}
<div class="wrap">
  <section class="intro">
    <h1>{FAM.TITLE}</h1>
    {FAM.INTRO}
    <p><b>My top three:</b> {', '.join(f'<a href="#{r["id"]}">{r["id"]} {html.escape(r["name"])}</a> ({tot(r):.2f})' for r in top)}.</p>
  </section>
  <section class="intro">
    <h2>Scores</h2>
    <div class="legend muted">
      <span><b>Fit</b> (30%): a believable one-handed technique for this action; the parts and shells move because of what the gun does. <b>Clarity</b> (25%): reads in first person, nothing in the face. <b>Weight</b> (20%): inertia reads (overshoot, rebound, lag), shells move as rigid bodies at the gun's speed; motion against the approved clips. <b>Style</b> (15%): a different physical idea from every other draft and from the banned list. <b>Cost</b> (10%): risk in game and for the other guns of the family.</span>
      <span><b>Peak</b>: largest grip speed, cm per frame (target 8 to 12). <b>At</b>: where in a big move the peak is (0.45 to 0.65). <b>Stop</b>: speed lost in the last 2 frames of a move (3.5 to 6). <b>Eye</b> (rule 20 cm, or the gun's idle less 1 cm), <b>Cover</b> (rule 18%), <b>Hidden</b>: frames the script may fast-forward. <b>Wrist</b> (113), <b>Reach</b> (0.985), <b>Guns</b>: gap to the other gun. <b>End</b>: first and last frame against the idle. <b>Overshoot</b>: largest excursion past the hand's target after a stop (spring-damper gun). <b>Lag</b>: frames the rotation trails the translation. <b>Shells</b>: see the family notes.</span>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Draft</th><th class="num">Fit</th><th class="num">Clarity</th><th class="num">Weight</th><th class="num">Style</th><th class="num">Cost</th><th class="num">Score</th><th>Take</th><th class="num">Peak</th><th class="num">At</th><th class="num">Stop</th><th class="num">Eye</th><th class="num">Cover</th><th class="num">Hidden</th><th class="num">Wrist</th><th class="num">Reach</th><th class="num">Guns</th><th class="num">End</th><th class="num">Overshoot</th><th class="num">Lag</th><th>Shells</th><th>Gate failures</th></tr></thead>
      <tbody id="tbody"></tbody></table></div>
  </section>
  <section id="list"></section>
</div>
<script>
const V = {json.dumps(rows)};
const W = {json.dumps(W)};
const NT = {len(FAM.TAKES)};
const total = s => s.reduce((a, x, i) => a + x * W[i], 0);
V.forEach(v => v.t = total(v.s));
V.sort((a, b) => b.t - a.t || b.s[0] - a.s[0]);
const cls = t => t >= 7 ? "s-good" : t >= 6 ? "s-mid" : "s-low";
function player(id, gun) {{
  return `<div class="take"><h3>${{id}} &middot; ${{gun}}</h3><div class="player">
    <video src="${{id}}.mp4" controls loop muted playsinline preload="metadata"></video>
    <div class="speed" role="group" aria-label="Playback speed for ${{id}}">Speed
      ${{[1, 0.5, 0.25].map(r => `<button type="button" data-r="${{r}}" aria-pressed="${{r === 1}}">${{r}}x</button>`).join("")}}
    </div>
    <details><summary>Key frames</summary><img class="strip" src="${{id}}_strip.png" alt="Labelled first-person key frames of ${{id}}" loading="lazy"></details></div></div>`;
}}
function wire(el) {{
  el.querySelectorAll(".player").forEach(p => {{
    const vid = p.querySelector("video");
    p.querySelectorAll(".speed button").forEach(b => b.addEventListener("click", () => {{
      vid.playbackRate = parseFloat(b.dataset.r);
      p.querySelectorAll(".speed button").forEach(o => o.setAttribute("aria-pressed", String(o === b)));
      vid.play().catch(() => {{}});
    }}));
  }});
}}
const tb = document.getElementById("tbody");
V.forEach((v, i) => {{
  v.takes.forEach((k, j) => {{
    const tr = document.createElement("tr");
    tr.innerHTML = (j === 0 ? `<td class="mono" rowspan="${{NT}}">${{i + 1}}</td><td rowspan="${{NT}}"><a href="#${{v.id}}">${{v.id}} ${{v.name}}</a></td>` +
      v.s.map(x => `<td class="num" rowspan="${{NT}}">${{x}}</td>`).join("") + `<td class="num total ${{cls(v.t)}}" rowspan="${{NT}}">${{v.t.toFixed(2)}}</td>` : "") +
      `<td class="mono">${{k.id}}</td>` + k.m.map(x => `<td class="num">${{x}}</td>`).join("") + `<td>${{k.fails.length ? k.fails.join("; ") : "none"}}</td>`;
    tb.appendChild(tr);
  }});
}});
const labels = {json.dumps(SC['labels'])};
const list = document.getElementById("list");
V.forEach((v, i) => {{
  const el = document.createElement("article"); el.className = "variant"; el.id = v.id;
  el.innerHTML = `
    <div class="head"><span class="rank">#${{i + 1}} - ${{v.id}}</span><h2>${{v.name}}</h2><span class="score ${{cls(v.t)}}">${{v.t.toFixed(2)}} / 10</span></div>
    <div class="row">
      <div class="takes">${{v.takes.map(k => player(k.id, k.gun)).join("")}}</div>
      <div class="notes">
        <p class="mech">${{v.mech}}</p>
        <p>${{v.concept}}</p>
        <div class="bars">${{v.s.map((x, k) => `<span>${{labels[k]}}</span><span class="bar"><i style="width:${{x * 10}}%"></i></span><span class="mono">${{x}}</span>`).join("")}}</div>
        <ul>${{v.good.map(g => `<li>${{g}}</li>`).join("")}}</ul>
        <ul class="muted">${{v.bad.map(b => `<li>${{b}}</li>`).join("")}}</ul>
        ${{v.takes.map(k => `<p class="mono muted">${{k.id}}: peak ${{k.m[0]}} cm/f at ${{k.m[1]}}, stop ${{k.m[2]}}, eye ${{k.m[3]}}, cover ${{k.m[4]}}, hidden ${{k.m[5]}}, wrist ${{k.m[6]}}, reach ${{k.m[7]}}, guns ${{k.m[8]}}, end ${{k.m[9]}}, overshoot ${{k.m[10]}}, lag ${{k.m[11]}}, shells ${{k.m[12]}}${{k.fails.length ? "; FAILS: " + k.fails.join("; ") : ""}}</p>`).join("")}}
      </div>
    </div>`;
  list.appendChild(el); wire(el);
}});
</script>
'''
    p = f'{REV}/review.html'; open(p, 'w', encoding='utf-8').write(pg); print('wrote', p)
    for r in sorted(rows, key=lambda r: -tot(r)): print(f"  {r['id']} {r['name']}: {tot(r):.2f}")


if __name__ == '__main__':
    argv = sys.argv[2:]; cmd = argv[0]
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(FAM.PICKS)
    if cmd == 'frames':
        for p in ids:
            for t in FAM.TAKES: render(p + t); print('rendered', p + t, flush=True)
    elif cmd == 'dense': dense(argv[1])
    elif cmd == 'sheet': sheet(ids)
    elif cmd == 'grid': grid(ids)
    elif cmd == 'page': page(ids)
    else: raise SystemExit(__doc__)
