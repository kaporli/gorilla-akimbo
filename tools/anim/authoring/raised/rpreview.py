"""Previews of the raised poses (Blender, ../author/scene.py), first person, the camera of checks.raised.

usage: rpreview.py sheet <gun> [--body pma] [--partner ajax] [--out <dir>]
         before | after stills: the gun in both hands (idle, aim), the gun right with the partner left, the partner
         right with the gun left  -> <out>/<body>_<gun>_before_after.png
       rpreview.py seq <gun> [--body pma] [--partner ajax] [--work <build work>] [--out <dir>]
         before | after video: raised idle, aim, back, the per-hand reload of the right gun, lowered, raise
         -> <out>/<body>_<gun>_before_after.mp4 (needs the built reload sets: WORK/tmp_reload)
       rpreview.py partner <gun> [--body pma] [--topmag shingen] [--pick lupper] [--out <dir>]
         the top-magazine reload with the gun as partner, both orders, before | after
         -> <out>/<body>_<gun>_partner_<side>.mp4
  GA_TEST=1 for test guns. --out default: <authoring work>/raised/previews
"""
import json, os, subprocess, sys
import rpose as R
from rpose import common
from lpose import blend, ease, FPS
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, common.ANIM)
import topmagsets

SCENE = os.path.join(common.HERE, 'author', 'scene.py')
RES = [1280, 720]


def owner(gid):
    """The gun whose manifest entries (raised, lowered, variables) a gun uses."""
    g = common.gun(gid)
    if g.get('vars') or g.get('generic'): return g
    return next(o for o in common.manifest.guns(all_=True) if o.get('vars') and o.get('arm_set') == g.get('arm_set'))


def raised_of(gid, body):
    ra = owner(gid).get('raised') or {}
    return (ra['pose'], ra['family'], ra['s'][body]) if ra.get('family', 'none') != 'none' else None


def hand_pose(body, L, gid, S, clip, t=0.0):
    """L with hand S in the gun's raised clip (or untouched without one)."""
    r = raised_of(gid, body)
    if not r: return L
    X = R.rig_of(R.clip_glb(r[0], body)).sample(clip + ('' if S == 'Right' else '_l'), t); L = list(L)
    for j in R.arm_joints(S): L[j] = X[j]
    return L


def low_glb(gid, body):
    low = owner(gid)['lowered']
    for d in (common.path('low_clips'), common.path('low_clips_test')):
        p = f'{d}/{body}/lowered_{low["pose"]}.glb'
        if os.path.exists(p): return p
    raise SystemExit(f'no lowered clip for {gid}')


def blender(body, frames, rg, lg, out, base_glb=None):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rig, p = R.base(body); glb = out + '_seq.glb'; R.write_full(rig, base_glb or p, {'seq': frames}, glb)
    j = {'clip_glb': glb, 'clip': 'seq', 'frames': list(range(len(frames))), 'out': out, 'body': body, 'view': 'fpp', 'eye': list(R.CAM['eye']),
         'fov': R.CAM['hfov_169'], 'pitch': 0, 'res': RES, 'left_mag_clip': None, 'right_mag_clip': None, 'one_mag': True, 'bg': [0.33, 0.36, 0.40]}
    for s, g in (('right', rg), ('left', lg)):
        j[f'{s}_gun'] = g; j[f'{s}_parts'] = R.gun_parts(common.gun(g)['mesh'])
    c = out + '_cfg.json'; json.dump(j, open(c, 'w'))
    return subprocess.Popen([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', c], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL), [f'{out}_{k:03d}.png' for k in range(len(frames))]


def text(im, s, y=0, size=22, color=(255, 220, 0)):
    d = ImageDraw.Draw(im); f = ImageFont.truetype('arialbd.ttf', size)
    d.rectangle([0, y, im.width, y + size + 12], fill=(18, 18, 22)); d.text((10, y + 5), s, fill=color, font=f)
    return im


def sheet(gid, body, partner, out):
    rig, _ = R.base(body); I0 = rig.sample(R.IDLE, 0.0); A0 = rig.sample(R.AIM, 0.0); jobs = []
    for tag, rg, lg in (('pair', gid, gid), ('right', gid, partner), ('left', partner, gid)):
        fr = []
        for L0, clip in ((I0, R.IDLE), (A0, R.AIM)):
            fr += [L0, hand_pose(body, hand_pose(body, L0, rg, 'Right', clip), lg, 'Left', clip)]
        jobs.append((tag, rg, lg) + blender(body, fr, rg, lg, f'{out}/frames/{body}_{gid}_{tag}'))
    for j in jobs: j[3].wait()
    r = raised_of(gid, body); W, H, PAD = 960, 540, 40
    rows = [('pair', 0, f'{gid} in both hands, raised idle'), ('pair', 2, f'{gid} in both hands, aim'), ('right', 0, f'{gid} right, {partner} left, raised idle'),
            ('left', 0, f'{partner} right, {gid} left, raised idle')]
    im = Image.new('RGB', (W * 2, 60 + (H + PAD) * len(rows)), (18, 18, 22)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype('arialbd.ttf', 26); fs = ImageFont.truetype('arialbd.ttf', 18)
    d.text((10, 14), f'before: game pistol pose ({body})', fill=(255, 220, 0), font=f)
    o = [round(100 * x, 1) for x in R.delta(r[1], r[2])[0]]
    d.text((W + 10, 14), f'after: {r[1]} {R.FAM[r[1]]["name"]}, s {r[2]:.3f} m (right {o[0]:+.1f}, up {o[1]:+.1f}, back {o[2]:+.1f} cm)', fill=(255, 220, 0), font=f)
    by = {j[0]: j[4] for j in jobs}
    for k, (tag, i, title) in enumerate(rows):
        y = 60 + k * (H + PAD); d.text((10, y + 8), title, fill=(255, 255, 255), font=fs)
        for c in (0, 1): im.paste(Image.open(by[tag][i + c]).convert('RGB').resize((W, H)), (c * W, y + PAD))
    p = f'{out}/{body}_{gid}_before_after.png'; im.save(p); print(p)


def seq(gid, body, partner, work, out):
    rig, _ = R.base(body); I0 = rig.sample(R.IDLE, 0.0); A0 = rig.sample(R.AIM, 0.0); jobs = []
    rg, lg = gid, partner
    for tag, raised in (('before', False), ('after', True)):
        hp = (lambda L, clip, t=0.0: hand_pose(body, hand_pose(body, L, rg, 'Right', clip, t), lg, 'Left', clip, t)) if raised else (lambda L, clip, t=0.0: L)
        I, Am = hp(I0, R.IDLE), hp(A0, R.AIM)
        # the right gun's reload clip: its own set (after) or the shared one (before)
        r = raised_of(rg, body)
        name = common.manifest.raised_reload_set(body, 'right', r[0]) if raised and r else common.manifest.reload_set(body, 'right')
        rr = R.rig_of(common.need(f'{work}/tmp_reload/{name}/{name}.glb')); n = int(round(rr.duration('reload') * FPS)) + 1
        Lw = list(I0)
        for S, g_, c in (('Right', rg, 'friendly_idlepose'), ('Left', lg, 'friendly_idlepose_l')):
            X = R.rig_of(low_glb(g_, body)).sample(c, 0.0)
            for j in R.arm_joints(S): Lw[j] = X[j]
        fr, lab = [], []

        def hold(P, k, s):
            for _ in range(k): fr.append(P); lab.append(s)

        def tr(P, Q, secs, kind, s):
            k = max(1, int(round(secs * 30)))
            for i in range(1, k + 1): fr.append(blend(P, Q, ease(kind, i / k))); lab.append(s)
        hold(I, 20, 'raised idle'); tr(I, Am, 0.25, 'EaseInOut', 'aim in'); hold(Am, 20, 'aim'); tr(Am, I, 0.25, 'EaseInOut', 'aim out'); hold(I, 10, 'raised idle')
        R0 = None
        for f in range(n):   # right arm from the reload clip, the rest stays in the idle
            X = rr.sample('reload', f / FPS); P = list(I)
            for j in R.arm_joints('Right'): P[j] = X[j]
            if f < 6: P = blend(I, P, (f + 1) / 6)      # Ready -> Reload blends 0.2 s
            fr.append(P); lab.append('reload (right gun)' if f < n - 1 else 'reload: last frame')
        hold(I, 12, 'raised idle (cut from the reload, 0 s)')
        tr(I, Lw, 0.3, 'EaseInOut', 'lower (0.3 s)'); hold(Lw, 20, 'lowered'); tr(Lw, I, 0.2, 'EaseOut', 'raise (0.2 s)'); hold(I, 15, 'raised idle')
        keep = list(range(0, len(fr), 2))
        jobs.append((tag, [lab[i] for i in keep]) + blender(body, [fr[i] for i in keep], rg, lg, f'{out}/frames/{body}_{gid}_seq_{tag}'))
    for j in jobs: j[2].wait()
    fd = f'{out}/frames/{body}_{gid}_seq_c'; os.makedirs(fd, exist_ok=True)
    for k in range(len(jobs[0][1])):
        im = Image.new('RGB', (RES[0] * 2, RES[1]), (0, 0, 0))
        for c, j in enumerate(jobs):
            a = Image.open(j[3][k]).convert('RGB'); text(a, f'{j[0]}: {rg} right, {lg} left ({body})   |   {j[1][k]}'); im.paste(a, (c * RES[0], 0))
        im.save(f'{fd}/c_{k:03d}.png')
    p = f'{out}/{body}_{gid}_before_after.mp4'
    subprocess.run([common.need(common.path('ffmpeg')), '-y', '-loglevel', 'error', '-framerate', '15', '-i', f'{fd}/c_%03d.png', '-c:v', 'libx264', '-crf', '18',
                    '-pix_fmt', 'yuv420p', p], check=True)
    print(p)


def partner(gid, body, topmag, pick, out):
    r = raised_of(gid, body); var = owner(gid)['vars'][0]
    srcs = [(src, S) for b, src, pose, S in topmagsets.raised_sources(common.path('clips')) if b == body and pose == r[0]]
    for side in ('left', 'right'):   # the top-magazine gun's hand
        cand = [(src, S) for src, S in srcs if os.path.basename(src).startswith(f'{topmag}_{side}_')]
        src, S = next(((a, b) for a, b in cand if f'_{pick}' in os.path.basename(a)), cand[0])
        rg, lg = (gid, topmag) if side == 'left' else (topmag, gid); jobs = []
        for tag, glb in (('before', src), ('after', topmagsets.raised_clip(src, r[0]))):
            rig = R.rig_of(glb); c = rig.g.j['animations'][0]['name']; n = int(round(rig.duration(c) * FPS)) + 1
            # before: the clip between the gun's raised idle (Ready blends in 0.2 s, the end is a cut)
            I = hand_pose(body, R.base(body)[0].sample(R.IDLE, 0.0), gid, S, R.IDLE)
            fr = [I] * 10 + [blend(I, rig.sample(c, f / FPS), min(1.0, (f + 1) / 6)) for f in range(n)] + [I] * 14
            lab = ['raised idle'] * 10 + [f'top-magazine reload f{f}' for f in range(n)] + ['raised idle (cut, 0 s)'] * 14
            keep = list(range(0, len(fr), 2))
            jobs.append((tag, [lab[i] for i in keep]) + blender(body, [fr[i] for i in keep], rg, lg, f'{out}/frames/{body}_{gid}_partner_{side}_{tag}', base_glb=glb))
        for j in jobs: j[2].wait()
        fd = f'{out}/frames/{body}_{gid}_partner_{side}_c'; os.makedirs(fd, exist_ok=True)
        for k in range(len(jobs[0][1])):
            im = Image.new('RGB', (RES[0] * 2, RES[1]), (0, 0, 0))
            for cc, j in enumerate(jobs):
                a = Image.open(j[3][k]).convert('RGB')
                text(a, f'{j[0]}: {rg} right, {lg} left, {os.path.basename(src)[:-4]} ({body})   |   {j[1][k]}', size=18); im.paste(a, (cc * RES[0], 0))
            im.save(f'{fd}/c_{k:03d}.png')
        p = f'{out}/{body}_{gid}_partner_{topmag}_{side}.mp4'
        subprocess.run([common.need(common.path('ffmpeg')), '-y', '-loglevel', 'error', '-framerate', '15', '-i', f'{fd}/c_%03d.png', '-c:v', 'libx264', '-crf', '18',
                        '-pix_fmt', 'yuv420p', p], check=True)
        print(p)


if __name__ == '__main__':
    argv = sys.argv[1:]
    body = common.opt(argv, '--body') or 'pma'; other = common.opt(argv, '--partner') or 'ajax'
    out = common.opt(argv, '--out') or common.work('raised', 'previews')
    work = common.opt(argv, '--work') or (common.manifest.path('work') + ('/test' if common.manifest.with_test() else ''))
    tm = common.opt(argv, '--topmag') or 'shingen'; pick = common.opt(argv, '--pick') or 'lupper'
    cmd, gid = argv[:2]
    if cmd == 'sheet': sheet(gid, body, other, out)
    elif cmd == 'seq': seq(gid, body, other, work, out)
    elif cmd == 'partner': partner(gid, body, tm, pick, out)
