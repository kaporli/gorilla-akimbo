"""Contact sheet per gun of all its production clips in first person (smgprod.py output).
Renders only the frames the sheet shows (scene.py, one Blender at a time: memory), then composes one PNG per gun.

usage: smgsheet.py render [gun]     frames of every clip (skips clips whose frames are newer than the clip)
       smgsheet.py sheet [gun]      <OUT>/sheets/<gun>_production_contact_sheet.png
Columns: start (f0), technique (3 frames before the release), magazine out (release + 2), fresh magazine (seat - 2),
rack (empty reload: the hit) or ready (reload: the settle), last frame; numbers and the gate result beside.
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import smgprod
from rrender import font, SCENE, CAM
from PIL import Image, ImageDraw

YEL = (255, 220, 0); RED = (255, 120, 110)
SHEETS = renv.OUT + '/sheets'


def clips_of(gid):
    out = []
    for fam, pick, clip, side, body in smgprod.plan():
        g, take = smgprod.FAMILIES[fam][0], smgprod.FAMILIES[fam][1]
        if g == gid: out.append((f'{smgprod.OUT}/{body}/{smgprod.stem(g, side, pick, take, clip)}', pick + take, clip, side, body))
    order = {p: i for i, p in enumerate(smgprod.SLOTS[gid])}
    return sorted(out, key=lambda r: (order[r[1][:-1]], r[2] != 'reload', r[4], r[3] != 'right'))


def cols(spec, gate):
    B = spec['_timing']['beats']; mk = spec['_marks']; N = spec['frames']
    last = ('rack', mk['hit']) if 'hit' in mk else ('ready', mk.get('ready', B['held'] + 3))
    return [('start', 0), ('technique', B['rel'] - 3), ('magazine out', B['rel'] + 2), ('fresh magazine', B['seat'] - 2), last, ('last frame', N - 1)]


def fdir(base): d = os.path.dirname(base) + '/frames/' + os.path.basename(base); os.makedirs(d, exist_ok=True); return d


def render(gid, res=(640, 360)):
    for base, pk, clip, side, body in clips_of(gid):
        spec = json.load(open(base + '.json')); gate = json.load(open(base + '_gate.json')); d = fdir(base); fr = sorted(set(f for _, f in cols(spec, gate)))
        if all(os.path.exists(f'{d}/fpp_{f:03d}.png') and os.path.getmtime(f'{d}/fpp_{f:03d}.png') > os.path.getmtime(base + '.glb') for f in fr): continue
        s = spec['_side'].lower(); o = 'left' if s == 'right' else 'right'; parts = common.gun(gid)['parts']
        cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': fr, 'out': f'{d}/fpp', 'body': body, 'view': 'fpp', 'res': list(res),
               'right_gun': gid, 'left_gun': gid, 'right_parts': parts, 'left_parts': parts, f'{s}_mag_clip': spec['_gun_clip'], f'{o}_mag_clip': None,
               'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40], f'{s}_parts_anim': True, f'{s}_mag_track': spec['_track'], f'{s}_parts_map': spec['_gun_map']}
        cfg.update(CAM); c = f'{d}/cfg_fpp.json'; json.dump(cfg, open(c, 'w'))
        r = subprocess.run([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', c], capture_output=True, text=True, errors='replace')
        if 'DONE' not in r.stdout: raise SystemExit(f'scene.py failed for {c}:\n' + '\n'.join((r.stdout + r.stderr).splitlines()[-15:]))
        print('rendered', os.path.basename(base), fr, flush=True)


def sheet(gid):
    rows = clips_of(gid); w, h = 352, 198; crop = (0.25, 1.0); nw = 470; top = 70; rowh = h + 6; nc = 6
    S = Image.new('RGB', (nc * w + nw, top + rowh * len(rows)), (20, 20, 24)); dr = ImageDraw.Draw(S); name = common.gun(gid)['name']
    npass = sum(1 for r in rows if not json.load(open(r[0] + '_gate.json'))['fails'])
    dr.text((10, 6), f'{name}: production one-handed reloads, {len(rows)} clips (3 picks x reload / empty reload x male / female V x right / left hand), first person. Gate: {npass} of {len(rows)} pass.', fill=(255, 255, 255), font=font(19))
    dr.text((10, 36), 'Columns: start, technique (3 frames before the release), magazine out, fresh magazine, rack (empty reload) or ready (reload: no rack, a round is chambered), last frame (= the idle).', fill=(180, 185, 195), font=font(15, False))
    for k, (base, pk, clip, side, body) in enumerate(rows):
        spec = json.load(open(base + '.json')); g = json.load(open(base + '_gate.json')); d = fdir(base); y = top + k * rowh
        for j, (lab, f) in enumerate(cols(spec, g)):
            im = Image.open(f'{d}/fpp_{f:03d}.png').convert('RGB'); im = im.crop((0, int(im.size[1] * crop[0]), im.size[0], int(im.size[1] * crop[1]))).resize((w, h))
            di = ImageDraw.Draw(im); di.rectangle((0, 0, w, 20), fill=(0, 0, 0)); di.text((5, 2), f'{lab}  f{f}', fill=YEL, font=font(13)); S.paste(im, (j * w, y))
        L = g['layout']; m = g['motion']; x = nc * w + 10
        dr.text((x, y + 4), f"{pk} {spec['_name'].split(',')[0]}", fill=YEL, font=font(17))
        dr.text((x, y + 28), f"{clip}, {'male' if body == 'pma' else 'female'} V, {side} hand", fill=(255, 255, 255), font=font(15, False))
        lines = [f"{spec['frames']} frames ({L['keys']} keys), out f{L['mag_out']}, seated f{L['seated']}, hit {L['handle']}",
                 f"hidden f{L['hide_start']}-{L['hide_end']} ({g['hidden_frames']} f)", f"eye {g['eye_cm'][0]} cm, cover {g['cover_peak'][0]} %, wrist in view {g['wrist_view']}",
                 f"peak {m['peak_speed']} cm/f, stop {m['stop']}; magazine in view {g['mag_view_frames']} f",
                 'in-hand gun motion: needs in-game check' if spec.get('_in_hand') else '']
        for i, tx in enumerate(t for t in lines if t): dr.text((x, y + 52 + i * 21), tx, fill=(225, 225, 225) if 'in-game' not in tx else (255, 190, 90), font=font(14, False))
        res = 'gate: pass' if not g['fails'] else 'gate: ' + '; '.join(g['fails'])
        dr.text((x, y + 52 + 5 * 21 + 4), res[:60], fill=(140, 230, 140) if not g['fails'] else RED, font=font(14))
    os.makedirs(SHEETS, exist_ok=True); out = f'{SHEETS}/{gid}_production_contact_sheet.png'; S.save(out); print('wrote', out, S.size)


if __name__ == '__main__':
    argv = sys.argv[1:]; cmd = argv[0]; guns = [argv[1]] if len(argv) > 1 else list(smgprod.SLOTS)
    for gid in guns: (render if cmd == 'render' else sheet)(gid)
