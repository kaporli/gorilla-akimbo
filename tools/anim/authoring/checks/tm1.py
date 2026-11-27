"""TM1 (reload time): the hidden window absorbs the stat time. Measures for one clip (paudit/TIMING.md section 3):
  state_f          round(30 * (S + FB)) with S = reload + end (empty: empty + empty end) from reload.stats and FB the script's FireBuffer: the frame the rise has to settle on at runtime
  hidden_avail_f   the hidden window available at that settle: state_f - hide_start - (settle - hide_end)   (the visible start and the rise are played at speed 1, only the hidden part is stretched or cut)
  hidden_cut_rate  hidden frames of the clip over hidden_avail_f: the speed the script plays the hidden part at (a stretch is below 1); at most the script's MaxSpeed
  visible_identical  frames of the clip against the control (the shipped clip): 0 added or removed frames, so the visible start and end are the control's
settle is the frame after which the reloading arm stays within 1 deg of the last frame (the measure genguns writes into ReloadSettle)."""
import os, json, math


def settle_frames(glb_path, tol=1.0):
    import numpy as np
    from glb import Glb
    if not os.path.exists(glb_path): return None
    g = Glb(glb_path); side = 'Left' if '_left_' in os.path.basename(glb_path) else 'Right'; t = g.tracks(g.j['animations'][0]['name']); worst = None
    for b in ('Shoulder', 'Arm', 'ForeArm', 'Hand'):
        k = (side + b, 'rotation')
        if k in t:
            v = t[k][1]; a = np.degrees(2 * np.arccos(np.abs(np.sum(v * v[-1][None], axis=-1)).clip(0, 1))); worst = a if worst is None else np.maximum(worst, a)
    if worst is None: return None
    moving = np.nonzero(worst > tol)[0]
    return int(moving[-1]) + 1 if len(moving) else 0


def measure(glb, gate, gun, clip, frames, stats, T, control_frames):
    """dict of the TM1 numbers, or {'note': why not measurable}."""
    lay = (gate or {}).get('layout') or {}
    if not stats: return {'note': 'no reload.stats for this gun (not in the TweakDB dump)'}
    hs, he = lay.get('hide_start'), lay.get('hide_end'); se = settle_frames(glb)
    if hs is None or he is None or se is None: return {'note': 'no hidden window or settle in the clip'}
    S = (stats['empty_s'] + stats['empty_end_s']) if clip == 'empty_reload' else (stats['reload_s'] + stats['end_s'])
    state_f = round(30.0 * (S + T['fire_buffer_s'])); avail = state_f - hs - (se - he); nat = he - hs
    return {'state_f': state_f, 'settle_f': se, 'hide_start': hs, 'hide_end': he, 'hidden_natural_f': nat, 'hidden_avail_f': avail, 'hidden_cut_rate': round(nat / avail, 3) if avail > 0 else 99.0,
            'visible_identical': None if control_frames is None else abs(frames - control_frames)}
