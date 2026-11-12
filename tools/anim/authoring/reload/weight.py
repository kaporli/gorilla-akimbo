"""Weight class of each rifle from its mesh: bulk, not length. A light gun gets the snappy take (A) of each pick, a
heavy gun the heavy take (B).

usage: weight.py <out png> [--json out.json]
Per gun (body parts and seated magazine, gun axes): length, height, width (95 % of the vertices, so a sight post or
a cable does not count), side area (cm^2 of the side silhouette on a 5 mm grid), top area, bulk = side area x mean
width (litres: the volume of the silhouette extruded to the gun's mean width), bulk per length.
Class: heavy when bulk is over BULK_HEAVY litres or the mean width is over WIDTH_HEAVY cm.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import qrot
from wclip import TClip
import gungeo
from PIL import Image, ImageDraw, ImageFont

GUNS = ['copperhead', 'umbra', 'sidewinder', 'ajax', 'kyubi', 'masamune', 'hercules']
BULK_HEAVY = 5.5; WIDTH_HEAVY = 5.4
OWNER = {'masamune': 'heavy', 'hercules': 'heavy',     # picked by the owner (round 2)
         'copperhead': 'light', 'umbra': 'light', 'ajax': 'light', 'kyubi': 'light', 'sidewinder': 'light'}  # confirmed 2026-11-12


def cloud(gid):
    gun = common.gun(gid); G = gun['mesh']; V = []
    for p in gungeo.BODY_PARTS:
        f = common.find('weapon_meshes', f'{G}__{p}.glb')
        if f: V.append(rchecks_sample(f))
    b = gungeo.wanim(gun, 'base1'); mf = common.find('weapon_meshes', f'{G}__mag_std_01.glb'); M = None
    if mf and b:
        bs = b if 'mag_slot' in Glb(b).names else gungeo.wanim(gun, 'rcv1'); gb = Glb(bs); an = [a['name'] for a in gb.j['animations']]
        st, sq = TClip(gb, 'reload' if 'reload' in an else an[0]).world(0)[gb.names.index('mag_slot')]
        import magtrack2
        S = magtrack2.vanilla(gid, 'empty_reload')['seat']; P = rchecks_sample(mf); M = (np.c_[P, np.ones(len(P))] @ S.T)[:, :3]
    return np.concatenate(V), M


def rchecks_sample(path, n=60000):
    import rchecks
    return rchecks.sample(rchecks.tris(path), n)


def measure(gid):
    V, M = cloud(gid); A = np.concatenate([V, M]) if M is not None else V
    lo, hi = np.percentile(A, 2.5, axis=0), np.percentile(A, 97.5, axis=0); g = 0.005
    def area(a, b):
        ij = np.unique(np.floor(A[:, [a, b]] / g).astype(int), axis=0); return len(ij) * g * g * 1e4, ij
    side, sij = area(2, 1); top, tij = area(2, 0)
    # mean width: per 5 mm slice along the barrel, the x extent
    z = np.floor(A[:, 2] / g).astype(int); w = [np.ptp(A[z == k, 0]) for k in np.unique(z) if (z == k).sum() > 20]
    mw = float(np.mean(w)) * 100; bulk = side * mw / 1000.0; L = float(A[:, 2].max() - A[:, 2].min())
    r = {'gun': gid, 'name': common.gun(gid)['name'], 'length_cm': round(L * 100, 1), 'height_cm': round(float(hi[1] - lo[1]) * 100, 1), 'width_cm': round(float(hi[0] - lo[0]) * 100, 1),
         'mean_width_cm': round(mw, 1), 'side_area_cm2': round(side), 'top_area_cm2': round(top), 'bulk_l': round(bulk, 1), 'bulk_per_m': round(bulk / L, 1)}
    r['class'] = OWNER.get(gid) or ('heavy' if bulk > BULK_HEAVY or mw > WIDTH_HEAVY else 'light'); r['by'] = 'owner' if gid in OWNER else 'proposed'
    return r, V, M


def main(out, jo=None):
    W, H, SC = 900, 330, 800.0; rows = []
    try: ft = ImageFont.truetype('arial.ttf', 17); fb = ImageFont.truetype('arialbd.ttf', 22)
    except OSError: ft = fb = ImageFont.load_default()
    img = Image.new('RGB', (2 * W + 420, 60 + H * len(GUNS)), (245, 245, 245)); d = ImageDraw.Draw(img)
    d.text((12, 8), 'Rifle weight classes from the mesh (body parts and seated magazine). Light = snappy take (A), heavy = heavy take (B). Same scale for every gun.', fill=(0, 0, 0), font=ft)
    d.text((12, 32), f'Rule: heavy when bulk (side area x mean width) is over {BULK_HEAVY} l or the mean width is over {WIDTH_HEAVY} cm. All classes decided by the owner.', fill=(60, 60, 60), font=ft)
    for r, gid in enumerate(GUNS):
        m, V, M = measure(gid); rows.append(m); y0 = 60 + r * H
        for k, (a, b) in enumerate(((2, 1), (2, 0))):
            ox, oy = k * W + W * 0.62, y0 + H * (0.50 if k == 0 else 0.5)
            for P, col in ((V[::6], (95, 95, 95)), (M[::3] if M is not None else [], (232, 100, 26))):
                for p in P: d.point((ox + p[a] * SC, oy - p[b] * SC), fill=col)
        heavy = m['class'] == 'heavy'
        d.text((2 * W + 10, y0 + 20), f"{m['name']}", fill=(0, 0, 0), font=fb)
        d.text((2 * W + 10, y0 + 52), f"{m['class'].upper()} ({m['by']})", fill=(180, 60, 20) if heavy else (30, 120, 60), font=fb)
        for i, t in enumerate((f"length {m['length_cm']} cm   height {m['height_cm']} cm", f"width {m['width_cm']} cm   mean width {m['mean_width_cm']} cm",
                               f"side area {m['side_area_cm2']} cm2   top area {m['top_area_cm2']} cm2", f"bulk {m['bulk_l']} l   bulk per metre {m['bulk_per_m']} l/m")):
            d.text((2 * W + 10, y0 + 90 + i * 24), t, fill=(40, 40, 40), font=ft)
        d.text((10, y0 + 6), 'side', fill=(120, 120, 120), font=ft); d.text((W + 10, y0 + 6), 'top', fill=(120, 120, 120), font=ft)
        d.line((0, y0, 2 * W + 420, y0), fill=(200, 200, 200))
    img.save(out); print('wrote', out)
    for m in rows: print(m)
    if jo: json.dump(rows, open(jo, 'w'), indent=1)


if __name__ == '__main__':
    argv = sys.argv[1:]; jo = common.opt(argv, '--json'); main(argv[0], jo)
