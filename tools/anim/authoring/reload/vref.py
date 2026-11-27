"""Measured events and gun path of a vanilla reload clip, for vtop.py (one-handed drafts from vanilla reloads).

ref(id) -> dict, cached in <OUT>/vref/<id>.json:
  frames        clip length (30 fps frames)
  T, Q          WeaponRight world position (m, model space) and rotation (xyzw) per frame
  out, seated   frame the magazine leaves the well, frame the fresh one is home (gun's own anim sets; Warden seated 77 as r2lib.gun_events)
  exit_dir, exit_cm_f   magazine exit axis in gun axes, mean speed over its first 12 cm (cm per vanilla frame)
  pick, pick_p  frame the left palm is farthest from the chest while it is away from the gun, and its model-space position there (None: no left hand action)
  away          [first, last] frame the left palm is more than 20 cm from the gun body (None: never)
  handle        [first, last] frame window of the part that moves after the seat (cocking device, bolt), its move (cm) and direction (gun axes)
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
import vanillainv as VI
from glb import Glb
from wclip import TClip, FPS
from fk import qrot, qinv

# id -> (gun, arm set owner gun id, clip, label); one-handed sets first
REFS = {'SV01': ('lexington', 'empty_reload', 'Lexington dual wield'), 'SV02': ('lexington', 'empty_reload_01', 'Lexington dual wield'), 'SV03': ('lexington', 'empty_reload_02', 'Lexington dual wield'),
        'SV04': ('warden', 'empty_reload', 'Warden'), 'SV05': ('warden', 'empty_reload_01', 'Warden'), 'SV06': ('warden', 'empty_reload_02', 'Warden'),
        'SV07': ('lexington', 'reload', 'Lexington dual wield'), 'SV08': ('lexington', 'reload_01', 'Lexington dual wield'), 'SV09': ('lexington', 'reload_02', 'Lexington dual wield'),
        'SV10': ('warden', 'reload', 'Warden'), 'SV11': ('warden', 'reload_01', 'Warden'), 'SV12': ('warden', 'reload_02', 'Warden'),
        'SV13': ('shingen', 'empty_reload', 'Shingen'), 'SV14': ('shingen', 'empty_reload_01', 'Shingen'), 'SV15': ('shingen', 'empty_reload_02', 'Shingen'),
        'SV16': ('borg', 'empty_reload', 'Borg')}


def arm_of(gid):
    if gid == 'lexington':
        for dp, dn, fn in os.walk(VI.SETS + '/ga-build'):
            if 'pma_w_handgun_dual_wield_right__militech_lexington.anims.glb' in fn: return os.path.join(dp, 'pma_w_handgun_dual_wield_right__militech_lexington.anims.glb').replace(chr(92), '/')
    return VI.arm_glb(common.gun(gid))


def ref(rid, force=False):
    d = renv.OUT + '/vref'; p = f'{d}/{rid}.json'
    if os.path.exists(p) and not force: return json.load(open(p))
    gid, clip, label = REFS[rid]; arm = arm_of(gid); pts = VI.body_points(gid)
    r = VI.analyse(gid, arm, clip, pts)
    c = TClip(Glb(arm), clip); nm = c.names; gi = nm.index('WeaponRight'); ch = nm.index('Spine3'); ph = nm.index('LeftHandMiddle1')
    T, Q, PL, CH = [], [], [], []
    for f in range(c.frames):
        W = c.world(f / FPS); T.append(W[gi][0]); Q.append(W[gi][1]); PL.append(W[ph][0]); CH.append(W[ch][0])
    T, Q, PL, CH = np.array(T), np.array(Q), np.array(PL), np.array(CH)
    out = {'id': rid, 'gun': gid, 'clip': clip, 'label': label, 'arm_set': os.path.basename(arm), 'frames': c.frames, 'T': T.round(5).tolist(), 'Q': Q.round(6).tolist(),
           'out': r.get('out'), 'seated': r.get('seated'), 'exit_dir': r.get('exit_dir'), 'exit_cm_f': r.get('exit_speed_cm_f'), 'left_acts': r['left_acts'], 'one_handed': r['one_handed'],
           'mag_position': r.get('mag_position'), 'away': r.get('left_away')}
    if gid == 'warden': out['seated'] = 77      # r2lib.gun_events: the fresh magazine rocks home as the latch shuts
    a = r.get('left_away')
    if a and not r['one_handed']:
        dd = np.linalg.norm(PL[a[0]:a[1] + 1] - CH[a[0]:a[1] + 1], axis=1); k = a[0] + int(np.argmax(dd)); out['pick'] = k; out['pick_p'] = PL[k].round(4).tolist()
    parts = [x for x in r.get('parts', []) if x['window'][0] >= (out['seated'] or 0) - 2 and x['move_cm'] >= 1.0]
    if parts:
        x = max(parts, key=lambda x: x['move_cm']); out['handle'] = {'part': x['part'], 'window': x['window'], 'move_cm': x['move_cm']}
        g = common.gun(gid); import gungeo
        try:
            for src in {gungeo.wanim(g, 'base1'), gungeo.wanim(g, 'rcv1')} - {None}:
                import dumpanim
                gg = Glb(src); cl = [a_['name'] for a_ in gg.j['animations']]
                if clip not in cl: continue
                w = dumpanim.windows(TClip(gg, clip)).get(x['part'])
                if w: out['handle']['dir'] = w['dir']
        except Exception as e: out['handle']['dir_error'] = str(e)[:80]
    os.makedirs(d, exist_ok=True); json.dump(out, open(p, 'w'))
    return out


if __name__ == '__main__':
    for rid in (sys.argv[1:] or REFS):
        r = ref(rid, True); print(rid, r['gun'], r['clip'], 'frames', r['frames'], 'out', r['out'], 'seated', r['seated'], 'exit', r['exit_dir'], r['exit_cm_f'], 'pick', r.get('pick'), r.get('pick_p'), 'away', r['away'], 'handle', r.get('handle'), 'one-handed', r['one_handed'])
