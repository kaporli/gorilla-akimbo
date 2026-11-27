"""Review graphics of the SMG/shotgun FRONT round 2 drafts (sf2.py): frames, dense sheets, strips, per-take videos,
contact sheet, grid video, scored review page. Blender runs one process at a time (memory).

usage:
  sf2review.py frames [ids csv] [--takes A,B]   render first person and outside frames of each take (sequential)
  sf2review.py dense <id><take> [--every 2]      every 2nd frame around each move, first person over outside
  sf2review.py sheet [ids csv]                   contact sheet: per draft a row, take A then take B
  sf2review.py grid [ids csv]                    grid video of all drafts, take A over take B
  sf2review.py page [ids csv]                    scored review page (scores.json), videos, strips
Output: <OUT>/review/
"""
import os, sys, json, subprocess, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import sf2, rrender3
from rrender import font, ffmpeg, SCENE, CAM
from PIL import Image, ImageDraw

REV = renv.OUT + '/review'
CL = renv.OUT + '/clips/pma'
YEL = (255, 220, 0)
TAKE_NAME = {'A': 'A snappy, Saratoga', 'B': 'B heavy, Zhuo'}


def spec_path(pt): return f'{CL}/{sf2.stem(pt[:-1], pt[-1])}.json'
def load(pt): p = spec_path(pt); return json.load(open(p)), json.load(open(p[:-5] + '_gate.json'))
def fdir(pt): return rrender3.fdir(spec_path(pt))


def render(pt, res=(640, 360)):
    """First person, then outside (one Blender at a time). The gun's own part list (weapons.json parts) is drawn,
    its moving parts posed from its own anim sets, the magazine from the own track."""
    p = spec_path(pt); spec = json.load(open(p)); d = fdir(pt); N = spec['frames']; gid = spec['_gun']; parts = common.gun(gid)['parts']
    for v in ('fpp', 'out'):
        if os.path.exists(f'{d}/{v}_{N - 1:03d}.png') and os.path.getmtime(f'{d}/{v}_{N - 1:03d}.png') > os.path.getmtime(spec['out']): continue
        cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': list(range(N)), 'out': f'{d}/{v}', 'body': spec['_body'], 'view': v, 'res': list(res),
               'right_gun': gid, 'left_gun': gid, 'right_parts': parts, 'left_parts': parts, 'right_mag_clip': spec['_gun_clip'], 'left_mag_clip': None,
               'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40], 'right_parts_anim': True, 'right_mag_track': spec['_track'],
               'right_parts_frames': spec['_part_frames']}
        cfg.update(CAM if v == 'fpp' else rrender3.OUTCAM['Right'])
        c = f'{d}/cfg_{v}.json'; json.dump(cfg, open(c, 'w'))
        r = subprocess.run([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', c], capture_output=True, text=True, errors='replace')
        if 'DONE' not in r.stdout: raise SystemExit(f'scene.py failed for {c}:\n' + '\n'.join((r.stdout + r.stderr).splitlines()[-15:]))
    return d


def key(pt):
    """Key moments: cocking piece back (opener), magazine out, fresh magazine (gun arriving on it), cocking home."""
    s, g = load(pt); mk = s['_marks']; mg = s['_mag']; se = s['_timing']['seated']
    return [('wind-up', mk['windup']), ('strike: magazine out', mg['release'] + 2), ('fresh magazine', se - 2), ('rack', mk['hit'])]


def phase(s, g, f):
    mk = s['_marks']; mg = s['_mag']; L = g['layout']; se = s['_timing']['seated']; hit = mk.get('hit')
    if abs(f - mk['cock']) <= 2: return 'opener (cocking back)'
    if f < mg['release']: return 'start' if f < mk['cock'] else ('wind-up' if f <= mk['windup'] else 'strike')
    if f < mg['release'] + 6: return 'magazine out'
    if L['hide_start'] is not None and L['hide_start'] <= f <= L['hide_end']: return 'HIDDEN: seated' if f == se else 'HIDDEN (fast-forward)'
    if hit is not None and abs(f - hit) <= 2: return 'rack (cocking home)'
    if f < se: return 'to the fresh magazine'
    if hit is not None and f < hit: return 'up'
    return 'settle'


def cell(pt, v, f, size, title, big=False, crop=None):
    s, g = load(pt); d = fdir(pt); ff = min(max(f, 0), s['frames'] - 1)
    im = Image.open(f'{d}/{v}_{ff:03d}.png').convert('RGB')
    if crop: im = im.crop((0, int(im.size[1] * crop[0]), im.size[0], int(im.size[1] * crop[1])))
    im = im.resize(size); dr = ImageDraw.Draw(im); W = size[0]; h = 30 if big else 22
    dr.rectangle((0, 0, W, h), fill=(0, 0, 0)); dr.text((6, 3), title, fill=YEL, font=font(19 if big else 14))
    sub = f'f{ff}/{s["frames"] - 1}  {phase(s, g, ff)}' + ('' if f == ff else '  (idle after the clip)'); fs = font(16 if big else 13, False)
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


def numbers(pt):
    s, g = load(pt); m = g['motion']; L = g['layout']; ex = g.get('mag_exit') or {}
    return [f"peak {m['peak_speed']} cm/f, at {m['peak_at']}, stop {m['stop']}", f"jerks {m['jerk_events']}, still {int(m['hold_share'] * 100)} %",
            f"hidden f{L['hide_start']}-{L['hide_end']} ({g['hidden_frames']} f)", f"eye {g['eye_cm'][0]} cm, cover {g['cover_peak'][0]} %",
            f"wrist {g['wrist'][0]} / in view {g['wrist_view']} deg, reach {g['reach'][0]}", f"magazine out f{s['_mag']['release']} at {g['mag_speed']['exit_cm_f']} cm/f, gun {g['mag_speed']['gun_cm_f']} (x{g['mag_speed']['ratio']})", f"hang {g['mag_hang']} f, lands (next-frame height {g['mag_gone_height_m']} m)",
            f"exit / insert off axis {g['exit_off_axis_cm']} / {g['insert_off_axis_cm']} cm, free exit {ex.get('off_axis_cm')}",
            'gate: ' + ('pass' if not g['fails'] else '; '.join(g['fails']))]


def sheet(ids, out=None):
    """One row per draft: take A first person at opener, magazine out, fresh magazine, rack, outside at magazine out;
    take B the same five; numbers of each take under its name."""
    out = out or f'{REV}/smg_front_round2_contact_sheet.png'; w, h = 384, 216; crop = (0.30, 1.0); nw = 360; top = 64; rowh = 2 * h + 10
    S = Image.new('RGB', (5 * w + nw, top + rowh * len(ids)), (20, 20, 24)); dr = ImageDraw.Draw(S)
    dr.text((10, 6), 'SMG and shotgun FRONT, round 2: wind-up chop variations (right hand, male V, empty reload). Per draft: take A on the Saratoga (top, 72 frames), take B on the Zhuo (bottom, 81 frames).', fill=(255, 255, 255), font=font(19))
    dr.text((10, 34), 'First person at the top of the wind-up, 2 frames after the release, fresh magazine, rack; outside 2 frames after the release. Magazine leaves at the strike speed (ratio 0.85 to 1.15); targets peak 8 to 12 cm/f.', fill=(180, 185, 195), font=font(16, False))
    for r, p in enumerate(ids):
        y0 = top + r * rowh
        for t, take in enumerate('AB'):
            pt = p + take; y = y0 + t * h; K = key(pt)
            for k, (lab, f) in enumerate(K): S.paste(cell(pt, 'fpp', f, (w, h), (f'{pt}: ' if k == 0 else '') + lab, crop=crop), (k * w, y))
            S.paste(cell(pt, 'out', K[1][1], (w, h), 'outside, magazine out'), (4 * w, y))
            x = 5 * w + 10; dr.text((x, y + 4), f"{pt}  {sf2.PICKS[p][0]}", fill=YEL, font=font(18)); dr.text((x, y + 26), TAKE_NAME[take], fill=(200, 200, 200), font=font(14, False))
            for i, tx in enumerate(numbers(pt)): dr.text((x, y + 46 + i * 20), tx, fill=(230, 230, 230) if not tx.startswith('gate: ') or tx == 'gate: pass' else (255, 120, 110), font=font(14, False))
    S.save(out); print('wrote', out, S.size)


def grid(ids, out=None, cols=5):
    """All drafts side by side, first person; take A row band over take B row band; frame numbers burned in."""
    out = out or f'{REV}/smg_front_round2_grid.mp4'; w, h = 384, 216; rows = (len(ids) + cols - 1) // cols
    n = max(load(p + t)[0]['frames'] for p in ids for t in 'AB'); tmp = f'{REV}/frames_grid'; os.makedirs(tmp, exist_ok=True)
    for f in range(n + 20):
        G = Image.new('RGB', (w * cols, 2 * h * rows), (20, 20, 24))
        for k, p in enumerate(ids):
            x, y = (k % cols) * w, (k // cols) * 2 * h
            for t, take in enumerate('AB'): G.paste(cell(p + take, 'fpp', f, (w, h), f'{p}{take} {sf2.PICKS[p][0]}'), (x, y + t * h))
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 20), '-vf', 'format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-crf', '23', out]); print('wrote', out)


def video(pt, out):
    """One take: first person | outside, 640 x 360 each, labels burned in, 15 frames of the idle after the clip."""
    s, g = load(pt); N = s['frames']; w, h = 640, 360; tmp = f'{REV}/frames_{pt}'; os.makedirs(tmp, exist_ok=True)
    for f in range(N + 15):
        G = Image.new('RGB', (2 * w, h)); nm = f'{pt} {sf2.PICKS[pt[:-1]][0]}'
        G.paste(cell(pt, 'fpp', f, (w, h), nm), (0, 0)); G.paste(cell(pt, 'out', f, (w, h), nm + ' (outside)'), (w, 0)); G.save(f'{tmp}/v_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/v_%03d.png', '-frames:v', str(N + 15), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '20', out])


def strip(pt, out):
    s, g = load(pt); L = g['layout']; fr = [0] + [f for _, f in key(pt)] + [L['hide_start'] - 1, (L['hide_end'] or 0) + 1, s['frames'] - 1]; fr = sorted(set(fr))
    w, h = 480, 270; cols = 4; S = Image.new('RGB', (w * cols, h * ((len(fr) + cols - 1) // cols)), (20, 20, 24))
    for k, f in enumerate(fr): S.paste(cell(pt, 'fpp', f, (w, h), f'{pt} frame {f}'), ((k % cols) * w, (k // cols) * h))
    S.save(out)


STYLE_FROM = common.mp('C:/Modding/anim-work/long-partner/review/long-topmag.html')


def page(ids):
    SC = json.load(open(renv.OUT + '/scores.json')); W = SC['weights']; os.makedirs(REV, exist_ok=True); rows = []
    for p in ids:
        sc = SC['drafts'][p]; takes = []
        for take in 'AB':
            pt = p + take; s, g = load(pt); m = g['motion']; L = g['layout']
            if not os.path.exists(f'{REV}/{pt}.mp4') or os.path.getmtime(f'{REV}/{pt}.mp4') < os.path.getmtime(s['out']): video(pt, f'{REV}/{pt}.mp4')
            strip(pt, f'{REV}/{pt}_strip.png')
            takes.append({'id': pt, 'gun': TAKE_NAME[take], 'm': [f"{m['peak_speed']}", f"{m['peak_at']}", f"{m['stop']}", f"{g['eye_cm'][0]} cm", f"{g['cover_peak'][0]}%",
                          f"f{L['hide_start']}-{L['hide_end']}", f"{g['wrist'][0]:.0f} deg", f"{g['reach'][0]:.3f}", f"{g['guns_gap_cm'][0]:.0f} cm", f"{max(g['end_cm'], g['start_cm']):.3f} cm",
                          f"{g['mag_hang']} f", f"{g['mag_speed']['exit_cm_f']} / {g['mag_speed']['gun_cm_f']}"], 'fails': g['fails']})
        s, _ = load(p + 'A')
        rows.append({'id': p, 'name': sf2.PICKS[p][0], 's': sc['s'], 'concept': html.escape(sf2.DOC[p]), 'good': sc['good'], 'bad': sc['bad'], 'takes': takes})
    tot = lambda r: sum(a * b for a, b in zip(r['s'], W)); top = sorted(rows, key=lambda r: -tot(r))[:3]
    css = open(STYLE_FROM, encoding='utf-8').read(); css = css[css.index('<style>'):css.index('</style>') + 8]
    css = css.replace('</style>', '.takes{display:grid;gap:14px}.take h3{margin:6px 0 4px;font-size:15px}.player video{max-width:100%}</style>')
    BA, BB = sf2.BUDGET['A'], sf2.BUDGET['B']
    pg = f'''<title>SMG Shotgun Reloads, Round 2</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
{css}
<div class="wrap">
  <section class="intro">
    <h1>SMG and Shotgun Reloads, Round 2 (front magazine)</h1>
    <p>{len(ids)} variations of round 1's wind-up chop (SF09, rebuilt here as SF11) for the FRONT family: a clear wind-up, one strike along the well that stops dead, the magazine driven out by it. Each in two takes: <b>A</b> on the Saratoga (light guns) and <b>B</b> on the Zhuo (heavy), right hand, male V, empty reload, starting and ending in the dual-wield idle. Round 1 stays as it was in <span class="mono">round1-front</span>.</p>
    <p class="muted"><b>One timing budget for all ten</b> (30 fps). Take A: opener f{BA['cock']}, wind-up, strike stops dead f{BA['stop']} (magazine released on the strike's fastest frame), dive to the rig, seat f{BA['seat']}, rise, rack f{BA['home']}, {BA['frames']} frames. Take B: the same beats about 13 % later: opener f{BB['cock']}, stop f{BB['stop']}, seat f{BB['seat']}, rack f{BB['home']}, {BB['frames']} frames. The gun's own frames (cocking back, magazine out, clamp, seat, cocking home) are mapped onto these beats; the previews pose the gun parts that way (in game the gun anim needs the same remap, unverified).</p>
    <p class="muted"><b>Magazine from the force.</b> Seated until the release, then it keeps the velocity and spin the gun gave it on that frame, gravity 9.81 m/s2 at 30 fps, no drag, until it lands. <b>Mag / gun</b> below: its exit speed against the gun's speed at the magazine over the 3 frames up to the release (cm/f; ratio 0.85 to 1.15 or the gate fails). Round 1's cause: three drafts slid the magazine out at 1.7 to 12 times the gun's speed, and on the Saratoga the falling magazine was removed 0.57 to 1.22 m above the ground (<span class="mono">measure/round1_magazine_speed.md</span>).</p>
    <p><b>My top three:</b> {', '.join(f'<a href="#{r["id"]}">{r["id"]} {html.escape(r["name"])}</a> ({tot(r):.2f})' for r in top)}.</p>
  </section>
  <section class="intro">
    <h2>Scores</h2>
    <div class="legend muted">
      <span><b>Fit</b> (30%): keeps what made the wind-up chop work (clear wind-up, one decisive strike along the well, the magazine visibly driven out) and gives the gun's frames a reason. <b>Clarity</b> (25%): reads in first person, nothing in the face. <b>Weight</b> (20%): the force reads, the magazine's speed matches it, the take reads as its gun; motion measured against the approved clips. <b>Style</b> (15%): different from SF11, from each other and from the rifle picks. <b>Cost</b> (10%): risk for the other guns of the family and in game.</span>
      <span><b>Peak</b>: largest grip speed, cm per frame (target 8 to 12). <b>At</b>: where in a big move the peak is (target 0.45 to 0.65). <b>Stop</b>: speed lost in the last 2 frames of a move (target 3.5 to 6). <b>Eye</b>: closest the gun gets to the eye while on screen (rule 20 cm). <b>Cover</b>: peak screen share (rule 18%). <b>Hidden</b>: frames the script may fast-forward. <b>Wrist</b> (rule 113), <b>Reach</b> (rule 0.985), <b>Guns</b>: gap to the other gun. <b>End</b>: first and last frame against the idle (rule 0.02 cm). <b>Hang</b>: frames the magazine is in the air and not in free fall (rule 0). <b>Mag / gun</b>: magazine exit speed / gun speed at the magazine over the 3 frames up to the release, cm/f.</span>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Draft</th><th class="num">Fit</th><th class="num">Clarity</th><th class="num">Weight</th><th class="num">Style</th><th class="num">Cost</th><th class="num">Score</th><th>Take</th><th class="num">Peak</th><th class="num">At</th><th class="num">Stop</th><th class="num">Eye</th><th class="num">Cover</th><th class="num">Hidden</th><th class="num">Wrist</th><th class="num">Reach</th><th class="num">Guns</th><th class="num">End</th><th class="num">Hang</th><th class="num">Mag / gun</th><th>Gate failures</th></tr></thead>
      <tbody id="tbody"></tbody></table></div>
  </section>
  <section id="list"></section>
</div>
<script>
const V = {json.dumps(rows)};
const W = {json.dumps(W)};
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
    tr.innerHTML = (j === 0 ? `<td class="mono" rowspan="2">${{i + 1}}</td><td rowspan="2"><a href="#${{v.id}}">${{v.id}} ${{v.name}}</a></td>` +
      v.s.map(x => `<td class="num" rowspan="2">${{x}}</td>`).join("") + `<td class="num total ${{cls(v.t)}}" rowspan="2">${{v.t.toFixed(2)}}</td>` : "") +
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
        <p>${{v.concept}}</p>
        <div class="bars">${{v.s.map((x, k) => `<span>${{labels[k]}}</span><span class="bar"><i style="width:${{x * 10}}%"></i></span><span class="mono">${{x}}</span>`).join("")}}</div>
        <ul>${{v.good.map(g => `<li>${{g}}</li>`).join("")}}</ul>
        <ul class="muted">${{v.bad.map(b => `<li>${{b}}</li>`).join("")}}</ul>
        ${{v.takes.map(k => `<p class="mono muted">${{k.id}}: peak ${{k.m[0]}} cm/f at ${{k.m[1]}}, stop ${{k.m[2]}}, eye ${{k.m[3]}}, cover ${{k.m[4]}}, hidden ${{k.m[5]}}, wrist ${{k.m[6]}}, reach ${{k.m[7]}}, guns ${{k.m[8]}}, end ${{k.m[9]}}, hang ${{k.m[10]}}, magazine / gun ${{k.m[11]}} cm/f${{k.fails.length ? "; FAILS: " + k.fails.join("; ") : ""}}</p>`).join("")}}
      </div>
    </div>`;
  list.appendChild(el); wire(el);
}});
</script>
'''
    p = f'{REV}/review.html'; open(p, 'w', encoding='utf-8').write(pg); print('wrote', p)
    for r in sorted(rows, key=lambda r: -tot(r)): print(f"  {r['id']} {r['name']}: {tot(r):.2f}")


if __name__ == '__main__':
    argv = sys.argv[1:]; o = lambda n: common.opt(argv, n); cmd = argv[0]
    takes = (o('--takes') or 'A,B').split(','); every = int(o('--every') or 2)
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(sf2.PICKS)
    if cmd == 'frames':
        for p in ids:
            for t in takes: render(p + t); print('rendered', p + t, flush=True)
    elif cmd == 'dense': dense(argv[1], every)
    elif cmd == 'sheet': sheet(ids)
    elif cmd == 'grid': grid(ids)
    elif cmd == 'page': page(ids)
    else: raise SystemExit(__doc__)
