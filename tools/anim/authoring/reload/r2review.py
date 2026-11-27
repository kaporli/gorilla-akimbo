"""Review graphics of the SMG round 1 GRIP / BULLPUP / TOP drafts (after sf1review.py, FRONT): frames, dense
sheets, strips, per-draft videos, contact sheet, grid video, scored review page in the FRONT page's format.
Blender runs one process at a time (memory).

usage: r1review.py <family module: grip1|bull1|top1> <cmd> [ids csv]
  frames | dense <id> | sheet | grid | page
Output: <OUT>/review/
"""
import os, sys, json, subprocess, html, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import r2lib as r1lib, rrender3
from rrender import font, ffmpeg, SCENE, CAM
from PIL import Image, ImageDraw

REV = renv.OUT + '/review'
CL = renv.OUT + '/clips/pma'
YEL = (255, 220, 0)
F = None


def take_name(): return f"{'A snappy' if F.TAKE == 'A' else 'B heavy'}, {common.gun(F.GUN)['name']}"
def spec_path(pt): return f'{CL}/{r1lib.stem(F, pt[:-1])}.json'
def load(pt): p = spec_path(pt); return json.load(open(p)), json.load(open(p[:-5] + '_gate.json'))
def fdir(pt): return rrender3.fdir(spec_path(pt))
def ids_all(): return [p + F.TAKE for p in getattr(F, 'PINNED', {})] + [p + F.TAKE for p in F.PICKS if p not in getattr(F, 'PINNED', {})]


def render(pt, res=(640, 360)):
    """First person, then outside (one Blender at a time). The gun's parts posed from its own anim set through the
    time map onto the beats (_gun_map), the magazines from the own track (old and fresh)."""
    p = spec_path(pt); spec = json.load(open(p)); d = fdir(pt); N = spec['frames']; gid = spec['_gun']; parts = common.gun(gid)['parts']
    for v in ('fpp', 'out'):
        last = f'{d}/{v}_{N - 1:03d}.png'
        if os.path.exists(last) and os.path.getmtime(last) > max(os.path.getmtime(spec['out']), os.path.getmtime(spec['_track'])): continue
        cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': list(range(N)), 'out': f'{d}/{v}', 'body': spec['_body'], 'view': v, 'res': list(res),
               'right_gun': gid, 'left_gun': gid, 'right_parts': parts, 'left_parts': parts, 'right_mag_clip': spec['_gun_clip'], 'left_mag_clip': None,
               'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40], 'right_parts_anim': True, 'right_mag_track': spec['_track'], 'right_parts_map': spec['_gun_map']}
        cfg.update(CAM if v == 'fpp' else rrender3.OUTCAM['Right'])
        c = f'{d}/cfg_{v}.json'; json.dump(cfg, open(c, 'w'))
        r = subprocess.run([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', c], capture_output=True, text=True, errors='replace')
        if 'DONE' not in r.stdout: raise SystemExit(f'scene.py failed for {c}:\n' + '\n'.join((r.stdout + r.stderr).splitlines()[-15:]))
    return d


def key(pt):
    """Key moments: the technique (just before the release), magazine out, fresh magazine (gun arriving on it), rack hit."""
    s, g = load(pt); mk = s['_marks']; B = s['_timing']['beats']
    return [('technique', B['rel'] - 3), ('magazine out', B['rel'] + 2), ('fresh magazine', B['seat'] - 2), ('rack', mk.get('hit', B['hit']))]


def phase(s, g, f):
    mk = s['_marks']; B = s['_timing']['beats']; L = g['layout']; se = B['seat']; hit = mk.get('hit')
    if f <= B['cue'] + 1: return 'opener' if f >= B['cue'] - 3 else 'start'
    if f < B['rel']: return 'technique'
    if f == B['rel']: return 'release'
    if f < B['rel'] + 6: return 'magazine out'
    if L['hide_start'] is not None and L['hide_start'] <= f <= L['hide_end']: return 'HIDDEN: seated' if f == se else 'HIDDEN (fast-forward)'
    if hit is not None and abs(f - hit) <= 2: return 'rack'
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
    """Every 2nd frame from the start to the end, key frames, and the idle after the clip; first person over outside."""
    s, g = load(pt); N = s['frames']; ks = [x[1] for x in key(pt)]
    fr = sorted(set(f for f in range(N) if f % every == 0) | set(ks) | {N - 1}) + [N + 5]
    w, h = 480, 270; hf = 150; cols = 6; per = cols * 4; base = f'{REV}/dense/{pt}'; os.makedirs(os.path.dirname(base), exist_ok=True); outs = []
    for pg in range((len(fr) + per - 1) // per):
        part = fr[pg * per:(pg + 1) * per]; rows = (len(part) + cols - 1) // cols
        S = Image.new('RGB', (w * cols, 34 + rows * (h + hf)), (20, 20, 24)); dr = ImageDraw.Draw(S)
        dr.text((8, 6), f"{pt} {s['_name']}: every {every}nd frame, key frames, and the idle after the clip; first person (lower part) over outside (page {pg + 1})", fill=(255, 255, 255), font=font(18))
        for k, f in enumerate(part):
            x, y = (k % cols) * w, 34 + (k // cols) * (h + hf)
            S.paste(cell(pt, 'fpp', f, (w, hf), f'f{f}', crop=(0.44, 1.0)), (x, y)); S.paste(cell(pt, 'out', f, (w, h), f'f{f} outside'), (x, y + hf))
        S.save(f'{base}_p{pg + 1}.png'); outs.append(f'{base}_p{pg + 1}.png')
    print('wrote', outs)


def numbers(pt):
    s, g = load(pt); m = g['motion']; L = g['layout']; ex = g.get('mag_exit') or {}; ms = g['mag_speed']
    return [f"peak {m['peak_speed']} cm/f, at {m['peak_at']}, stop {m['stop']}", f"jerks {m['jerk_events']}, still {int(m['hold_share'] * 100)} %",
            f"hidden f{L['hide_start']}-{L['hide_end']} ({g['hidden_frames']} f)", f"eye {g['eye_cm'][0]} cm, cover {g['cover_peak'][0]} %",
            f"wrist {g['wrist'][0]} / in view {g['wrist_view']} deg, reach {g['reach'][0]}", f"magazine out f{s['_mag']['release']} at {ms['mag_cm_f']} cm/f, gun on that frame {ms['gun_rel_cm_f']} ({ms.get('na') or 'ratio ' + str(ms['ratio'])})", f"in first person for {g['mag_view_frames']} frame{'s' if g['mag_view_frames'] != 1 else ''} after the release, hang {g['mag_hang']}",
            f"free exit off axis {ex.get('off_axis_cm')} cm, dv {g['release_dv_cm_f']}", 'gate: ' + ('pass' if not g['fails'] else '; '.join(g['fails']))]


def sheet(ids):
    """One row per draft: first person at the technique, magazine out, fresh magazine, rack; outside at magazine out;
    numbers beside."""
    out = f'{REV}/smg_{F.FAMILY.lower()}_round2_contact_sheet.png'; w, h = 384, 216; crop = (0.30, 1.0); nw = 380; top = 64; rowh = h + 8
    S = Image.new('RGB', (5 * w + nw, top + rowh * len(ids)), (20, 20, 24)); dr = ImageDraw.Draw(S)
    dr.text((10, 6), f'SMG {F.FAMILY}, round 2: one-handed reload drafts, take {take_name()} (right hand, male V, empty reload, {r1lib.BEATS[F.TAKE]["N"]} frames each).', fill=(255, 255, 255), font=font(19))
    dr.text((10, 34), 'First person at the technique (3 frames before the release), magazine out, fresh magazine, rack; outside at magazine out. Targets (approved clips): peak 8 to 12 cm/f at 0.45 to 0.65 of the move, stop 3.5 to 6.', fill=(180, 185, 195), font=font(16, False))
    for r, pt in enumerate(ids):
        y = top + r * rowh; K = key(pt)
        for k, (lab, f) in enumerate(K): S.paste(cell(pt, 'fpp', f, (w, h), (f'{pt}: ' if k == 0 else '') + lab, crop=crop), (k * w, y))
        S.paste(cell(pt, 'out', K[1][1], (w, h), 'outside, magazine out'), (4 * w, y))
        x = 5 * w + 10; dr.text((x, y + 4), f"{pt}  {F.PICKS[pt[:-1]][0]}", fill=YEL, font=font(18))
        for i, tx in enumerate(numbers(pt)): dr.text((x, y + 30 + i * 22), tx, fill=(230, 230, 230) if not tx.startswith('gate: ') or tx == 'gate: pass' else (255, 120, 110), font=font(14, False))
    S.save(out); print('wrote', out, S.size)


def grid(ids, cols=5):
    """All drafts side by side, first person, frame numbers burned in."""
    out = f'{REV}/smg_{F.FAMILY.lower()}_round2_grid.mp4'; w, h = 384, 216; rows = (len(ids) + cols - 1) // cols
    n = max(load(p)[0]['frames'] for p in ids); tmp = f'{REV}/frames_grid'; os.makedirs(tmp, exist_ok=True)
    for f in range(n + 20):
        G = Image.new('RGB', (w * cols, h * rows), (20, 20, 24))
        for k, p in enumerate(ids): G.paste(cell(p, 'fpp', f, (w, h), f'{p} {F.PICKS[p[:-1]][0]}'), ((k % cols) * w, (k // cols) * h))
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-y', '-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 20), '-vf', 'format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-crf', '23', out]); print('wrote', out)


def video(pt, out):
    """One draft: first person | outside, 640 x 360 each, labels burned in, 15 frames of the idle after the clip."""
    s, g = load(pt); N = s['frames']; w, h = 640, 360; tmp = f'{REV}/frames_{pt}'; os.makedirs(tmp, exist_ok=True)
    for f in range(N + 15):
        G = Image.new('RGB', (2 * w, h)); nm = f'{pt} {F.PICKS[pt[:-1]][0]}'
        G.paste(cell(pt, 'fpp', f, (w, h), nm), (0, 0)); G.paste(cell(pt, 'out', f, (w, h), nm + ' (outside)'), (w, 0)); G.save(f'{tmp}/v_{f:03d}.png')
    ffmpeg(['-y', '-framerate', '30', '-i', f'{tmp}/v_%03d.png', '-frames:v', str(N + 15), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '20', out])


def strip(pt, out):
    s, g = load(pt); L = g['layout']; fr = [0] + [f for _, f in key(pt)] + [L['hide_start'] - 1, (L['hide_end'] or 0) + 1, s['frames'] - 1]; fr = sorted(set(fr))
    w, h = 480, 270; cols = 4; S = Image.new('RGB', (w * cols, h * ((len(fr) + cols - 1) // cols)), (20, 20, 24))
    for k, f in enumerate(fr): S.paste(cell(pt, 'fpp', f, (w, h), f'{pt} frame {f}'), ((k % cols) * w, (k // cols) * h))
    S.save(out)


STYLE_FROM = common.mp('C:/Modding/anim-work/smg-shotgun/round1-front/review/review.html')      # the FRONT page: same CSS and tokens
FAMILY_TEXT = {'GRIP': ('Grip', 'Senkoh LX (magazine in the pistol grip, light)'),
               'BULLPUP': ('Bullpup', 'Pulsar (magazine behind the grip, under the stock, light)'),
               'TOP': ('Top', 'Warden (top magazine that leaves forward-up, heavy)')}


def page(ids):
    SC = json.load(open(renv.OUT + '/scores.json')); W = SC['weights']; os.makedirs(REV, exist_ok=True); rows = []
    for pt in ids:
        p = pt[:-1]; sc = SC['drafts'][p]; s, g = load(pt); m = g['motion']; L = g['layout']; ms = g['mag_speed']
        if not os.path.exists(f'{REV}/{pt}.mp4') or os.path.getmtime(f'{REV}/{pt}.mp4') < os.path.getmtime(f'{fdir(pt)}/out_{s["frames"] - 1:03d}.png'): video(pt, f'{REV}/{pt}.mp4')
        strip(pt, f'{REV}/{pt}_strip.png')
        takes = [{'id': pt, 'gun': take_name(), 'm': [f"{m['peak_speed']}", f"{m['peak_at']}", f"{m['stop']}", f"{g['eye_cm'][0]} cm", f"{g['cover_peak'][0]}%",
                  f"f{L['hide_start']}-{L['hide_end']}", f"{g['wrist'][0]:.0f} deg", f"{g['reach'][0]:.3f}", f"{g['guns_gap_cm'][0]:.0f} cm", f"{max(g['end_cm'], g['start_cm']):.3f} cm",
                  f"{g['mag_hang']} f", f"{g['release_dv_cm_f']}", f"{ms['mag_cm_f']} / {ms['gun_rel_cm_f']} ({ms.get('na') or ms['ratio']})", f"{g['mag_view_frames']} f"], 'fails': g['fails']}]
        rows.append({'id': p, 'name': F.PICKS[p][0], 's': sc['s'], 'concept': html.escape(s['_doc']), 'good': sc['good'], 'bad': sc['bad'], 'takes': takes,
                     'pin': getattr(F, 'PINNED', {}).get(p, '')})
    tot = lambda r: sum(a * b for a, b in zip(r['s'], W)); top = sorted([r for r in rows if not r['pin']], key=lambda r: -tot(r))[:3]
    pins = [r for r in rows if r['pin']]
    css = open(STYLE_FROM, encoding='utf-8').read(); css = css[css.index('<style>'):css.index('</style>') + 8]
    B = r1lib.BEATS[F.TAKE]; ev = r1lib.gun_events(F.GUN); A = r1lib.gun_map(F.GUN, F.TAKE)[1]; ttl, gtxt = FAMILY_TEXT[F.FAMILY]
    anch = ', '.join(f'f{a} on gun f{b}' for a, b in A[1:-1])
    pg = f'''<title>SMG {ttl} Reloads, Round 2</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
{css}
<div class="wrap">
  <section class="intro">
    <h1>SMG Reloads, Round 2 ({ttl.lower()} magazine)</h1>
    <p>{len(ids) - len(pins)} one-handed reload drafts for the {F.FAMILY} family, each a different technique{(' (plus the owner' + chr(39) + 's pick from round 1 at the top)') if pins else ''}: {gtxt}. Take <b>{take_name()}</b>, right hand, male V, empty reload, starting and ending in the dual-wield idle. Pick at most 3; nothing goes to production before that.</p>
    <p class="muted">One timing budget for all {len(ids)} drafts (owner feedback on FRONT): {B['N']} frames, opener f{B['cue']}, magazine out f{B['rel']}, rig f{B['arr']}, seated f{B['seat']}, held f{B['held']}, rack hit f{B['hit']}, idle f{B['idle']}. Take A is 68 frames, take B 77 (13 % slower). The gun's own anim is time-mapped onto these beats ({anch}; its own clip is {ev['frames']} frames). Round 1 made every draft a wind-up chop; here each draft is its own technique and at most one is a chop. Magazine: seated until the release frame, then it slides along its well pushed only by gravity and by the gun's own acceleration (a dead stop throws it on at the gun's speed, a jerk away leaves it behind, a tilt lets it slide out by its weight, a shake works it loose), or a rig holds it while the gun is pulled off; once out it flies free at 9.81 m/s2 to the ground. The fresh one waits still on a rig out of view and the gun is driven onto it. Mag / gun: magazine exit speed against the gun's speed on the release frame (FRONT round 2 metric, ratio 0.85 to 1.15; not applicable where a rig holds the magazine or the gun is still on the release frame). Videos: first person (camera fitted to the game, 105 degrees) and outside. Blender previews only; nothing in game.</p>
    {''.join(f'<p><b>{html.escape(r["pin"])}:</b> <a href="#{r["id"]}">{r["id"]} {html.escape(r["name"])}</a>, shown first.</p>' for r in pins)}
    <p><b>My top three{' of the new drafts' if pins else ''}:</b> {', '.join(f'<a href="#{r["id"]}">{r["id"]} {html.escape(r["name"])}</a> ({tot(r):.2f})' for r in top)}.</p>
  </section>
  <section class="intro">
    <h2>Scores</h2>
    <div class="legend muted">
      <span><b>Fit</b> (30%): the technique suits the magazine position and gives the gun's own frames a reason (magazine out, seat, rack). <b>Clarity</b> (25%): reads in first person, nothing in the face, the magazine seen driven out. <b>Weight</b> (20%): the take reads as its gun, measured motion against the approved clips, magazine speed from the force. <b>Style</b> (15%): a silhouette of its own in first person, different from the other drafts and from round 1. <b>Cost</b> (10%): risk in game.</span>
      <span><b>Peak</b>: largest grip speed, cm per frame (target 8 to 12). <b>At</b>: where in a big move the peak is (target 0.45 to 0.65). <b>Stop</b>: speed lost in the last 2 frames of a move (target 3.5 to 6). <b>Eye</b>: closest the gun gets to the eye while on screen (rule 20 cm). <b>Cover</b>: peak screen share (rule 18%). <b>Hidden</b>: frames the script may fast-forward. <b>Wrist</b> (rule 113), <b>Reach</b> (rule 0.985), <b>Guns</b>: gap to the other gun. <b>End</b>: first and last frame against the idle (rule 0.02 cm). <b>Hang</b>: frames the magazine is in the air and not in free fall (rule 0). <b>dv</b>: velocity jump at the hand-off to free fall, cm/f (rule 1.5). <b>Mag / gun</b>: magazine exit speed / the gun's speed on the release frame, cm/f, and their ratio (rule 0.85 to 1.15, as FRONT round 2; held by the rig or gun still: not applicable). <b>Mag seen</b>: frames the old magazine is on the first-person screen after the release.</span>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Draft</th><th class="num">Fit</th><th class="num">Clarity</th><th class="num">Weight</th><th class="num">Style</th><th class="num">Cost</th><th class="num">Score</th><th>Take</th><th class="num">Peak</th><th class="num">At</th><th class="num">Stop</th><th class="num">Eye</th><th class="num">Cover</th><th class="num">Hidden</th><th class="num">Wrist</th><th class="num">Reach</th><th class="num">Guns</th><th class="num">End</th><th class="num">Hang</th><th class="num">dv</th><th class="num">Mag / gun</th><th class="num">Mag seen</th><th>Gate failures</th></tr></thead>
      <tbody id="tbody"></tbody></table></div>
  </section>
  <section id="list"></section>
</div>
<script>
const V = {json.dumps(rows)};
const W = {json.dumps(W)};
const total = s => s.reduce((a, x, i) => a + x * W[i], 0);
V.forEach(v => v.t = total(v.s));
V.sort((a, b) => (b.pin ? 1 : 0) - (a.pin ? 1 : 0) || b.t - a.t || b.s[0] - a.s[0]);
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
    const tr = document.createElement("tr"); const n = v.takes.length;
    tr.innerHTML = (j === 0 ? `<td class="mono" rowspan="${{n}}">${{i + 1}}</td><td rowspan="${{n}}"><a href="#${{v.id}}">${{v.id}} ${{v.name}}</a></td>` +
      v.s.map(x => `<td class="num" rowspan="${{n}}">${{x}}</td>`).join("") + `<td class="num total ${{cls(v.t)}}" rowspan="${{n}}">${{v.t.toFixed(2)}}</td>` : "") +
      `<td class="mono">${{k.id}}</td>` + k.m.map(x => `<td class="num">${{x}}</td>`).join("") + `<td>${{k.fails.length ? k.fails.join("; ") : "none"}}</td>`;
    tb.appendChild(tr);
  }});
}});
const labels = {json.dumps(SC['labels'])};
const list = document.getElementById("list");
V.forEach((v, i) => {{
  const el = document.createElement("article"); el.className = "variant"; el.id = v.id;
  el.innerHTML = `
    <div class="head"><span class="rank">${{v.pin ? v.pin : "#" + (i + 1)}} - ${{v.id}}</span><h2>${{v.name}}</h2><span class="score ${{cls(v.t)}}">${{v.t.toFixed(2)}} / 10</span></div>
    <div class="row">
      <div class="takes">${{v.takes.map(k => player(k.id, k.gun)).join("")}}</div>
      <div class="notes">
        <p>${{v.concept}}</p>
        <p><b>${{v.takes.map(k => `In first person the magazine is visible for ${{parseInt(k.m[13])}} frame${{parseInt(k.m[13]) === 1 ? "" : "s"}} after the release.`).join(" ")}}</b></p>
        <div class="bars">${{v.s.map((x, k) => `<span>${{labels[k]}}</span><span class="bar"><i style="width:${{x * 10}}%"></i></span><span class="mono">${{x}}</span>`).join("")}}</div>
        <ul>${{v.good.map(g => `<li>${{g}}</li>`).join("")}}</ul>
        <ul class="muted">${{v.bad.map(b => `<li>${{b}}</li>`).join("")}}</ul>
        ${{v.takes.map(k => `<p class="mono muted">${{k.id}}: peak ${{k.m[0]}} cm/f at ${{k.m[1]}}, stop ${{k.m[2]}}, eye ${{k.m[3]}}, cover ${{k.m[4]}}, hidden ${{k.m[5]}}, wrist ${{k.m[6]}}, reach ${{k.m[7]}}, guns ${{k.m[8]}}, end ${{k.m[9]}}, hang ${{k.m[10]}}, dv ${{k.m[11]}}, mag / gun on the release frame ${{k.m[12]}} cm/f${{k.fails.length ? "; FAILS: " + k.fails.join("; ") : ""}}</p>`).join("")}}
      </div>
    </div>`;
  list.appendChild(el); wire(el);
}});
</script>
'''
    p = f'{REV}/review.html'; open(p, 'w', encoding='utf-8').write(pg); print('wrote', p)
    for r in sorted(rows, key=lambda r: -tot(r)): print(f"  {r['id']} {r['name']}: {tot(r):.2f}")


if __name__ == '__main__':
    argv = sys.argv[1:]; F = importlib.import_module(argv[0]); r1lib.prod.STATION.update(F.STATIONS); cmd = argv[1]; o = lambda n: common.opt(argv, n)
    ids = [x + F.TAKE if not x.endswith(F.TAKE) else x for x in argv[2].split(',')] if len(argv) > 2 and not argv[2].startswith('--') else ids_all()
    if cmd == 'frames':
        for pt in ids: render(pt); print('rendered', pt, flush=True)
    elif cmd == 'dense':
        for pt in ids: dense(pt, int(o('--every') or 2))
    elif cmd == 'sheet': sheet(ids)
    elif cmd == 'grid': grid(ids)
    elif cmd == 'page': page(ids)
    else: raise SystemExit(__doc__)
