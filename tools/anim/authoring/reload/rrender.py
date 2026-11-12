"""Previews of reload drafts: Blender (author/scene.py) and ffmpeg.

usage:
  rrender.py draft <spec.json> [--res 640,360] [--jobs 2]     frames, <stem>.mp4 (first person | outside), <stem>_strip.png
  rrender.py sheet <out png> <title> <spec.json> ...           contact sheet: one row per draft
  rrender.py grid  <out mp4> <spec.json> ...                   all drafts side by side (first person over outside)
First person: the camera fitted to the game for the raised poses (eye [0, 1.61, -0.02], 105 deg, level).
The reloading gun's magazine plays the gun's own reload animation (orange). Outside view: from the front right,
grey blocks stand for torso, belt and thighs.
Frames are kept in <spec folder>/frames/<stem>/.
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import gungeo
from PIL import Image, ImageDraw, ImageFont

SCENE = renv.TOOLS + '/authoring/author/scene.py'
CAM = {'eye': [0, 1.61, -0.02], 'fov': 105.0, 'pitch': 0}
OUTCAM = {'cam_loc': [1.4, 1.8, 1.8], 'cam_tgt': [0.05, 0.1, 1.22], 'angle': 52}


def font(size, bold=True):
    try: return ImageFont.truetype('arialbd.ttf' if bold else 'arial.ttf', size)
    except OSError: return ImageFont.load_default()


def ffmpeg(args):
    subprocess.run([common.need(common.path('ffmpeg')), '-y', '-loglevel', 'error'] + args, check=True)


def parts(gid):
    G = common.gun(gid)['mesh']
    return [f'{G}__{p}' for p in gungeo.BODY_PARTS if common.find('weapon_meshes', f'{G}__{p}.glb')]


def stem_of(spec_path): return os.path.splitext(os.path.basename(spec_path))[0]


def frames_dir(spec_path):
    d = os.path.dirname(spec_path) + '/frames/' + stem_of(spec_path); os.makedirs(d, exist_ok=True)
    return d


def phase(T, f):
    if f < T['out']: return 'start'
    if f < (T.get('far') or T['out'] + 5): return 'magazine out'
    if f < T['near']: return 'magazine away'
    if f < T['seated']: return 'new magazine in'
    h = T.get('handle')
    if h and h[0] <= f <= h[1]: return 'handle'
    if f < T['seated'] + 4: return 'seated'
    return 'back up' if not h or f > h[1] else 'loaded'


def render_frames(spec_path, res=(640, 360), jobs=2, views=('fpp', 'out')):
    spec = json.load(open(spec_path)); d = frames_dir(spec_path); N = spec['frames']; procs = []
    for v in views:
        for k in range(jobs):
            cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': list(range(N))[k::jobs], 'out': f'{d}/{v}', 'body': spec['_body'], 'view': v,
                   'res': list(res), 'right_gun': spec['_gun'], 'left_gun': spec['_left_gun'], 'right_parts': parts(spec['_gun']), 'left_parts': parts(spec['_left_gun']),
                   'right_mag_clip': spec['_gun_clip'], 'left_mag_clip': None, 'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40]}
            cfg.update(CAM if v == 'fpp' else OUTCAM)
            p = f'{d}/cfg_{v}_{k}.json'; json.dump(cfg, open(p, 'w'))
            procs.append((p, subprocess.Popen([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', p],
                                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')))
    for p, pr in procs:
        log = pr.communicate()[0]
        if 'DONE' not in log: raise SystemExit(f'scene.py failed for {p}:\n' + '\n'.join(log.splitlines()[-15:]))
    return d


def key_frames(spec):
    T = spec['_timing']; N = spec['frames']; h = T.get('handle')
    fr = [0, max(T['out'] - 4, 1), T['out'] + 1, (T.get('far') or T['out'] + 5) + 2, (T['near'] + T['out']) // 2 + 6, T['seated'], T['seated'] + 6]
    fr += [h[0] - 2, h[0] + 3, h[1] + 3] if h else [T['seated'] + 14]
    fr += [N - 10, N - 1]
    return sorted({min(max(int(f), 0), N - 1) for f in fr})


def draft(spec_path, res=(640, 360), jobs=2):
    spec = json.load(open(spec_path)); T = spec['_timing']; N = spec['frames']; W, H = res
    d = frames_dir(spec_path)
    if not all(os.path.exists(f'{d}/{v}_{N - 1:03d}.png') for v in ('fpp', 'out')) or os.path.getmtime(f'{d}/fpp_{N - 1:03d}.png') < os.path.getmtime(spec['out']):
        render_frames(spec_path, res, jobs)
    ft, fs = font(20), font(15, False); title = f"{spec['_draft']} {spec.get('_name', '')}"
    for f in range(N):
        o = Image.new('RGB', (2 * W, H))
        for k, v in enumerate(('fpp', 'out')): o.paste(Image.open(f'{d}/{v}_{f:03d}.png').convert('RGB').resize((W, H)), (k * W, 0))
        dr = ImageDraw.Draw(o); dr.rectangle((0, 0, 2 * W, 28), fill=(0, 0, 0))
        dr.text((8, 3), title, fill=(255, 220, 0), font=ft); dr.text((W + 8, 5), f'frame {f} / {N - 1}   {phase(T, f)}', fill=(255, 255, 255), font=fs)
        o.save(f'{d}/c_{f:03d}.png')
    base = os.path.dirname(spec_path) + '/' + stem_of(spec_path)
    ffmpeg(['-framerate', '30', '-i', f'{d}/c_%03d.png', '-frames:v', str(N), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '20', base + '.mp4'])
    fr = key_frames(spec); cols = 4; S = Image.new('RGB', (W * cols, H * ((len(fr) + cols - 1) // cols)), (20, 20, 24))
    for k, f in enumerate(fr):
        im = Image.open(f'{d}/fpp_{f:03d}.png').convert('RGB').resize((W, H)); dr = ImageDraw.Draw(im)
        dr.rectangle((0, 0, W, 30), fill=(0, 0, 0)); dr.text((8, 4), f'frame {f}: {phase(T, f)}', fill=(255, 220, 0), font=ft)
        S.paste(im, ((k % cols) * W, (k // cols) * H))
    S.save(base + '_strip.png')
    print('wrote', base + '.mp4', base + '_strip.png')
    return base


def sheet(out, title, specs):
    """One row per draft: first person at magazine out, at the seat, at the handle (or after the seat); outside at the
    seat and at the handle."""
    w, h = 384, 216; rows = []; ft, fs = font(18), font(13, False)
    for sp in specs:
        spec = json.load(open(sp)); T = spec['_timing']; d = frames_dir(sp); hd = T.get('handle'); N = spec['frames']
        hf = min((hd[0] + 3) if hd else T['seated'] + 12, N - 1)
        cells = [('fpp', T['out'] + 2, 'magazine out'), ('fpp', (T['near'] + T['seated']) // 2, 'new magazine'), ('fpp', hf, 'handle' if hd else 'after'),
                 ('out', T['seated'], 'seat, outside'), ('out', hf, ('handle' if hd else 'after') + ', outside')]
        rows.append((f"{spec['_draft']} {spec.get('_name', '')}", [(Image.open(f'{d}/{v}_{f:03d}.png').convert('RGB').resize((w, h)), f'f{f} {lab}') for v, f, lab in cells]))
    S = Image.new('RGB', (w * 5, 40 + (h + 26) * len(rows)), (20, 20, 24)); dr = ImageDraw.Draw(S); dr.text((10, 8), title, fill=(255, 255, 255), font=font(22))
    for r, (name, cells) in enumerate(rows):
        y = 40 + r * (h + 26); dr.text((8, y + 3), name, fill=(255, 220, 0), font=ft)
        for k, (im, lab) in enumerate(cells):
            S.paste(im, (k * w, y + 26)); dr.rectangle((k * w, y + 26, k * w + 150, y + 44), fill=(0, 0, 0)); dr.text((k * w + 4, y + 28), lab, fill=(255, 255, 255), font=fs)
    S.save(out); print('wrote', out)


def grid(out, specs, cols=5):
    """All drafts side by side: first person over the outside view, each at its own length (shorter ones hold)."""
    w, h = 384, 216; S = [json.load(open(sp)) for sp in specs]; D = [frames_dir(sp) for sp in specs]; n = max(s['frames'] for s in S)
    rows = (len(S) + cols - 1) // cols; tmp = os.path.dirname(out) + '/frames_' + os.path.splitext(os.path.basename(out))[0]; os.makedirs(tmp, exist_ok=True); ft = font(15)
    for f in range(n + 15):
        G = Image.new('RGB', (w * cols, 2 * h * rows), (20, 20, 24)); dr = ImageDraw.Draw(G)
        for k, (s, d) in enumerate(zip(S, D)):
            ff = min(f, s['frames'] - 1); x, y = (k % cols) * w, (k // cols) * 2 * h
            G.paste(Image.open(f'{d}/fpp_{ff:03d}.png').convert('RGB').resize((w, h)), (x, y)); G.paste(Image.open(f'{d}/out_{ff:03d}.png').convert('RGB').resize((w, h)), (x, y + h))
            dr.rectangle((x, y, x + w, y + 20), fill=(0, 0, 0)); dr.text((x + 5, y + 2), f"{s['_draft']} {s.get('_name', '')}", fill=(255, 220, 0), font=ft)
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 15), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '22', out]); print('wrote', out)


if __name__ == '__main__':
    argv = sys.argv[1:]; res = [int(x) for x in (common.opt(argv, '--res') or '640,360').split(',')]; jobs = int(common.opt(argv, '--jobs') or 2)
    if argv[0] == 'draft': draft(argv[1], res, jobs)
    elif argv[0] == 'sheet': sheet(argv[1], argv[2], argv[3:])
    elif argv[0] == 'grid': grid(argv[1], argv[2:])
    else: raise SystemExit(__doc__)
