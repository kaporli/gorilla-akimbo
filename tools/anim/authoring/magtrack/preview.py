"""Preview sheets of the written magazine tracks, through the fitted first-person camera (E, hfov 97, 16:9):
one sheet per set, one row per pick (its first clip), frames around the hit.
Grey: magazine gun, blue: partner gun, orange: magazine (pale once hidden).
usage: preview.py <sets glb dir> <out dir> [--spec <spec.json>] [--clips <dir>]"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw
import mag_geom as g
from mag_geom import app, partner_pts, E, TX, MAGB, Glb

FR = (22, 24, 25, 26, 27, 28, 30, 32, 35, 40, 47, 62)
_own = None


def pts(key):
    global _own
    if key == g.MAGGUN['id']:
        if _own is None: _own = g.dense(*g.tris(g.PARTS[key]['parts']), 0.012)
        return _own
    return partner_pts(key)[::3]


def proj(P):
    q = P - E; z = -q[:, 2]; ok = z > 0.02
    fp = 640 / TX
    return np.c_[640 + fp * q[ok, 0] / z[ok], 360 - fp * q[ok, 1] / z[ok]]


def sheet(spec, d, key, out, clips_dir=None, sc=0.25):
    gl = Glb(g.common.need(g.set_glb(d, key)))
    W_, H_ = int(1280 * sc), int(720 * sc); LBL = 150; TOP = 22; n = len(spec[key])
    im = Image.new('RGB', (LBL + len(FR) * (W_ + 4), TOP + n * (H_ + 18)), 'white'); dr = ImageDraw.Draw(im)
    dr.text((4, 4), f'{g.MAGGUN["name"]} magazine, {key}, first clip of each pick. Camera fit: eye y {E[1]}, hfov 97. '
                    f'grey {g.MAGGUN["name"]}, blue partner, orange magazine (pale = hidden)', fill='black')
    for pi, e in enumerate(spec[key]):
        G, S_, _ = g.read_track(gl, g.NAMES[pi])
        p, b, sh, st, keys = g.spec_cases(spec, key, pi, clips_dir)[0]
        a = g.Arm(p); pk = keys[0]
        y0 = TOP + pi * (H_ + 18)
        dr.text((4, y0 + 20), g.pick_name(e), fill='black'); dr.text((4, y0 + 36), os.path.basename(p)[:-4][:24], fill='#555555')
        dr.text((4, y0 + 52), f'{b}, partner {pk}', fill='#555555')
        for j, f in enumerate(FR):
            x0 = LBL + j * (W_ + 4)
            dr.rectangle([x0, y0 + 14, x0 + W_ - 1, y0 + 14 + H_ - 1], fill='#f2f2f2', outline='#999999')
            dr.text((x0 + 2, y0), f'f{f}' + (' (mag hidden)' if S_[f] < 0.5 else ''), fill='black')
            def plot(P, col):
                for u, v in proj(P):
                    if 0 <= u < 1280 and 0 <= v < 720: dr.point((x0 + u * sc, y0 + 14 + v * sc), fill=col)
            plot(app(a.W(sh, f), pts(g.MAGGUN['id'])[::2]), '#808080')
            plot(app(a.W(st, f), pts(pk)[::2]), '#3a6fd8')
            plot(app(a.W(sh, f) @ G[f], MAGB[::2]), '#ff7a00' if S_[f] > 0.5 else '#ffd9b3')
    im.save(out); print('wrote', out)


if __name__ == '__main__':
    a = sys.argv[1:]; spec = g.load_spec(g.common.opt(a, '--spec')); cdir = g.common.opt(a, '--clips')
    if len(a) != 2: raise SystemExit(__doc__)
    os.makedirs(a[1], exist_ok=True)
    for key in g.spec_keys(spec):
        sheet(spec, a[0], key, f'{a[1]}/sheet_{key}.png', cdir)
