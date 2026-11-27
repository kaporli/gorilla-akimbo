"""Contact sheet per gun of all its production clips in first person, for FRONT (frontprod.py) and TUBE (tubeprod.py).
One Blender session per gun renders the frames the sheet shows (scene.py batch mode); guns one after the other.

usage: prodsheet.py <frontprod|tubeprod> render [gun] | sheet [gun]
Output: <OUT>/sheets/<gun>_production_contact_sheet.png; frames in clips/<body>/frames/<stem>/fpp_###.png
"""
import os, sys, json, subprocess, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
from rrender import font, SCENE, CAM
from PIL import Image, ImageDraw

YEL = (255, 220, 0); RED = (255, 120, 110)
FAM = importlib.import_module(sys.argv[1]); TUBE = sys.argv[1] in ('tubeprod', 'tube2'); BREAK = sys.argv[1] == 'breakprod'
SHEETS = renv.OUT + '/sheets'


def rows_of(gid):
    out = []
    for p in (FAM.plan_list([gid]) if BREAK else FAM.plan([gid])):
        if BREAK: g, pick, clip, side, body = p; base = f'{FAM.OUT}/{body}/{FAM.stem(g, side, pick, clip)}'
        elif TUBE: g, pick, side, body = p; clip = FAM.CLIP; base = f'{FAM.OUT}/{body}/{FAM.stem(g, side, pick)}'
        else: g, pick, clip, side, body = p; base = f'{FAM.OUT}/{body}/{FAM.stem(g, side, pick, clip)}'
        out.append((base, pick, clip, side, body))
    order = {p: i for i, p in enumerate(FAM.SLOTS)}
    return sorted(out, key=lambda r: (order[r[1]], r[2] != 'reload', r[4], r[3] != 'right'))


def cols(spec, gate):
    mk = spec['_marks']; N = spec['frames']
    if BREAK:
        ph = gate['phys']; L = gate['layout']; tr = int(ph['trip_f'] or 8); sh = int(ph['shut_f'] or N - 10)
        return [('start', 0), ('lever', ph['lever_f']), ('hulls out', min(tr + 2, N - 1)), ('hidden: loading', (L['hide_start'] or 30) + 3), ('shut', min(sh + 1, N - 1)), ('last frame', N - 1)]
    if TUBE:
        pc = spec['_pump_cm']; op = next((f for f in range(N) if pc[f] > 4), 8); L = gate['layout']; home = gate['pump']['home_frame'] or mk.get('hit', 57)
        return [('start', 0), ('pump opens', op), ('first shell', int(spec.get('_first_load') or 20)), ('hidden: loading', (L['hide_start'] or 30) + 3), ('pump shut', min(home, N - 1)), ('last frame', N - 1)]
    B = spec['_timing']['budget']; r = spec['_mag']['release']
    last = ('rack', mk['hit']) if 'hit' in mk else ('ready', mk.get('ready', B['home'] - 3))
    return [('start', 0), ('technique', max(r - 3, 1)), ('magazine out', r + 2), ('fresh magazine', B['seat'] - 2), last, ('last frame', N - 1)]


def fdir(base): d = os.path.dirname(base) + '/frames/' + os.path.basename(base); os.makedirs(d, exist_ok=True); return d


def render(gid, res=(640, 360)):
    cfgs = []
    for base, pk, clip, side, body in rows_of(gid):
        spec = json.load(open(base + '.json')); gate = json.load(open(base + '_gate.json')); d = fdir(base); fr = sorted(set(f for _, f in cols(spec, gate)))
        if all(os.path.exists(f'{d}/fpp_{f:03d}.png') and os.path.getmtime(f'{d}/fpp_{f:03d}.png') > os.path.getmtime(base + '.glb') for f in fr): continue
        s = spec['_side'].lower(); o = 'left' if s == 'right' else 'right'; parts = common.gun(gid).get('parts')      # Carnage: none listed (scene.py's default parts)
        cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': fr, 'out': f'{d}/fpp', 'body': body, 'view': 'fpp', 'res': list(res),
               'right_gun': gid, 'left_gun': gid, 'right_parts': parts, 'left_parts': parts, f'{s}_mag_clip': spec['_gun_clip'], f'{o}_mag_clip': None,
               'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40], f'{s}_parts_anim': True, f'{s}_mag_track': spec['_track'], f'{s}_parts_frames': spec['_part_frames']}
        if TUBE:
            import tube1; FAM.use_gun(gid); cfg['objects'] = tube1.objects(spec); cfg['objects_side'] = spec['_side']
        if BREAK:
            J = json.load(open(spec['_objects'])); mesh = common.find('weapon_meshes', FAM.bp.MESH[gid] + '__mag_std_01.glb'); col = {'spent': (0.85, 0.75, 0.2, 1), 'fresh': (1, 0.35, 0.1, 1), 'live': (0.3, 0.8, 0.3, 1)}
            cfg['objects'] = [{'mesh': mesh, 'joints': J['joints'][n], 'color': col.get(n, (1, 0.35, 0.1, 1))} for n in J['names']]; cfg['objects_side'] = spec['_side']
            cfg['prims'] = json.load(open(spec['_prims'])) if os.path.exists(spec.get('_prims', '')) else []
        cfg.update(CAM); cfgs.append(cfg)
    if not cfgs: print(gid, 'frames up to date'); return
    c = f'{renv.OUT}/work/render_{gid}.json'; json.dump(cfgs, open(c, 'w'))
    r = subprocess.run([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', c], capture_output=True, text=True, errors='replace')
    n = r.stdout.count('DONE ') ; open(f'{renv.OUT}/work/render_{gid}.log', 'w').write(r.stdout[-20000:] + r.stderr[-5000:])
    if 'ALLDONE' not in r.stdout or n != len(cfgs): raise SystemExit(f'{gid}: scene.py rendered {n} of {len(cfgs)}:\n' + '\n'.join((r.stdout + r.stderr).splitlines()[-15:]))
    print(gid, 'rendered', n, 'clips', flush=True)


def sheet(gid):
    rows = rows_of(gid); w, h = 352, 198; crop = (0.25, 1.0); nw = 470; top = 70; rowh = h + 6; nc = 6
    S = Image.new('RGB', (nc * w + nw, top + rowh * len(rows)), (20, 20, 24)); dr = ImageDraw.Draw(S); name = common.gun(gid)['name']
    npass = sum(1 for r in rows if not json.load(open(r[0] + '_gate.json'))['fails'])
    what = (f"{len(rows)} = picks x clips x bodies x hands; shells as in NOTES.md") if BREAK else '3 picks x male / female V x right / left hand; one clip serves reload and empty reload' if TUBE else '3 picks x reload / empty reload x male / female V x right / left hand'
    dr.text((10, 6), f'{name}: production one-handed reloads, {len(rows)} clips ({what}), first person. Gate: {npass} of {len(rows)} pass.', fill=(255, 255, 255), font=font(19))
    sub = ('Columns: start, lever, hulls out (trip + 2), hidden (loading), shut + 1, last frame (= the idle).' if BREAK else 'Columns: start, pump opens, first shell, hidden (loading), pump shut, last frame (= the idle).' if TUBE else
           'Columns: start, technique (3 frames before the release), magazine out, fresh magazine, rack (or ready: reload without a cocking piece), last frame (= the idle).')
    dr.text((10, 36), sub, fill=(180, 185, 195), font=font(15, False))
    for k, (base, pk, clip, side, body) in enumerate(rows):
        spec = json.load(open(base + '.json')); g = json.load(open(base + '_gate.json')); d = fdir(base); y = top + k * rowh
        for j, (lab, f) in enumerate(cols(spec, g)):
            im = Image.open(f'{d}/fpp_{f:03d}.png').convert('RGB'); im = im.crop((0, int(im.size[1] * crop[0]), im.size[0], int(im.size[1] * crop[1]))).resize((w, h))
            di = ImageDraw.Draw(im); di.rectangle((0, 0, w, 20), fill=(0, 0, 0)); di.text((5, 2), f'{lab}  f{f}', fill=YEL, font=font(13)); S.paste(im, (j * w, y))
        L = g['layout']; m = g['motion']; x = nc * w + 10
        dr.text((x, y + 4), f"{pk}{spec['_take']} {spec['_name'].split(',')[0]}", fill=YEL, font=font(17))
        dr.text((x, y + 28), f"{('reload and empty reload' if TUBE or (BREAK and gid == 'igla') else clip)}, {'male' if body == 'pma' else 'female'} V, {side} hand", fill=(255, 255, 255), font=font(15, False))
        lines = [f"{spec['frames']} frames ({L['keys']} keys), hit {L['handle']}", f"hidden f{L['hide_start']}-{L['hide_end']} ({g['hidden_frames']} f)",
                 f"eye {g['eye_cm'][0]} cm, cover {g['cover_peak'][0]} %, wrist in view {g['wrist_view']}", f"peak {m['peak_speed']} cm/f, stop {m['stop']}"]
        for i, tx in enumerate(lines): dr.text((x, y + 52 + i * 21), tx, fill=(225, 225, 225), font=font(14, False))
        res = 'gate: pass' if not g['fails'] else 'gate: ' + '; '.join(g['fails'])
        dr.text((x, y + 52 + 4 * 21 + 8), res[:60], fill=(140, 230, 140) if not g['fails'] else RED, font=font(14))
    os.makedirs(SHEETS, exist_ok=True); out = f'{SHEETS}/{gid}_production_contact_sheet.png'; S.save(out); print('wrote', out, S.size)


if __name__ == '__main__':
    argv = sys.argv[2:]; cmd = argv[0]; guns = [argv[1]] if len(argv) > 1 else (list(FAM.TAKE) if BREAK else FAM.GUNS if TUBE else list(FAM.GUNS))
    for gid in guns: (render if cmd == 'render' else sheet)(gid)
