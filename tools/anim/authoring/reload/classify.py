"""Classification table of every magazine-fed gun the mod handles, from the gun's own reload animation and mesh.

usage: classify.py [--out dir]      writes classify.json and classify.md there (default <OUT>/classify)
Per gun and clip (reload, empty_reload): magazine position against the grip (gun axes), exit direction and speed,
frames (out, clear, far, near, seated), gun parts that move after the seat (handle, bolt), clip length.
Position: front = in front of the grip under the receiver, rear = behind the grip (bullpup), top = above the bore,
side = beside the receiver; from the magazine mesh box when there is one, else from the slot.
Leaves: "drops free" is not in the data: every one of these magazines follows the left hand in the game's own clip.
The column says which way it goes and how fast; pulled = the left hand is on it (armhands.py, rifles only).
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
import gungeo, timing

# weapon anim stems that differ from the mesh stem and are not in weapons.json
ANIM = {'tactician': 'w_shotgun__constitutional_arms_tactician'}
GUNS = ['ajax', 'kyubi', 'copperhead', 'umbra', 'masamune', 'sidewinder', 'hercules',
        'shingen', 'senkoh', 'pulsar', 'saratoga', 'warden', 'borg', 'dian',
        'carnage', 'tactician', 'zhuo', 'crusher', 'pozhar', 'igla', 'palica', 'testera', 'satara']


def position(geo):
    if 'slot' not in geo: return 'none'
    c = geo.get('mag_centre') or geo['slot']; s = geo['slot']
    if 'mag_min' in geo:
        w = geo['mag_max'][0] - geo['mag_min'][0]; off = abs(c[0])
        if c[1] > 0.03 and geo['mag_min'][1] > -0.02: return 'top'
        if off > 0.012 or (w > 0.09 and geo['mag_min'][1] > -0.12): return 'side cassette'
    return 'front box' if c[2] < -0.04 else 'rear (bullpup)' if c[2] > 0.04 else 'in the grip'


def direction(d):
    if not d: return ''
    n = [('right', d[0]), ('left', -d[0]), ('up', d[1]), ('down', -d[1]), ('back', d[2]), ('forward', -d[2])]
    n = sorted(n, key=lambda x: -x[1]); out = n[0][0]
    if n[1][1] > 0.45: out += '-' + n[1][0]
    return out


def row(gid):
    gun = common.gun(gid)
    if gid in ANIM: gun = dict(gun); gun['weapon_anim'] = ANIM[gid]
    r = {'gun': gid, 'name': gun['name'], 'type': gun['type']}
    try: geo = gungeo.geo(gid) if gid not in ANIM else None
    except Exception as e: geo = None; r['geo_error'] = str(e)[:80]
    if geo: r.update({'slot': geo.get('slot'), 'mag_centre': geo.get('mag_centre'), 'length': geo['length'], 'position': position(geo)})
    if not gungeo.wanim(gun, 'mag_std'):
        r['note'] = 'no magazine anim set: shells or break-open'; return r
    timing.common.gun = lambda k, g=gun, f=common.gun: g if k == gid else f(k)   # stem override for this call
    for clip in ('reload', 'empty_reload'):
        try:
            t = timing.table(gid, clip)
            r[clip] = {k: t[k] for k in ('frames', 'out', 'clear', 'far', 'near', 'seated', 'exit_dir', 'exit_speed_cm_f', 'in_dir', 'handle', 'slot')}
            r[clip]['leaves'] = direction(t['exit_dir']); r[clip]['parts'] = {n: [p['window'], p['move_cm'], p['turn_deg'], p['side'], p['stays_moved']] for n, p in t['parts'].items()}
            if 'position' not in r:
                s = t['slot']; r['position'] = 'front box (from the slot)' if s[2] < -0.04 else 'rear (from the slot)' if s[2] > 0.04 else 'at the grip (from the slot)'
        except Exception as e:
            r[clip] = {'error': str(e)[:120]}
    return r


if __name__ == '__main__':
    argv = sys.argv[1:]; out = common.opt(argv, '--out') or renv.OUT + '/classify'; os.makedirs(out, exist_ok=True)
    rows = [row(g) for g in GUNS]; json.dump(rows, open(out + '/classify.json', 'w'), indent=1)
    L = ['| gun | type | magazine | clip | frames | out | clear | seated | leaves (cm/f) | after the seat |', '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        if 'note' in r: L.append(f"| {r['name']} | {r['type']} | {r.get('position', '')} | | | | | | | {r['note']} |"); continue
        for clip in ('reload', 'empty_reload'):
            c = r[clip]
            if 'error' in c: L.append(f"| {r['name']} | {r['type']} | {r.get('position', '')} | {clip} | | | | | | error: {c['error']} |"); continue
            parts = '; '.join(f"{n} f{p[0][0]}-{p[0][1]} {p[1]} cm {p[2]} deg {p[3]}{' stays' if p[4] else ''}" for n, p in c['parts'].items()) or 'nothing moves'
            L.append(f"| {r['name']} | {r['type']} | {r.get('position', '')} | {clip} | {c['frames']} | {c['out']} | {c['clear']} | {c['seated']} | {c['leaves']} {c['exit_speed_cm_f']} | {parts} |")
    open(out + '/classify.md', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
