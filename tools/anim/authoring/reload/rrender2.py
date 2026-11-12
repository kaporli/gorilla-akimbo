"""Round 2 previews: larger, own magazine track, moving gun parts, frame numbers burned in.

usage:
  rrender2.py take <spec.json> [--res 1280,720] [--jobs 2]   frames; <stem>_fpp.mp4, <stem>_out.mp4, <stem>.mp4 (both), <stem>_strip.png
  rrender2.py versus <out mp4> <round 1 spec> <take A spec> <take B spec>    round 1 | A | B, first person over outside
  rrender2.py grid <out mp4> <spec> ...        all takes, first person over outside
  rrender2.py sheet <out png> <spec> ...       contact sheet: per take release, flight, seat, handle (first person and outside)
Round 1 frames are read from the round 1 folders (640 x 360, the game's magazine animation, static gun parts).
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import rrender
from rrender import font, ffmpeg, parts, stem_of, frames_dir, SCENE, CAM, OUTCAM
from PIL import Image, ImageDraw


def phase(spec, f):
    T = spec['_timing']; mk = spec.get('_marks', {}); mg = spec.get('_mag', {})
    if not mg: return rrender.phase(T, f)
    h = T.get('handle'); g = T['parts'].get('magazine_grabber', {}).get('window')
    if g and g[0] - 3 <= f <= g[0] + 3: return 'latch opens'
    if 'loosen' in mk and mk['loosen'] - 2 <= f < mg['release']: return 'shake: loose'
    if f < mg['release']: return 'start'
    if f < mg['release'] + 6: return 'magazine thrown' if mg.get('mode') != 'hook' else 'magazine hooked off'
    if f < mg['appear']: return 'magazine falls'
    if f < T['seated'] - 5: return 'over the fresh magazine'
    if f < T['seated']: return 'slam'
    if f < T['seated'] + 4: return 'seated'
    if h and h[0] - 1 <= f <= h[0] + 6: return 'handle / bolt'
    if g and g[1] - 4 <= f <= g[1] + 3: return 'latch shuts'
    return 'up'


def render_frames(spec_path, res=(1280, 720), jobs=2):
    spec = json.load(open(spec_path)); d = frames_dir(spec_path); N = spec['frames']; procs = []
    for v in ('fpp', 'out'):
        for k in range(jobs):
            cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': list(range(N))[k::jobs], 'out': f'{d}/{v}', 'body': spec['_body'], 'view': v, 'res': list(res),
                   'right_gun': spec['_gun'], 'left_gun': spec['_left_gun'], 'right_parts': parts(spec['_gun']), 'left_parts': parts(spec['_left_gun']),
                   'right_mag_clip': spec['_gun_clip'], 'left_mag_clip': None, 'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40],
                   'right_parts_anim': True}
            if spec.get('_track'): cfg['right_mag_track'] = spec['_track']
            cfg.update(CAM if v == 'fpp' else OUTCAM)
            p = f'{d}/cfg_{v}_{k}.json'; json.dump(cfg, open(p, 'w'))
            procs.append((p, subprocess.Popen([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', p], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')))
    for p, pr in procs:
        log = pr.communicate()[0]
        if 'DONE' not in log: raise SystemExit(f'scene.py failed for {p}:\n' + '\n'.join(log.splitlines()[-15:]))
    return d


def label(im, title, sub, big=True):
    dr = ImageDraw.Draw(im); W = im.size[0]; h = 40 if big else 26; ft = font(26 if big else 17); fs = font(20 if big else 14, False)
    dr.rectangle((0, 0, W, h), fill=(0, 0, 0)); dr.text((10, 5 if big else 3), title, fill=(255, 220, 0), font=ft)
    w = dr.textlength(sub, font=fs); dr.text((W - w - 12, 9 if big else 5), sub, fill=(255, 255, 255), font=fs)
    return im


def take(spec_path, res=(1280, 720), jobs=2):
    spec = json.load(open(spec_path)); N = spec['frames']; W, H = res; d = frames_dir(spec_path)
    if not all(os.path.exists(f'{d}/{v}_{N - 1:03d}.png') for v in ('fpp', 'out')) or os.path.getmtime(f'{d}/fpp_{N - 1:03d}.png') < os.path.getmtime(spec['out']):
        render_frames(spec_path, res, jobs)
    title = f"{spec['_draft']} {spec.get('_name', '')}"; base = os.path.dirname(spec_path) + '/' + stem_of(spec_path)
    for f in range(N):
        sub = f'frame {f} / {N - 1}   {phase(spec, f)}'; both = Image.new('RGB', (2 * W, H))
        for k, v in enumerate(('fpp', 'out')):
            im = label(Image.open(f'{d}/{v}_{f:03d}.png').convert('RGB'), title + ('  first person' if v == 'fpp' else '  outside'), sub); im.save(f'{d}/l{v}_{f:03d}.png'); both.paste(im, (k * W, 0))
        both.save(f'{d}/c_{f:03d}.png')
    for tag, src in (('_fpp', 'lfpp'), ('_out', 'lout'), ('', 'c')):
        ffmpeg(['-framerate', '30', '-i', f'{d}/{src}_%03d.png', '-frames:v', str(N), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '20', base + tag + '.mp4'])
    fr = key_frames(spec); cols = 4; w, h = 640, 360; S = Image.new('RGB', (w * cols, h * ((len(fr) + cols - 1) // cols)), (20, 20, 24))
    for k, f in enumerate(fr):
        S.paste(label(Image.open(f'{d}/fpp_{f:03d}.png').convert('RGB').resize((w, h)), f'frame {f}', phase(spec, f), big=False), ((k % cols) * w, (k // cols) * h))
    S.save(base + '_strip.png'); print('wrote', base + '.mp4')


def key_frames(spec):
    T = spec['_timing']; N = spec['frames']; mg = spec.get('_mag') or {'release': T['out'], 'appear': T['near']}; h = T.get('handle'); g = T['parts'].get('magazine_grabber', {}).get('window')
    r = mg['release']; fr = [0, r - 4, r, r + 2, r + 5, r + 9, mg['appear'], T['seated'] - 4, T['seated'], T['seated'] + 2]
    if g: fr += [g[0], g[1] - 3, g[1], g[1] + 2]
    if h: fr += [h[0] - 2, h[0], h[0] + 3]
    fr += [N - 12, N - 1]
    return sorted({min(max(int(f), 0), N - 1) for f in fr})


def cell(spec_path, v, f, size, title, spec):
    d = frames_dir(spec_path); N = spec['frames']; ff = min(f, N - 1)
    return label(Image.open(f'{d}/{v}_{ff:03d}.png').convert('RGB').resize(size), title, f'f{ff}  {phase(spec, ff)}', big=False)


def versus(out, sp1, spa, spb):
    S = [json.load(open(p)) for p in (sp1, spa, spb)]; n = max(s['frames'] for s in S); w, h = 853, 480
    tmp = os.path.dirname(out) + '/frames_' + os.path.splitext(os.path.basename(out))[0]; os.makedirs(tmp, exist_ok=True)
    names = [f"ROUND 1  {S[0]['_draft']}", f"ROUND 2  {S[1]['_draft']} (snappy)", f"ROUND 2  {S[2]['_draft']} (heavy)"]
    for f in range(n + 20):
        G = Image.new('RGB', (3 * w + 2, 2 * h), (20, 20, 24))
        for k, (p, s) in enumerate(zip((sp1, spa, spb), S)):
            G.paste(cell(p, 'fpp', f, (w, h), names[k], s), (k * (w + 1), 0)); G.paste(cell(p, 'out', f, (w, h), names[k] + '  outside', s), (k * (w + 1), h))
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 20), '-vf', 'format=yuv420p,pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-crf', '21', out]); print('wrote', out)


def grid(out, specs, cols=5):
    S = [json.load(open(p)) for p in specs]; n = max(s['frames'] for s in S); w, h = 512, 288; rows = (len(S) + cols - 1) // cols
    tmp = os.path.dirname(out) + '/frames_' + os.path.splitext(os.path.basename(out))[0]; os.makedirs(tmp, exist_ok=True)
    for f in range(n + 20):
        G = Image.new('RGB', (w * cols, 2 * h * rows), (20, 20, 24))
        for k, (p, s) in enumerate(zip(specs, S)):
            x, y = (k % cols) * w, (k // cols) * 2 * h
            G.paste(cell(p, 'fpp', f, (w, h), s['_draft'] + ' ' + s.get('_name', '').split(',')[0], s), (x, y)); G.paste(cell(p, 'out', f, (w, h), s['_draft'] + ' outside', s), (x, y + h))
        G.save(f'{tmp}/g_{f:03d}.png')
    ffmpeg(['-framerate', '30', '-i', f'{tmp}/g_%03d.png', '-frames:v', str(n + 20), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '22', out]); print('wrote', out)


def sheet(out, specs):
    w, h = 480, 270; S = Image.new('RGB', (w * 6, 44 + (h + 2) * len(specs)), (20, 20, 24)); dr = ImageDraw.Draw(S)
    dr.text((10, 8), 'Round 2 takes: first person at the release, 3 and 7 frames later (magazine in flight), outside at the flight, at the slam, at the handle / bolt / latch', fill=(255, 255, 255), font=font(20))
    for r, p in enumerate(specs):
        s = json.load(open(p)); T = s['_timing']; mg = s['_mag']; rel = mg['release']; hd = T.get('handle'); g = T['parts'].get('magazine_grabber', {}).get('window')
        hf = (hd[0] + 1) if hd else (g[1] if g else T['seated'] + 14)
        for k, (v, f) in enumerate((('fpp', rel), ('fpp', rel + 3), ('fpp', rel + 7), ('out', rel + 6), ('out', T['seated'] - 3), ('out', hf))):
            S.paste(cell(p, v, f, (w, h), s['_draft'] if k else s['_draft'] + ' ' + s.get('_name', ''), s), (k * w, 44 + r * (h + 2)))
    S.save(out); print('wrote', out)


if __name__ == '__main__':
    argv = sys.argv[1:]; res = [int(x) for x in (common.opt(argv, '--res') or '1280,720').split(',')]; jobs = int(common.opt(argv, '--jobs') or 2)
    if argv[0] == 'take': take(argv[1], res, jobs)
    elif argv[0] == 'versus': versus(argv[1], *argv[2:5])
    elif argv[0] == 'grid': grid(argv[1], argv[2:])
    elif argv[0] == 'sheet': sheet(argv[1], argv[2:])
    else: raise SystemExit(__doc__)
