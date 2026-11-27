"""Review graphics of the SMG/shotgun FRONT round 4 drafts (sf4.py); SF13 (round 2, pick 1) shown first for comparison: frames, dense sheets, strips, per-take videos,
contact sheet, grid video, scored review page. Blender runs one process at a time (memory).

usage:
  sf4review.py frames [ids csv] [--takes A,B]   render first person and outside frames of each take (sequential)
  sf4review.py dense <id><take> [--every 2]      every 2nd frame around each move, first person over outside
  sf4review.py sheet [ids csv]                   contact sheet: per draft a row, take A then take B
  sf4review.py grid [ids csv]                    grid video of all drafts, take A over take B
  sf4review.py page [ids csv]                    scored review page (scores.json), videos, strips
Output: <OUT>/review/
"""
import os, sys, json, subprocess, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import sf2, sf4, rrender3, inertia
from rrender import font, ffmpeg, SCENE, CAM
from PIL import Image, ImageDraw

REV = renv.OUT + '/review'
CL = renv.OUT + '/clips/pma'
YEL = (255, 220, 0)
TAKE_NAME = {'A': 'A snappy, Saratoga', 'B': 'B heavy, Zhuo'}


PICK1 = 'SF13'
R2 = common.mp('C:/Modding/anim-work/smg-shotgun/round2-front/clips/pma')
NAME = lambda p: 'Low chop (pick 1, round 2)' if p == PICK1 else sf4.PICKS[p][0]


def spec_path(pt): return f'{R2 if pt[:-1] == PICK1 else CL}/{sf2.stem(pt[:-1], pt[-1])}.json'
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


def track(pt): return json.load(open(load(pt)[0]['_track']))


def key(pt):
    """Key moments: the move (2 frames before the latch), magazine out (free), fresh magazine, rack."""
    s, g = load(pt); mk = s['_marks']; mg = s['_mag']; se = s['_timing']['seated']; tr = track(pt)
    out = tr['free_from'] + 1 if tr['free_from'] < s['frames'] else mg['release'] + 3
    return [('the move', max(mg['release'] - 2, 0)), ('magazine out', out), ('fresh magazine', se - 2), ('rack', mk['hit'])]


def phase(s, g, f):
    mk = s['_marks']; mg = s['_mag']; L = g['layout']; se = s['_timing']['seated']; hit = mk.get('hit')
    tr = json.load(open(s['_track'])); ff = tr['free_from']
    if abs(f - mk['cock']) <= 2: return 'opener (cocking back)'
    if f < mg['release']: return 'start' if f < mk['cock'] else 'the move'
    if f < ff and mg.get('mode', 'phys') == 'phys': return 'magazine slides out'
    if f < ff + 5: return 'magazine out'
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
    s, g = load(pt); m = g['motion']; L = g['layout']; ms = g['mag_speed']; inn = g.get('inertia')
    rows = [f"peak {m['peak_speed']} cm/f, at {m['peak_at']}, stop {m['stop']}", f"hidden f{L['hide_start']}-{L['hide_end']} ({g['hidden_frames']} f), eye {g['eye_cm'][0]} cm",
            f"wrist {g['wrist'][0]} / in view {g['wrist_view']} deg, reach {g['reach'][0]}"]
    if inn:
        G = inn['gun']; M = inn['mag']
        rows += [f"overshoot {G['overshoot_cm_max']} cm / {G['overshoot_deg_max']} deg, settle {G['settle_f_max']} f", f"rot lag {G['rot_lag_f']} f, muzzle trail {G['muzzle_trail_deg']} deg",
                 f"seat jolt {seat_jolt(G)}", f"mag: slide {M['slide_f']} f, exit {M['exit_cm_f']} cm/f, spin {M['spin_deg_f']} deg/f",
                 'pull ' + ', '.join(f"{k.replace('gun_', '')} {v} g" for k, v in M['pull_g'].items())]
    else: rows += [f"magazine f{s['_mag']['release']}: {ms['exit_cm_f']} cm/f, gun {ms['gun_cm_f']} (x{ms.get('ratio')})", 'round 2 model (no inertia simulation)']
    rows.append('gate: ' + ('pass' if not g['fails'] else '; '.join(g['fails'])))
    return rows


def seat_jolt(G):
    im = [e for e in G.get('impacts', []) if e['name'] == 'seat']
    return f"{im[0]['impact_cm_f']} cm/f in, {im[0]['rebound_cm_f']} out" if im else 'none'


def sheet(ids, out=None):
    """One row per draft: take A first person at opener, magazine out, fresh magazine, rack, outside at magazine out;
    take B the same five; numbers of each take under its name."""
    out = out or f'{REV}/smg_front_round4_contact_sheet.png'; w, h = 384, 216; crop = (0.30, 1.0); nw = 420; top = 64; rowh = 2 * h + 10
    S = Image.new('RGB', (5 * w + nw, top + rowh * len(ids)), (20, 20, 24)); dr = ImageDraw.Draw(S)
    dr.text((10, 6), 'SMG and shotgun FRONT, round 4: ten new techniques with simulated inertia, for picks 2 and 3; SF13 low chop (pick 1) on top. Take A Saratoga (72 frames), take B Zhuo (81 frames).', fill=(255, 255, 255), font=font(19))
    dr.text((10, 34), 'First person 2 frames before the latch, magazine out, fresh magazine, rack; outside at magazine out. Gun: spring-damper on the hand target. Magazine: slides along the well under the pseudo-forces, then a rigid body.', fill=(180, 185, 195), font=font(16, False))
    for r, p in enumerate(ids):
        y0 = top + r * rowh
        for t, take in enumerate('AB'):
            pt = p + take; y = y0 + t * h; K = key(pt)
            for k, (lab, f) in enumerate(K): S.paste(cell(pt, 'fpp', f, (w, h), (f'{pt}: ' if k == 0 else '') + lab, crop=crop), (k * w, y))
            S.paste(cell(pt, 'out', K[1][1], (w, h), 'outside, magazine out'), (4 * w, y))
            x = 5 * w + 10; dr.text((x, y + 4), f"{pt}  {NAME(p)}", fill=YEL, font=font(18)); dr.text((x, y + 26), TAKE_NAME[take], fill=(200, 200, 200), font=font(14, False))
            for i, tx in enumerate(numbers(pt)): dr.text((x, y + 44 + i * 16), tx, fill=(230, 230, 230) if not tx.startswith('gate: ') or tx == 'gate: pass' else (255, 120, 110), font=font(14, False))
    S.save(out); print('wrote', out, S.size)


def grid(ids, out=None, cols=5):
    """All drafts side by side, first person; take A row band over take B row band; frame numbers burned in."""
    out = out or f'{REV}/smg_front_round4_grid.mp4'; w, h = 384, 216; rows = (len(ids) + cols - 1) // cols
    n = max(load(p + t)[0]['frames'] for p in ids for t in 'AB'); tmp = f'{REV}/frames_grid'; os.makedirs(tmp, exist_ok=True)
    for f in range(n + 20):
        G = Image.new('RGB', (w * cols, 2 * h * rows), (20, 20, 24))
        for k, p in enumerate(ids):
            x, y = (k % cols) * w, (k // cols) * 2 * h
            for t, take in enumerate('AB'): G.paste(cell(p + take, 'fpp', f, (w, h), f'{p}{take} {NAME(p)}'), (x, y + t * h))
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 20), '-vf', 'format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-crf', '23', out]); print('wrote', out)


def video(pt, out):
    """One take: first person | outside, 640 x 360 each, labels burned in, 15 frames of the idle after the clip."""
    s, g = load(pt); N = s['frames']; w, h = 640, 360; tmp = f'{REV}/frames_{pt}'; os.makedirs(tmp, exist_ok=True)
    for f in range(N + 15):
        G = Image.new('RGB', (2 * w, h)); nm = f'{pt} {NAME(pt[:-1])}'
        G.paste(cell(pt, 'fpp', f, (w, h), nm), (0, 0)); G.paste(cell(pt, 'out', f, (w, h), nm + ' (outside)'), (w, 0)); G.save(f'{tmp}/v_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/v_%03d.png', '-frames:v', str(N + 15), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '20', out])


def strip(pt, out):
    s, g = load(pt); L = g['layout']; fr = [0] + [f for _, f in key(pt)] + [L['hide_start'] - 1, (L['hide_end'] or 0) + 1, s['frames'] - 1]; fr = sorted(set(fr))
    w, h = 480, 270; cols = 4; S = Image.new('RGB', (w * cols, h * ((len(fr) + cols - 1) // cols)), (20, 20, 24))
    for k, f in enumerate(fr): S.paste(cell(pt, 'fpp', f, (w, h), f'{pt} frame {f}'), ((k % cols) * w, (k // cols) * h))
    S.save(out)


STYLE_FROM = common.mp('C:/Modding/anim-work/long-partner/review/long-topmag.html')


def inertia_cells(g):
    """Inertia columns of one take (None for SF13, built before the model)."""
    inn = g.get('inertia')
    if not inn: return ['-'] * 7
    G = inn['gun']; M = inn['mag']; im = [e for e in G['impacts'] if e['name'] == 'seat']
    return [f"{G['overshoot_cm_max']} cm / {G['overshoot_deg_max']} deg", f"{G['settle_f_max']} f", f"{G['rot_lag_f']} f", f"{G['muzzle_trail_deg']} deg",
            f"{im[0]['impact_cm_f']} / {im[0]['rebound_cm_f']}" if im else '-', f"{M['slide_f']} f, {M['exit_cm_f']} cm/f", f"{M['spin_deg_f']} deg/f"]


def page(ids):
    SC = json.load(open(renv.OUT + '/scores.json')); W = SC['weights']; os.makedirs(REV, exist_ok=True); rows = []
    for p in ids:
        sc = SC['drafts'][p]; takes = []
        for take in 'AB':
            pt = p + take; s, g = load(pt); m = g['motion']; L = g['layout']; ms = g['mag_speed']
            if not os.path.exists(f'{REV}/{pt}.mp4') or os.path.getmtime(f'{REV}/{pt}.mp4') < os.path.getmtime(s['out']): video(pt, f'{REV}/{pt}.mp4')
            strip(pt, f'{REV}/{pt}_strip.png')
            takes.append({'id': pt, 'gun': TAKE_NAME[take], 'm': [f"{m['peak_speed']}", f"{m['peak_at']}", f"{m['stop']}", f"{g['eye_cm'][0]} cm", f"{g['cover_peak'][0]}%",
                          f"f{L['hide_start']}-{L['hide_end']}", f"{g['wrist'][0]:.0f} deg", f"{g['reach'][0]:.3f}", f"{g['guns_gap_cm'][0]:.0f} cm", f"{max(g['end_cm'], g['start_cm']):.3f} cm",
                          f"{g['mag_hang']} f", f"{ms['exit_cm_f']} / {ms['gun_cm_f']}"] + inertia_cells(g), 'fails': g['fails']})
        r = {'id': p, 'name': NAME(p), 's': sc['s'], 'pick1': p == PICK1, 'good': sc['good'], 'bad': sc['bad'], 'takes': takes}
        if p == PICK1: r.update(concept=html.escape(sf2.DOC[p]), release='stop (round 2 model)', load='rig', why='')
        else: r.update(concept=html.escape(sf4.DOC[p]), release=sf4.RELEASE[p], load=sf4.LOAD[p], why=html.escape(sf4.WHY[p]))
        rows.append(r)
    tot = lambda r: sum(a * b for a, b in zip(r['s'], W)); top = sorted([r for r in rows if not r['pick1']], key=lambda r: -tot(r))[:2]
    css = open(STYLE_FROM, encoding='utf-8').read(); css = css[css.index('<style>'):css.index('</style>') + 8]
    css = css.replace('</style>', '.takes{display:grid;gap:14px}.take h3{margin:6px 0 4px;font-size:15px}.player video{max-width:100%}.why{border-left:3px solid currentColor;padding-left:10px}</style>')
    BA, BB = sf2.BUDGET['A'], sf2.BUDGET['B']; MA, MB = inertia.MODEL['A'], inertia.MODEL['B']
    pg = f'''<title>SMG Shotgun Reloads, Round 4</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
{css}
<div class="wrap">
  <section class="intro">
    <h1>SMG and Shotgun Reloads, Round 4 (front magazine)</h1>
    <p>Pick 1 is <b>SF13 low chop</b> (round 2), shown first for comparison. Below it, {len(ids) - 1} new drafts for picks 2 and 3. No banned move is reused on its own: two release the magazine by a spin, the rest by an upside-down gun pulled away faster than gravity, a crest, a bat, or a stop against the body (elbow on ribs, fist on hip); three use a new loading trick (toss-and-catch, a rig that pushes the magazine up, slap home on the thigh). Every pair differs in release or in loading. Under each draft: the mechanism in one sentence and why no banned entry covers it. Each in two takes: <b>A</b> on the Saratoga, <b>B</b> on the Zhuo, right hand, male V, empty reload, starting and ending in the dual-wield idle.</p>
    <p class="muted"><b>Real inertia.</b> The timeline is the hand's target; the gun is simulated on it as a mass on a spring-damper (take A: {MA['wp']} rad/f, damping {MA['zp']}; rotation {MA['wr']} rad/f about pitch and yaw, stiffer about the bore by the gun's own inertia; take B softer: {MB['wp']} and {MB['wr']} rad/f), so moves overshoot and rebound, rotation lags, the muzzle trails from the gun's own inertia about the grip, and the fresh magazine is a stop the gun hits with restitution ({MA['e']} / {MB['e']}) and a jolt. The magazine slides along the well under gravity and the pseudo-forces of the moving, turning gun (no scripted push), then flies as a rigid body with the velocity and spin it has, gravity only; a bounce off the left gun or the bat is an impulse with restitution.</p>
    <p class="muted"><b>Round 2's timing budget</b> (30 fps). Take A: opener f{BA['cock']}, the move up to about f{BA['stop']}, seat f{BA['seat']}, rack f{BA['home']}, {BA['frames']} frames. Take B: the same beats about 13 % later (seat f{BB['seat']}, rack f{BB['home']}, {BB['frames']} frames). Gun parts are posed on the budget (in game the gun anim needs the same remap, unverified).</p>
    <p><b>My suggestion for picks 2 and 3:</b> {', '.join(f'<a href="#{r["id"]}">{r["id"]} {html.escape(r["name"])}</a> ({tot(r):.2f})' for r in top)}.</p>
  </section>
  <section class="intro">
    <h2>Scores</h2>
    <div class="legend muted">
      <span><b>Fit</b> (30%): a believable one-handed technique for a front box magazine; the force that frees the magazine reads. <b>Clarity</b> (25%): reads in first person, nothing in the face. <b>Weight</b> (20%): inertia reads in gun and magazine. <b>Style</b> (15%): new against the banned list and against each other. <b>Cost</b> (10%): risk for the other guns and in game.</span>
      <span><b>Peak</b> grip cm/f (target 8 to 12), <b>At</b> (0.45 to 0.65), <b>Stop</b> (3.5 to 6), <b>Eye</b> (rule 20 cm), <b>Cover</b> (rule 18%), <b>Hidden</b> (fast-forward frames), <b>Wrist</b> (rule 113), <b>Reach</b> (0.985), <b>Guns</b> gap, <b>End</b> (0.02 cm), <b>Hang</b> (0), <b>Mag / gun</b>: magazine exit speed / gun speed at the magazine over the 3 frames up to the latch. Inertia: <b>Over</b> largest overshoot past a stop, <b>Settle</b> frames to within 0.3 cm and 1 deg, <b>Rot lag</b> frames the gun's turning trails the hand's, <b>Trail</b> largest muzzle angle behind the hand's aim in a big move, <b>Seat</b> impact / rebound cm/f, <b>Slide</b> frames in the well after the latch and exit speed, <b>Spin</b> of the free magazine.</span>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Draft</th><th>Release</th><th>Loading</th><th class="num">Fit</th><th class="num">Clarity</th><th class="num">Weight</th><th class="num">Style</th><th class="num">Cost</th><th class="num">Score</th><th>Take</th><th class="num">Peak</th><th class="num">At</th><th class="num">Stop</th><th class="num">Eye</th><th class="num">Cover</th><th class="num">Hidden</th><th class="num">Wrist</th><th class="num">Reach</th><th class="num">Guns</th><th class="num">End</th><th class="num">Hang</th><th class="num">Mag / gun</th><th class="num">Over</th><th class="num">Settle</th><th class="num">Rot lag</th><th class="num">Trail</th><th class="num">Seat</th><th class="num">Slide</th><th class="num">Spin</th><th>Gate failures</th></tr></thead>
      <tbody id="tbody"></tbody></table></div>
  </section>
  <section id="list"></section>
</div>
<script>
const V = {json.dumps(rows)};
const W = {json.dumps(W)};
const total = s => s.reduce((a, x, i) => a + x * W[i], 0);
V.forEach(v => v.t = total(v.s));
V.sort((a, b) => (b.pick1 - a.pick1) || b.t - a.t || b.s[0] - a.s[0]);
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
    tr.innerHTML = (j === 0 ? `<td class="mono" rowspan="2">${{v.pick1 ? "pick 1" : i}}</td><td rowspan="2"><a href="#${{v.id}}">${{v.id}} ${{v.name}}</a></td><td rowspan="2">${{v.release}}</td><td rowspan="2">${{v.load}}</td>` +
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
    <div class="head"><span class="rank">${{v.pick1 ? "PICK 1 (round 2)" : "#" + i}} - ${{v.id}}</span><h2>${{v.name}}</h2><span class="score ${{cls(v.t)}}">${{v.t.toFixed(2)}} / 10</span></div>
    <div class="row">
      <div class="takes">${{v.takes.map(k => player(k.id, k.gun)).join("")}}</div>
      <div class="notes">
        ${{v.why ? `<p class="why"><b>Mechanism, and why it is new:</b> ${{v.why}}</p>` : ""}}
        <p><b>Release:</b> ${{v.release}}. <b>Loading:</b> ${{v.load}}.</p>
        <p>${{v.concept}}</p>
        <div class="bars">${{v.s.map((x, k) => `<span>${{labels[k]}}</span><span class="bar"><i style="width:${{x * 10}}%"></i></span><span class="mono">${{x}}</span>`).join("")}}</div>
        <ul>${{v.good.map(g => `<li>${{g}}</li>`).join("")}}</ul>
        <ul class="muted">${{v.bad.map(b => `<li>${{b}}</li>`).join("")}}</ul>
        ${{v.takes.map(k => `<p class="mono muted">${{k.id}}: peak ${{k.m[0]}} cm/f at ${{k.m[1]}}, stop ${{k.m[2]}}, eye ${{k.m[3]}}, cover ${{k.m[4]}}, hidden ${{k.m[5]}}, wrist ${{k.m[6]}}, reach ${{k.m[7]}}, guns ${{k.m[8]}}, end ${{k.m[9]}}, hang ${{k.m[10]}}, magazine / gun ${{k.m[11]}} cm/f; overshoot ${{k.m[12]}}, settle ${{k.m[13]}}, rotation lag ${{k.m[14]}}, muzzle trail ${{k.m[15]}}, seat ${{k.m[16]}} cm/f, slide ${{k.m[17]}}, spin ${{k.m[18]}}${{k.fails.length ? "; FAILS: " + k.fails.join("; ") : ""}}</p>`).join("")}}
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
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(sf4.PICKS)
    with1 = [PICK1] + [i for i in ids if i != PICK1]
    if cmd == 'frames':
        for p in ids:
            for t in takes: render(p + t); print('rendered', p + t, flush=True)
    elif cmd == 'dense': dense(argv[1], every)
    elif cmd == 'sheet': sheet(with1)
    elif cmd == 'grid': grid(with1)
    elif cmd == 'page': page(with1)
    else: raise SystemExit(__doc__)
