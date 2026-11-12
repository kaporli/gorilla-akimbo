"""Side and top silhouettes of guns with the seated magazine (orange), the grip hand (green) and moving parts (red),
gun axes. A picture to check the classification against.

usage: sideview.py <out png> <gun id> ...
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import qrot
from wclip import TClip
import gungeo, dumpanim
from PIL import Image, ImageDraw

W, H, SC = 760, 300, 700.0   # panel size, pixels per metre


def main(out, ids):
    img = Image.new('RGB', (2 * W, H * len(ids)), (245, 245, 245)); d = ImageDraw.Draw(img)
    hand = gungeo.hand_in_gun()['RightHandMiddle1']
    for r, gid in enumerate(ids):
        gun = common.gun(gid); G = gun['mesh']; V = []
        for p in gungeo.BODY_PARTS:
            f = common.find('weapon_meshes', f'{G}__{p}.glb')
            if f: V.append(gungeo.verts(f))
        V = np.concatenate(V)
        geo = gungeo.geo(gid); M = None
        b = gungeo.wanim(gun, 'base1')
        mf = common.find('weapon_meshes', f'{G}__mag_std_01.glb')
        if mf and 'slot' in geo:
            bs = b if 'mag_slot' in Glb(b).names else gungeo.wanim(gun, 'rcv1')
            gb = Glb(bs); an = [a['name'] for a in gb.j['animations']]
            c = TClip(gb, 'reload' if 'reload' in an else an[0]); st, sq = c.world(0)[gb.names.index('mag_slot')]
            M = np.array([st + qrot(sq, v) for v in gungeo.verts(mf)])
        parts = {}
        gb = Glb(b); an = [a['name'] for a in gb.j['animations']]
        if 'empty_reload' in an:
            c = TClip(gb, 'empty_reload')
            for n, w in dumpanim.windows(c).items():
                if n in ('muzzle_slot', 'fx_muzzle', 'pos_ironsight', 'scope_slot', 'mag_slot'): continue
                parts[n] = c.wf(w['peak_f'])[gb.names.index(n)][0]
        for k, (a, bb, name) in enumerate(((2, 1, 'side: muzzle left'), (2, 0, 'top: muzzle left, up = V right'))):
            ox, oy = k * W + W * 0.62, r * H + H * 0.52
            px = lambda p: (ox + p[a] * SC, oy - p[bb] * SC)
            for p in V: d.point(px(p), fill=(90, 90, 90))
            if M is not None:
                for p in M: d.point(px(p), fill=(232, 100, 26))
            x, y = px(hand); d.ellipse((x - 7, y - 7, x + 7, y + 7), outline=(30, 160, 30), width=3)
            for n, p in parts.items():
                x, y = px(p); d.line((x - 5, y - 5, x + 5, y + 5), fill=(220, 0, 0), width=2); d.line((x - 5, y + 5, x + 5, y - 5), fill=(220, 0, 0), width=2)
                d.text((x + 6, y - 12), n, fill=(200, 0, 0))
            d.text((k * W + 8, r * H + 6), f'{gid}: {name}', fill=(0, 0, 0))
            d.line((ox, r * H + 20, ox, r * H + H - 4), fill=(190, 190, 190))
    img.save(out); print('wrote', out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
