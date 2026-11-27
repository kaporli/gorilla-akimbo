"""Inventory of the game's own player reload clips (the arm sets of weapons.json, plus the dual-wield Lexington set), measured.

usage: vanillainv.py [--out dir] [--guns id,id] [--body pma]
Per clip: frames, magazine events (out = leaves the well, clear = 12 cm out, in_start, seated), gun path (cm, model space),
the left hand's distance to the gun body and to either magazine per frame (palm = middle finger root, gun axes), and the
left hand's actions: strip (palm within MAG_CM of the leaving magazine while it leaves), insert (within MAG_CM of the incoming one
before it seats), handle (within MAG_CM of a gun part that moves), touch frames (palm within TOUCH_CM of the body surface).
One-handed: no touch frame and no action over the whole clip. Writes inventory.json and inventory.md in --out.
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import qrot, qinv
from wclip import TClip, FPS
import gungeo, magpath, dumpanim, classify

TOUCH_CM = 7.0      # palm (middle finger root) to the body surface: a hand on the foregrip reads 3 to 6 cm
MAG_CM = 12.0       # palm to a magazine centre point: the hand holds it
SETS = common.mp('C:/Modding/_tools/gamefiles')
CLIPS = ('reload', 'reload_01', 'reload_02', 'empty_reload', 'empty_reload_01', 'empty_reload_02', 'reload_start', 'reload_loop')


STEM = {'lexington': 'w_handgun__militech_lexington'}        # guns without a mesh entry in weapons.json


def gun_of(gid):
    g = common.gun(gid)
    return dict(g, mesh=STEM[gid]) if 'mesh' not in g and gid in STEM else g


def arm_glb(gun):
    n = os.path.basename(gun['arm_set'].replace('\\', '/')) + '.glb' if gun.get('arm_set') else None
    if not n: return None
    for root in ('gripsets/glb', 'ga-reloads', 'ga-build', 'arm'):
        for dp, dn, fn in os.walk(f'{SETS}/{root}'):
            if n in fn: return os.path.join(dp, n).replace('\\', '/')
    return None


def body_points(gid):
    gun = gun_of(gid); V = []
    for p in gungeo.BODY_PARTS:
        f = common.find('weapon_meshes', f'{gun["mesh"]}__{p}.glb')
        if f: V.append(gungeo.verts(f))
    for p in gun.get('parts') or []:
        f = common.find('weapon_meshes', f'{p}.glb')
        if f: V.append(gungeo.verts(f))
    if not V: return None
    V = np.concatenate(V)
    return V[np.random.RandomState(0).choice(len(V), min(len(V), 6000), replace=False)]


def hands(arm, clip, rel_to='WeaponRight'):
    """Per frame: palm positions of both hands in gun axes, the gun's model-space position, the gun's rotation."""
    c = TClip(Glb(arm), clip); nm = c.names; gi = nm.index(rel_to); out = []; gp = []
    for f in range(c.frames):
        W = c.world(f / FPS); g0, gq = W[gi]; row = {}
        for S in ('Left', 'Right'):
            p = W[nm.index(f'{S}HandMiddle1')][0]; row[S] = qrot(qinv(gq), p - g0)
        sc = W[nm.index('Spine3')]; row['LeftChest'] = qrot(qinv(sc[1]), W[nm.index('LeftHandMiddle1')][0] - sc[0])
        out.append(row); gp.append(qrot(qinv(W[nm.index('Spine3')][1]), np.array(g0, float) - W[nm.index('Spine3')][0]))      # the gun in the chest frame (body sway out)
    return out, np.array(gp), c


def analyse(gid, arm, clip, pts):
    gun = gun_of(gid)
    H, GP, c = hands(arm, clip); n = len(H); L = np.array([h['Left'] for h in H]); R = np.array([h['Right'] for h in H])
    out = {'gun': gid, 'clip': clip, 'frames': n, 'seconds': round((n - 1) / FPS, 2)}
    step = np.linalg.norm(np.diff(GP, axis=0), axis=1) * 100
    out['gun_path_cm'] = round(float(step.sum()), 1); out['gun_peak_cm_f'] = round(float(step.max()), 2)      # chest frame
    out['gun_range_cm'] = round(float(np.linalg.norm(GP - GP[0], axis=1).max()) * 100, 1)
    dL = np.array([np.linalg.norm(pts - l, axis=1).min() * 100 for l in L]) if pts is not None else np.full(n, np.nan)
    dR = np.array([np.linalg.norm(pts - r, axis=1).min() * 100 for r in R]) if pts is not None else np.full(n, np.nan)
    out['left_to_body_cm'] = [round(float(x), 1) for x in dL]; out['right_to_body_cm'] = [round(float(x), 1) for x in dR]
    out['left_touch_frames'] = int((dL < TOUCH_CM).sum()); out['left_min_cm'] = round(float(np.nanmin(dL)), 1) if pts is not None else None
    # magazine events
    mag = None
    try:
        b = gungeo.wanim(gun, 'base1'); m = gungeo.wanim(gun, 'mag_std')
        bs = b if 'mag_slot' in Glb(b).names else gungeo.wanim(gun, 'rcv1')
        if clip in [a['name'] for a in Glb(m).j['animations']]:
            mag = magpath.track(bs, m, clip)
    except Exception as e:
        out['mag_error'] = str(e)[:100]
    acts = []
    if mag:
        for k in ('out', 'clear', 'in_start', 'seated'): out[k] = mag.get(k)
        out['exit_speed_cm_f'] = mag.get('exit_speed_cm_f'); out['exit_dir'] = mag.get('exit_dir'); out['in_dir'] = mag.get('in_dir')
        P = np.array(mag['joints'][mag['leave_joint']]['pos']); Q = np.array(mag['joints'][mag['come_joint']]['pos'])
        # the left hand strips if it is near the magazine while it leaves (frames out..clear+4), inserts if it is near the incoming one in_start..seated
        a0, a1 = mag['out'], (mag.get('clear') or mag['out'] + 4) + 4
        dm = lambda S, F_, X: min(float(np.linalg.norm((L if S == 'L' else R)[min(f, n - 1)] - X[min(f, len(X) - 1)])) * 100 for f in F_)
        if a0 is not None:
            out['left_to_leaving_mag_cm'] = round(dm('L', range(a0, min(a1, n)), P), 1); out['right_to_leaving_mag_cm'] = round(dm('R', range(a0, min(a1, n)), P), 1)
            if out['left_to_leaving_mag_cm'] < MAG_CM: acts.append('strip')
        fi = range(max(mag['seated'] - 4, 0), mag['seated'] + 1)      # the fresh magazine is swapped in by the left hand (it jumps in on the seat frame), so look at the seat
        out['left_to_incoming_mag_cm'] = round(dm('L', fi, Q), 1); out['right_to_incoming_mag_cm'] = round(dm('R', fi, Q), 1)
        if out['left_to_incoming_mag_cm'] < MAG_CM: acts.append('insert')
    # gun parts that move (handle, bolt, flaps): the left hand near them while they move
    handle = []
    try:
        for src in {gungeo.wanim(gun, 'base1'), gungeo.wanim(gun, 'rcv1')} - {None}:
            g = Glb(src)
            if clip not in [a['name'] for a in g.j['animations']]: continue
            cc = TClip(g, clip)
            for name, w in dumpanim.windows(cc).items():
                if name in ('muzzle_slot', 'fx_muzzle', 'pos_ironsight', 'scope_slot', 'mag_slot', 'reload_hinge_right'): continue
                if w['peak_cm'] < 1.0 and w['peak_deg'] < 10: continue
                i = g.names.index(name); fs = range(w['first'], min(w['last'], n - 1) + 1)
                dl = min(float(np.linalg.norm(L[f] - cc.world(f / FPS)[i][0])) * 100 for f in fs); dr = min(float(np.linalg.norm(R[f] - cc.world(f / FPS)[i][0])) * 100 for f in fs)
                handle.append({'part': name, 'window': [w['first'], w['last']], 'move_cm': w['peak_cm'], 'left_cm': round(dl, 1), 'right_cm': round(dr, 1)})
        if any(h['left_cm'] < MAG_CM and h['left_cm'] < h['right_cm'] for h in handle): acts.append('handle')
    except Exception as e:
        out['part_error'] = str(e)[:100]
    out['parts'] = handle; out['left_acts'] = acts
    # the left hand's excursion: frames in which it is more than 20 cm from the body surface (it left the gun)
    LC = np.array([h['LeftChest'] for h in H]); out['left_path_cm'] = round(float(np.linalg.norm(np.diff(LC, axis=0), axis=1).sum()) * 100, 1)      # the left palm's own travel in the chest frame
    out['left_away_frames'] = int((dL > 20).sum())
    away = np.nonzero(dL > 20)[0]; out['left_away'] = [int(away[0]), int(away[-1])] if len(away) else None
    try: out['mag_position'] = classify.position(gungeo.geo(gid) if gid not in STEM else {})
    except Exception as e: out['mag_position'] = '?'
    out['dual_wield'] = 'dual_wield' in os.path.basename(arm)
    out['one_handed'] = bool(out['left_touch_frames'] == 0 and not acts and out['dual_wield'])      # a dual-wield set: the left hand holds its own gun (its clip is the other hand's set); in any other set a hand that never touches the gun is fetching (shells)
    return out


def main(argv):
    o = lambda n, d=None: (argv.pop(argv.index(n) + 1), argv.remove(n))[0] if n in argv else d
    out = o('--out', common.mp('C:/Modding/gg-work/migration/pvanilla/inventory')); only = o('--guns'); os.makedirs(out, exist_ok=True)
    ids = only.split(',') if only else None
    rows = []; sets = []
    for g in common.manifest.guns(all_=True):
        if ids and g['id'] not in ids: continue
        a = arm_glb(g)
        if a: sets.append((g['id'], a))
    seen = {}
    for gid, a in sets:
        if a in seen: continue
        seen[a] = gid
    if not ids or 'lexington' in ids:
        nm = 'pma_w_handgun_dual_wield_right__militech_lexington.anims.glb'      # the dual-wield set: the shipped one-handed reloads are made from it
        for dp, dn, fn in os.walk(SETS + '/ga-build'):
            if nm in fn: seen[os.path.join(dp, nm).replace(chr(92), '/')] = 'lexington'
    for a, gid in seen.items():
        pts = body_points(gid); names = [x['name'] for x in Glb(a).j['animations']]
        for clip in CLIPS:
            if clip not in names: continue
            try: r = analyse(gid, a, clip, pts)
            except Exception as e: print('FAILED', gid, clip, e); continue
            r['arm_set'] = os.path.basename(a); rows.append(r)
            print(gid, clip, r['frames'], 'touch', r['left_touch_frames'], 'acts', r['left_acts'], 'min', r['left_min_cm'], flush=True)
    json.dump(rows, open(out + '/inventory.json', 'w'), indent=1)
    return rows


if __name__ == '__main__':
    main(sys.argv[1:])
