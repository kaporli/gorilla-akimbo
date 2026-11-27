"""Review graphics of BREAK-OPEN round 2 (break2.py): frames with the simulated barrels, the rigid shells and the
drawn rig, dense sheets, strips, per-take videos, contact sheet, grid video, scored review page (round4-front format,
plus per draft: reference source, swing speed at the break and at the close, latch result). One Blender at a time.

usage:
  break2review.py frames [ids csv] [--takes A,B]   render first person and outside frames (sequential)
  break2review.py dense <id><take> [--every 2]
  break2review.py sheet | grid | page [ids csv]
"""
import os, sys, json, subprocess, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import break2, rrender3, breakphys as bp
from rrender import font, ffmpeg, SCENE, CAM
from PIL import Image, ImageDraw

REV = renv.OUT + '/review'; CL = renv.OUT + '/clips/pma'; YEL = (255, 220, 0)
TAKE_NAME = {'A': 'A snappy, Palica (66 f)', 'B': 'B heavy, Satara (75 f)'}
FILE = 'break_round3'


def spec_path(pt): return f'{CL}/{break2.prod.stem(break2.GUNS[pt[-1]], pt[:-1], pt[-1], break2.CLIP, "right")}.json'
def load(pt): p = spec_path(pt); return json.load(open(p)), json.load(open(p[:-5] + '_gate.json'))
def fdir(pt): return rrender3.fdir(spec_path(pt))
def NAME(p): return break2.PICKS[p][0]


def objects(spec):
    J = json.load(open(spec['_objects'])); mesh = common.find('weapon_meshes', bp.MESH[spec['_gun']] + '__mag_std_01.glb'); col = {'spent': (0.85, 0.75, 0.2, 1), 'fresh': (1, 0.35, 0.1, 1)}
    return [{'mesh': mesh, 'joints': J['joints'][n], 'color': col.get(n, (1, 0.35, 0.1, 1))} for n in J['names']]


def render(pt, res=(640, 360)):
    p = spec_path(pt); spec = json.load(open(p)); d = fdir(pt); N = spec['frames']; gid = spec['_gun']; parts = common.gun(gid)['parts']
    prims = json.load(open(spec['_prims'])) if spec.get('_prims') and os.path.exists(spec['_prims']) else []
    for v in ('fpp', 'out'):
        if os.path.exists(f'{d}/{v}_{N - 1:03d}.png') and os.path.getmtime(f'{d}/{v}_{N - 1:03d}.png') > os.path.getmtime(spec['out']): continue
        cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': list(range(N)), 'out': f'{d}/{v}', 'body': spec['_body'], 'view': v, 'res': list(res),
               'right_gun': gid, 'left_gun': gid, 'right_parts': parts, 'left_parts': parts, 'right_mag_clip': spec['_gun_clip'], 'left_mag_clip': None,
               'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40], 'right_parts_anim': True, 'right_mag_track': spec['_track'],
               'right_parts_frames': spec['_part_frames'], 'objects': objects(spec), 'prims': prims}
        cfg.update(CAM if v == 'fpp' else rrender3.OUTCAM['Right'])
        c = f'{d}/cfg_{v}.json'; json.dump(cfg, open(c, 'w'))
        r = subprocess.run([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', c], capture_output=True, text=True, errors='replace')
        if 'DONE' not in r.stdout: raise SystemExit(f'scene.py failed for {c}:\n' + '\n'.join((r.stdout + r.stderr).splitlines()[-15:]))
    return d


def key(pt):
    s, g = load(pt); ph = g['phys']; mk = s['_marks']; se = s['_timing']['seated']; N = s['frames']
    tr = int(ph['trip_f']) + 1 if ph.get('trip_f') else ph['lever_f'] + 6
    sh = int(ph['shut_f']) if ph.get('shut_f') else s['_timing']['handle'][0]
    return [('break', max(ph['open_swing_at'] or ph['lever_f'] + 3, 0)), ('shells out', min(tr + 2, N - 1)), ('loading', min(se, N - 1)), ('shut', min(sh, N - 1))]


def phase(s, g, f):
    L = g['layout']; ph = g['phys']; d = s['_hinge_deg'][min(f, len(s['_hinge_deg']) - 1)]; se = s['_timing']['seated']
    if f < ph['lever_f']: return 'idle'
    if ph.get('shut_f') is not None and f >= int(ph['shut_f']) + 1: return 'latched' if f < int(ph['shut_f']) + 4 else 'settle'
    if L['hide_start'] is not None and L['hide_start'] <= f <= L['hide_end']: return f'HIDDEN (fast-forward) {d:.0f} deg' + (' seat' if f == se else '')
    if ph.get('trip_f') is None or f <= ph['trip_f'] + 1: return f'breaking {d:.0f} deg'
    if f < se: return f'loading, barrels {d:.0f} deg'
    return f'closing, barrels {d:.0f} deg'


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
    s, g = load(pt); N = s['frames']; fr = sorted(set(range(0, N, every)) | {x[1] for x in key(pt)} | {N - 1}) + [N + 5]
    w, h = 480, 270; hf = 150; cols = 6; per = cols * 4; base = f'{REV}/dense/{pt}'; os.makedirs(os.path.dirname(base), exist_ok=True); outs = []
    for pg in range((len(fr) + per - 1) // per):
        part = fr[pg * per:(pg + 1) * per]; rows = (len(part) + cols - 1) // cols
        S = Image.new('RGB', (w * cols, 34 + rows * (h + hf)), (20, 20, 24)); dr = ImageDraw.Draw(S)
        dr.text((8, 6), f"{pt} {s['_name']}: every {every}nd frame, key frames, the idle after the clip; first person (lower part) over outside (page {pg + 1})", fill=(255, 255, 255), font=font(18))
        for k, f in enumerate(part):
            x, y = (k % cols) * w, 34 + (k // cols) * (h + hf)
            S.paste(cell(pt, 'fpp', f, (w, hf), f'f{f}', crop=(0.44, 1.0)), (x, y)); S.paste(cell(pt, 'out', f, (w, h), f'f{f} outside'), (x, y + hf))
        S.save(f'{base}_p{pg + 1}.png'); outs.append(f'{base}_p{pg + 1}.png')
    print('wrote', outs)


def numbers(pt):
    s, g = load(pt); m = g['motion']; L = g['layout']; ph = g['phys']; G = g['inertia']['gun']
    sp = ph['spent'][0] if ph['spent'] else {}
    return [f"break: gun {ph['open_swing_deg_f']} deg/f -> barrels {ph['barrel_at_trip_deg_f']} deg/f at the trip f{ph['trip_f']}",
            f"close: gun {ph['close_swing_deg_f']} deg/f -> barrels {ph['latch_w_deg_f']} deg/f (need {ph['latch_need_deg_f']}): {ph['latch']}" + (f" f{ph['shut_f']}" if ph['shut_f'] else ''),
            f"shells out {sp.get('exit_m_s')} m/s (carry {sp.get('carry_m_s')}), land f{sp.get('land')}",
            f"peak {m['peak_speed']} cm/f, overshoot {G['overshoot_cm_max']} cm / {G['overshoot_deg_max']} deg, lag {G['rot_lag_f']} f, trail {G['muzzle_trail_deg']} deg",
            f"hidden f{L['hide_start']}-{L['hide_end']}, eye {g['eye_cm'][0]} cm, wrist {g['wrist'][0]} / {g['wrist_view']}",
            'gate: ' + ('pass' if not g['fails'] else '; '.join(g['fails']))] + (['note: ' + g['notes'][0][:95]] if g.get('notes') else [])


def sheet(ids, out=None):
    out = out or f'{REV}/{FILE}_contact_sheet.png'; w, h = 384, 216; crop = (0.30, 1.0); nw = 470; top = 64; rowh = 2 * h + 10
    S = Image.new('RGB', (5 * w + nw, top + rowh * len(ids)), (20, 20, 24)); dr = ImageDraw.Draw(S)
    dr.text((10, 6), 'BREAK-OPEN shotguns, round 2: ten one-handed break-action reloads from captured game references. Take A Palica (66 f), take B Satara (75 f); right hand, male V, empty reload.', fill=(255, 255, 255), font=font(19))
    dr.text((10, 34), 'First person at the break, shells out, loading, latch; outside at shells out. Barrels: rigid body on the hinge pin driven only by the gun\'s motion, gravity, springs and body contacts.', fill=(180, 185, 195), font=font(16, False))
    for r, p in enumerate(ids):
        y0 = top + r * rowh
        for t, take in enumerate('AB'):
            pt = p + take; y = y0 + t * h; K = key(pt)
            for k, (lab, f) in enumerate(K): S.paste(cell(pt, 'fpp', f, (w, h), (f'{pt}: ' if k == 0 else '') + lab, crop=crop), (k * w, y))
            S.paste(cell(pt, 'out', K[1][1], (w, h), 'outside, shells out'), (4 * w, y))
            x = 5 * w + 10; dr.text((x, y + 4), f"{pt}  {NAME(p)}", fill=YEL, font=font(18)); dr.text((x, y + 26), TAKE_NAME[take], fill=(200, 200, 200), font=font(14, False))
            for i, tx in enumerate(numbers(pt)): dr.text((x, y + 46 + i * 17), tx, fill=(230, 230, 230) if not tx.startswith('gate: ') or tx == 'gate: pass' else (255, 120, 110), font=font(13, False))
    S.save(out); print('wrote', out, S.size)


def grid(ids, out=None, cols=5):
    out = out or f'{REV}/{FILE}_grid.mp4'; w, h = 384, 216; rows = (len(ids) + cols - 1) // cols
    n = max(load(p + t)[0]['frames'] for p in ids for t in 'AB'); tmp = f'{REV}/frames_grid'; os.makedirs(tmp, exist_ok=True)
    for f in range(n + 20):
        G = Image.new('RGB', (w * cols, 2 * h * rows), (20, 20, 24))
        for k, p in enumerate(ids):
            x, y = (k % cols) * w, (k // cols) * 2 * h
            for t, take in enumerate('AB'): G.paste(cell(p + take, 'fpp', f, (w, h), f'{p}{take} {NAME(p)}'), (x, y + t * h))
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 20), '-vf', 'format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-crf', '23', out]); print('wrote', out)


def video(pt, out):
    s, g = load(pt); N = s['frames']; w, h = 640, 360; tmp = f'{REV}/frames_{pt}'; os.makedirs(tmp, exist_ok=True)
    for f in range(N + 15):
        G = Image.new('RGB', (2 * w, h)); nm = f'{pt} {NAME(pt[:-1])}'
        G.paste(cell(pt, 'fpp', f, (w, h), nm), (0, 0)); G.paste(cell(pt, 'out', f, (w, h), nm + ' (outside)'), (w, 0)); G.save(f'{tmp}/v_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/v_%03d.png', '-frames:v', str(N + 15), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '20', out])


def strip(pt, out):
    s, g = load(pt); L = g['layout']; fr = [0] + [f for _, f in key(pt)] + [x for x in ((L['hide_start'] or 0) - 1, (L['hide_end'] or 0) + 1) if x > 0] + [s['frames'] - 1]; fr = sorted(set(fr))
    w, h = 480, 270; cols = 4; S = Image.new('RGB', (w * cols, h * ((len(fr) + cols - 1) // cols)), (20, 20, 24))
    for k, f in enumerate(fr): S.paste(cell(pt, 'fpp', f, (w, h), f'{pt} frame {f}'), ((k % cols) * w, (k // cols) * h))
    S.save(out)


STYLE_FROM = common.mp('C:/Modding/anim-work/long-partner/review/long-topmag.html')


R2_OPEN = {'BR17A': 30, 'BR18A': 30, 'BR20A': 23, 'BR17B': 36, 'BR18B': 37, 'BR20B': 30}     # production layout (clips/layout_break.md, Palica / Satara)
GUN_T = {'A': (('Palica', 0.65), ('Palica empty', 0.75), ('Igla', 0.9)), 'B': (('Satara', 0.9), ('Testera', 0.85))}


def fit_cell(frames, take):
    """Required speed-up of the opening per gun sharing the take: base, Body 10 (x1.3), Body 20 (x1.6); over 1.15 falls back."""
    out = []
    for name, T in GUN_T[take]:
        r = [frames / 30.0 / (0.75 * T / b) for b in (1.0, 1.3, 1.6)]
        out.append(f"{name} {r[0]:.2f}{'' if r[0] <= 1.15 else '!'} / {r[1]:.2f} / {r[2]:.2f}")
    return '; '.join(out)


def page(ids):
    SC = json.load(open(renv.OUT + '/scores.json')); W = SC['weights']; os.makedirs(REV, exist_ok=True); rows = []
    for p in ids:
        sc = SC['drafts'][p]; takes = []
        for take in 'AB':
            pt = p + take; s, g = load(pt); m = g['motion']; L = g['layout']; ph = g['phys']; G = g['inertia']['gun']; sp = ph['spent'][0] if ph['spent'] else {}
            if not os.path.exists(f'{REV}/{pt}.mp4') or os.path.getmtime(f'{REV}/{pt}.mp4') < os.path.getmtime(s['out']): video(pt, f'{REV}/{pt}.mp4')
            strip(pt, f'{REV}/{pt}_strip.png')
            takes.append({'id': pt, 'gun': TAKE_NAME[take], 'm': [f"{m['peak_speed']}", f"{m['peak_at']}", f"{m['stop']}", f"{g['eye_cm'][0]} cm", f"{g['cover_peak'][0]}%",
                          f"f{L['hide_start']}-{L['hide_end']}", f"{g['wrist'][0]:.0f} deg", f"{g['reach'][0]:.3f}", f"{g['guns_gap_cm'][0]:.0f} cm", f"{max(g['end_cm'], g['start_cm']):.3f} cm",
                          f"{ph['open_swing_deg_f']} / {ph['barrel_at_trip_deg_f']}", f"{ph['close_swing_deg_f']} / {ph['latch_w_deg_f']} (need {ph['latch_need_deg_f']})", ph['latch'] + (f" f{ph['shut_f']}" if ph['shut_f'] else ''),
                          f"{sp.get('exit_m_s')} m/s, f{sp.get('land')}", f"{G['overshoot_cm_max']} cm / {G['overshoot_deg_max']} deg", f"{G['settle_f_max']} f", f"{G['rot_lag_f']} f", f"{G['muzzle_trail_deg']} deg",
                          f"{g['open_gun_f']} f (round 2: {R2_OPEN[pt]})", fit_cell(g['open_gun_f'], take)], 'fails': g['fails'], 'notes': g.get('notes', [])})
        rows.append({'id': p, 'name': NAME(p), 's': sc['s'], 'good': sc['good'], 'bad': sc['bad'], 'takes': takes, 'concept': html.escape(break2.DOC[p]),
                     'open': html.escape(break2.OPEN[p]), 'close': html.escape(break2.CLOSE[p]), 'load': html.escape(break2.LOADM[p]), 'src': break2.SOURCE[p], 'why': html.escape(sc.get('mechanism', ''))})
    tot = lambda r: sum(a * b for a, b in zip(r['s'], W)); top = sorted(rows, key=lambda r: -tot(r))[:3]
    css = open(STYLE_FROM, encoding='utf-8').read(); css = css[css.index('<style>'):css.index('</style>') + 8]
    css = css.replace('</style>', '.takes{display:grid;gap:14px}.take h3{margin:6px 0 4px;font-size:15px}.player video{max-width:100%}.why{border-left:3px solid currentColor;padding-left:10px}.src{font-size:13px}</style>')
    MA = bp.summary('palica'); MB = bp.summary('satara'); BA, BB = break2.BUDGET['A'], break2.BUDGET['B']
    intro = f'''<p><b>Round 3.</b> The owner's picks BR17, BR18 and BR20 re-timed so their visible opening (clip start until the gun, hand and forearm are out of view) fits the game's reload time. The script plays a pick only if that opening fits 0.75 x the reload time at no more than 1.15x speed (GorillaAkimbo.reds OwnSpeed, FallbackAbove; WIRING-NOTES.md): at most 16 frames on the Palica (0.65 s), 22 on the Testera (0.85 s), 23 on the Satara and Igla (0.9 s). Same moves and closes as round 2, faster (lever on f2 / f3, shorter holds, the break 2 to 3 frames earlier), and right after the break the gun is carried out to the right, out of view: a sideways move pushes along the hinge axis, so it neither opens nor shuts the barrels. The thumb holds the lever until then, so the fast moves cannot latch the barrels early. Round 2 (approved) beside each take. Hulls: the game does not draw them, so the hidden window starts when the gun leaves the view; hulls still in the air then are noted.</p>
    <p>One-handed reloads of a double-barrel break action while the other hand keeps its own gun, each built on a captured game reference (video and time stamps under each draft; stills in <code>refs/</code>) and on the mechanism research in <code>RESEARCH.md</code>. Take <b>A</b> on the Palica (light, short barrels), take <b>B</b> on the Satara (heavy, long barrels); right hand, male V, empty reload (both barrels), starting and ending in the dual-wield idle. Igla and Testera are not drafted (no shell joints or shell mesh; the Testera has only an empty reload).</p>
    <p class="muted"><b>Barrels.</b> A rigid body on the game's own hinge pin. They never move by themselves: the only causes are the gun's motion (inertia about the pin from its linear and angular acceleration), gravity, the springs and a body contact. Opening needs the top lever thumbed and a swing that carries the barrels through the cocking of both hammers (Palica {MA['cock_torque_Nm']} N m over {MA['cock_deg']:.0f} deg, {MA['gravity_torque_Nm']} N m of gravity at most; Satara {MB['cock_torque_Nm']} over {MB['cock_deg']:.0f} deg, gravity {MB['gravity_torque_Nm']}), so gravity alone never opens them from the idle. At {MA['trip_deg']} / {MB['trip_deg']} deg the ejectors trip and throw both hulls at {MA['v_eject_m_s']} m/s on top of the barrels' own speed. Closing re-compresses the ejector springs over the last {MA['ej_deg']:.0f} / {MB['ej_deg']:.0f} deg, and the bolt springs into the bite only if the barrels arrive with at least <b>{MA['latch_w_deg_f']} deg/f</b> (Palica) / <b>{MB['latch_w_deg_f']} deg/f</b> (Satara) (latch energy {MA['E_latch_J']} / {MB['E_latch_J']} J); slower, the bolt cam throws them back. Spring and friction numbers are estimates (unverified, see RESEARCH.md).</p>
    <p class="muted"><b>Gun.</b> The FRONT round 4 inertia model: the timeline is the hand's target, the gun follows as a spring-damper mass (overshoot, rebound, rotation lag, muzzle trail); the barrels hitting the open stop and the bolt catching kick the gun back (their angular momentum over the gun-and-hand inertia), three passes. <b>Timing budget</b> (30 fps): take A {BA['frames']} frames (the game's Palica reload length): lever f{BA['lever']}, open by about f{BA['open_by']}, seat f{BA['seat']}, shut about f{BA['shut']}; take B {BB['frames']} frames: lever f{BB['lever']}, open by f{BB['open_by']}, seat f{BB['seat']}, shut about f{BB['shut']} (the game's Satara shut frame). The draft decides the exact break and latch frames: they come out of the simulation.</p>'''
    pg = f'''<title>Break-Open Reloads, Round 3</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
{css}
<div class="wrap">
  <section class="intro">
    <h1>Break-Open Shotgun Reloads, Round 3: short openings</h1>
    {intro}
    <p><b>My top three:</b> {', '.join(f'<a href="#{r["id"]}">{r["id"]} {html.escape(r["name"])}</a> ({tot(r):.2f})' for r in top)}.</p>
  </section>
  <section class="intro">
    <h2>Scores</h2>
    <div class="legend muted">
      <span><b>Fit</b> (30%): reads as the referenced technique and the action breaks and shuts because of the swing. <b>Clarity</b> (25%): reads in first person, nothing in the face. <b>Weight</b> (20%): inertia reads in the gun, barrels and shells. <b>Style</b> (15%): different from the other drafts and from round 1. <b>Cost</b> (10%): risk in game.</span>
      <span><b>Peak</b> grip cm/f, <b>At</b>, <b>Stop</b>, <b>Eye</b> (rule 20 cm), <b>Cover</b> (18%), <b>Hidden</b>, <b>Wrist</b> (113), <b>Reach</b> (0.985), <b>Guns</b> gap, <b>End</b>. <b>Break</b>: the gun's peak angular speed from the lever to the trip / the barrels' speed at the trip (deg/f). <b>Close</b>: the gun's peak angular speed in the 6 frames before the latch / the barrels' speed at the breech (the bolt needs the number in brackets). <b>Latch</b>: latched, or bounced off the bolt. <b>Shells</b>: ejection speed, landing frame. Inertia: <b>Over</b>, <b>Settle</b>, <b>Rot lag</b>, <b>Trail</b>.</span>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Draft</th><th>Open</th><th>Close</th><th class="num">Fit</th><th class="num">Clarity</th><th class="num">Weight</th><th class="num">Style</th><th class="num">Cost</th><th class="num">Score</th><th>Take</th><th class="num">Peak</th><th class="num">At</th><th class="num">Stop</th><th class="num">Eye</th><th class="num">Cover</th><th class="num">Hidden</th><th class="num">Wrist</th><th class="num">Reach</th><th class="num">Guns</th><th class="num">End</th><th class="num">Break</th><th class="num">Close</th><th>Latch</th><th class="num">Shells</th><th class="num">Over</th><th class="num">Settle</th><th class="num">Rot lag</th><th class="num">Trail</th><th class="num">Opening</th><th>Speed-up base / Body 10 / Body 20 (! over 1.15)</th><th>Gate failures</th></tr></thead>
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
    ${{id.endsWith("_r2") ? "" : `<details><summary>Key frames</summary><img class="strip" src="${{id}}_strip.png" alt="Labelled first-person key frames of ${{id}}" loading="lazy"></details>`}}</div></div>`;
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
    tr.innerHTML = (j === 0 ? `<td class="mono" rowspan="2">${{i + 1}}</td><td rowspan="2"><a href="#${{v.id}}">${{v.id}} ${{v.name}}</a></td><td rowspan="2">${{v.open}}</td><td rowspan="2">${{v.close}}</td>` +
      v.s.map(x => `<td class="num" rowspan="2">${{x}}</td>`).join("") + `<td class="num total ${{cls(v.t)}}" rowspan="2">${{v.t.toFixed(2)}}</td>` : "") +
      `<td class="mono">${{k.id}}</td>` + k.m.map(x => `<td class="num">${{x}}</td>`).join("") + `<td>${{k.fails.length ? k.fails.join("; ") : "none"}}${{k.notes.length ? `<br><span class="muted">note: ${{k.notes.join("; ")}}</span>` : ""}}</td>`;
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
      <div class="takes">${{v.takes.map(k => player(k.id, k.gun + " (round 3)") + player(k.id + "_r2", k.gun + " (round 2, approved)")).join("")}}</div>
      <div class="notes">
        <p class="src"><b>Reference:</b> ${{v.src}}</p>
        ${{v.why ? `<p class="why"><b>Mechanism:</b> ${{v.why}}</p>` : ""}}
        <p><b>Open:</b> ${{v.open}}. <b>Load:</b> ${{v.load}}. <b>Close:</b> ${{v.close}}.</p>
        <p>${{v.concept}}</p>
        <div class="bars">${{v.s.map((x, k) => `<span>${{labels[k]}}</span><span class="bar"><i style="width:${{x * 10}}%"></i></span><span class="mono">${{x}}</span>`).join("")}}</div>
        <ul>${{v.good.map(g => `<li>${{g}}</li>`).join("")}}</ul>
        <ul class="muted">${{v.bad.map(b => `<li>${{b}}</li>`).join("")}}</ul>
        ${{v.takes.map(k => `<p class="mono muted">${{k.id}}: swing at break ${{k.m[10]}} deg/f (gun / barrels at the trip), swing at close ${{k.m[11]}} deg/f (gun / barrels at the breech), latch ${{k.m[12]}}, shells ${{k.m[13]}}; peak ${{k.m[0]}} cm/f at ${{k.m[1]}}, stop ${{k.m[2]}}, eye ${{k.m[3]}}, cover ${{k.m[4]}}, hidden ${{k.m[5]}}, wrist ${{k.m[6]}}, reach ${{k.m[7]}}, guns ${{k.m[8]}}, end ${{k.m[9]}}; overshoot ${{k.m[14]}}, settle ${{k.m[15]}}, rotation lag ${{k.m[16]}}, muzzle trail ${{k.m[17]}}; opening ${{k.m[18]}}; speed-up ${{k.m[19]}}${{k.fails.length ? "; FAILS: " + k.fails.join("; ") : ""}}${{k.notes.length ? "; note: " + k.notes.join("; ") : ""}}</p>`).join("")}}
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
    ids = argv[1].split(',') if len(argv) > 1 and not argv[1].startswith('--') else list(break2.PICKS)
    if cmd == 'frames':
        for p in ids:
            for t in takes: render(p + t); print('rendered', p + t, flush=True)
    elif cmd == 'dense': dense(argv[1], every)
    elif cmd == 'sheet': sheet(ids)
    elif cmd == 'grid': grid(ids)
    elif cmd == 'page': page(ids)
    else: raise SystemExit(__doc__)
