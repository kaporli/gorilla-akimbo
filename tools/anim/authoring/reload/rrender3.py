"""Previews of the production rifle reload clips (either hand, either body).

usage:
  rrender3.py frames <spec.json> [--res 640,360]      renders first person and outside frames next to the spec
  rrender3.py gun <gun id> <out mp4> [--body pma]     per gun: right reload | right empty reload | left reload, per
                                                      pick a band (first person over outside), frame numbers burned in
  rrender3.py grid <category> <out mp4> [--body pma]  every gun and pick of a category, right hand empty reload
  rrender3.py stills <out png> [--body pma]           every clip at its release, hide_start, hide_end and return
The reloading gun plays its own magazine track and its moving parts (handle, bolt, latch). The outside camera is on
the reloading hand's side.
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, manifest
import rrender, prod
from rrender import font, ffmpeg, parts, SCENE, CAM
from PIL import Image, ImageDraw

OUTCAM = {'Right': {'cam_loc': [1.4, 1.8, 1.8], 'cam_tgt': [0.05, 0.1, 1.22], 'angle': 52}, 'Left': {'cam_loc': [-1.4, 1.8, 1.8], 'cam_tgt': [-0.05, 0.1, 1.22], 'angle': 52}}


def fdir(spec_path):
    d = os.path.dirname(spec_path) + '/frames/' + os.path.splitext(os.path.basename(spec_path))[0]; os.makedirs(d, exist_ok=True)
    return d


def render(spec_path, res=(640, 360)):
    spec = json.load(open(spec_path)); d = fdir(spec_path); N = spec['frames']; s = spec['_side'].lower(); o = 'left' if s == 'right' else 'right'
    if os.path.exists(f'{d}/out_{N - 1:03d}.png') and os.path.exists(f'{d}/fpp_{N - 1:03d}.png') and os.path.getmtime(f'{d}/fpp_{N - 1:03d}.png') > os.path.getmtime(spec['out']): return d
    procs = []
    for v in ('fpp', 'out'):
        cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': list(range(N)), 'out': f'{d}/{v}', 'body': spec['_body'], 'view': v, 'res': list(res),
               'right_gun': spec['_gun'], 'left_gun': spec['_gun'], 'right_parts': parts(spec['_gun']), 'left_parts': parts(spec['_gun']),
               f'{s}_mag_clip': spec['_gun_clip'], f'{o}_mag_clip': None, 'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40],
               f'{s}_parts_anim': True, f'{s}_mag_track': spec['_track']}
        cfg.update(CAM if v == 'fpp' else OUTCAM[spec['_side']])
        p = f'{d}/cfg_{v}.json'; json.dump(cfg, open(p, 'w'))
        procs.append((p, subprocess.Popen([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', p], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')))
    for p, pr in procs:
        log = pr.communicate()[0]
        if 'DONE' not in log: raise SystemExit(f'scene.py failed for {p}:\n' + '\n'.join(log.splitlines()[-15:]))
    return d


def phase(spec, gate, f):
    L = gate['layout']; mg = spec['_mag']; hit = L['handle']; lat = spec['_marks'].get('latch')
    if lat is not None and lat - 3 <= f <= lat + 3: return 'latch opens'
    if f < mg['release']: return 'start'
    if f < mg['release'] + 5: return 'magazine hooked off' if mg.get('mode') == 'hook' else 'magazine thrown'
    if L['hide_start'] is not None and L['hide_start'] <= f <= L['hide_end']: return 'HIDDEN (may be fast-forwarded)' if f != L['seated'] else 'HIDDEN: seated'
    if hit is not None and hit - 1 <= f <= hit + 4: return 'handle / bolt / latch'
    return 'magazine falls' if f < (L['hide_start'] or 0) else 'up'


def cell(spec_path, v, f, size, title):
    spec = json.load(open(spec_path)); gate = json.load(open(spec_path[:-5] + '_gate.json')); d = fdir(spec_path); ff = min(f, spec['frames'] - 1)
    im = Image.open(f'{d}/{v}_{ff:03d}.png').convert('RGB').resize(size); dr = ImageDraw.Draw(im); W = size[0]
    dr.rectangle((0, 0, W, 22), fill=(0, 0, 0)); dr.text((6, 3), title, fill=(255, 220, 0), font=font(14))
    sub = f'f{ff}/{spec["frames"] - 1}  {phase(spec, gate, ff)}'; w = dr.textlength(sub, font=font(13, False)); dr.text((W - w - 6, 4), sub, fill=(255, 255, 255), font=font(13, False))
    return im


def spec_of(gid, pick, clip, side, body):
    g = common.gun(gid); take = prod.WEIGHT_TAKE[g['reload']['weight']]; d = manifest.path('rreload_clips')
    p = f'{d}/{body}/{prod.stem(gid, pick, take, clip, side)}.json'
    return p if os.path.exists(p) else f'{d}/{body}/{prod.stem(gid, pick, take, "reload", side)}.json'


def movie(cols, rows_of, out, size=(480, 270)):
    """cols: [(title, spec path)] per band; rows_of: list of bands; each band = first person row over outside row."""
    w, h = size; n = max(json.load(open(p))['frames'] for band in rows_of for _, p in band); nc = max(len(b) for b in rows_of)
    tmp = os.path.dirname(out) + '/frames_' + os.path.splitext(os.path.basename(out))[0]; os.makedirs(tmp, exist_ok=True)
    for f in range(n + 20):
        G = Image.new('RGB', (w * nc, 2 * h * len(rows_of)), (20, 20, 24))
        for r, band in enumerate(rows_of):
            for k, (title, p) in enumerate(band):
                G.paste(cell(p, 'fpp', f, size, title), (k * w, r * 2 * h)); G.paste(cell(p, 'out', f, size, title + '  outside'), (k * w, r * 2 * h + h))
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 20), '-vf', 'format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-crf', '22', out]); print('wrote', out)


def gun_specs(gid, body):
    g = common.gun(gid); out = []
    for pick in g['reload']['picks']:
        band = [(f'{g["name"]} {pick} right, reload', spec_of(gid, pick, 'reload', 'right', body))]
        if len(prod.clips_of(gid)) > 1: band.append((f'{g["name"]} {pick} right, empty reload', spec_of(gid, pick, 'empty_reload', 'right', body)))
        band.append((f'{g["name"]} {pick} left, reload', spec_of(gid, pick, 'reload', 'left', body))); out.append(band)
    return out


def stills(out, body='pma'):
    w, h = 384, 216; rows = []
    for gid, pick, take, clip, side, b in prod.plan(bodies=[body]):
        p = spec_of(gid, pick, clip, side, body)
        if not os.path.exists(fdir(p) + '/fpp_000.png'): continue
        L = json.load(open(p[:-5] + '_gate.json'))['layout']; rel = L['mag_out']
        rows.append((f'{gid} {pick}{take} {clip} {side}', p, [('fpp', rel + 2), ('out', rel + 3), ('fpp', (L['hide_start'] or rel) - 1), ('fpp', L['hide_start'] or rel), ('out', L['seated']), ('fpp', (L['hide_end'] or rel) + 1), ('fpp', (L['hide_end'] or rel) + 6)]))
    S = Image.new('RGB', (w * 7, 30 + h * len(rows)), (20, 20, 24)); dr = ImageDraw.Draw(S)
    dr.text((8, 6), 'Per clip: release +2 (first person), release +3 (outside), last frame before hide_start, hide_start, seated (outside), first frame after hide_end, 5 frames later', fill=(255, 255, 255), font=font(15))
    for r, (name, p, cells) in enumerate(rows):
        for k, (v, f) in enumerate(cells): S.paste(cell(p, v, f, (w, h), name if k == 0 else ''), (k * w, 30 + r * h))
    S.save(out); print('wrote', out)


if __name__ == '__main__':
    argv = sys.argv[1:]; body = common.opt(argv, '--body') or 'pma'; res = [int(x) for x in (common.opt(argv, '--res') or '640,360').split(',')]
    if argv[0] == 'frames': render(argv[1], res)
    elif argv[0] == 'gun': movie(None, gun_specs(argv[1], body), argv[2])
    elif argv[0] == 'grid':
        band = [(f'{g["name"]} {pick}', spec_of(g['id'], pick, 'empty_reload', 'right', body)) for g in [common.gun(i) for i, r in prod.owners() if r['category'] == argv[1]] for pick in g['reload']['picks']]
        movie(None, [band], argv[2], size=(384, 216) if len(band) > 4 else (480, 270))
    elif argv[0] == 'stills': stills(argv[1], body)
    else: raise SystemExit(__doc__)
