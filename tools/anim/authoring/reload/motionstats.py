"""Speed and acceleration profile of the gun in an arm clip: how it moves, not where.

usage: motionstats.py <label>=<glb>:<clip>[:<Right|Left>[:<muzzle metres>]] ... [--json out.json] [--plot out.png]
module: stats(glb, clip, side='Right', muzzle=0.55) -> dict

Sampled at 30 fps by time. Grip = the weapon bone; muzzle = a point `muzzle` metres in front of it on the gun.
  speed          grip speed per frame (cm/frame); muzzle_speed the same for the muzzle point
  moves          runs of frames with grip speed over 0.6 cm/frame: start, end, length, distance, peak speed,
                 peak_at (0..1, where in the move the peak is: early = fast attack, late = accelerates into the stop),
                 stop (cm/frame lost in the last 2 frames of the move: a hard stop is large)
  attack_frames  frames from the start of a move to 80 % of its peak speed (mean over moves of 8 cm and more)
  peak_at        distance-weighted mean of peak_at over those moves
  peak_speed     largest grip speed; p90_speed
  peak_acc       largest change of grip speed vector per frame (cm/frame^2), and where
  jerk_events    frames where the speed vector changes by more than 2.5 cm/frame^2 (hits, hard stops, snaps)
  holds          runs of 4 or more frames under 0.25 cm/frame (start, length); hold_share of the clip
  lag_deg        mean angle the muzzle direction trails the grip's travel in fast frames (follow-through): the
                 angle between gun forward and travel direction is not used; instead muzzle_speed / speed ratio:
  whip           mean muzzle speed over mean grip speed in moving frames (1 = rigid translation, more = the rifle
                 swings about the hand)
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import numpy as np
from glb import Glb
from fk import qrot
from wclip import TClip, FPS


def track(glb, clip, side='Right', muzzle=0.55):
    c = TClip(Glb(glb), clip); i = c.names.index(f'Weapon{side}'); G = []; M = []
    for f in range(c.frames):
        t, q = c.wf(f)[i]; G.append(t); M.append(t + qrot(q, np.array([0, 0, -muzzle])))
    return np.array(G), np.array(M)


def stats(glb, clip, side='Right', muzzle=0.55):
    G, M = track(glb, clip, side, muzzle); n = len(G)
    V = np.diff(G, axis=0) * 100; sp = np.r_[0, np.linalg.norm(V, axis=1)]; ms = np.r_[0, np.linalg.norm(np.diff(M, axis=0), axis=1) * 100]
    A = np.r_[0, 0, np.linalg.norm(np.diff(V, axis=0), axis=1)]
    moves = []; f = 1
    while f < n:
        if sp[f] > 0.6:
            k = f
            while k + 1 < n and sp[k + 1] > 0.6: k += 1
            seg = sp[f:k + 1]; pk = int(np.argmax(seg)); L = k - f + 1
            att = next((j for j in range(L) if seg[j] >= 0.8 * seg[pk]), 0) + 1
            moves.append({'start': f, 'end': k, 'frames': L, 'dist': round(float(seg.sum()), 1), 'peak': round(float(seg[pk]), 1),
                          'peak_at': round((pk + 0.5) / L, 2), 'attack': att, 'stop': round(float(seg[max(L - 3, 0)] - (sp[k + 1] if k + 1 < n else 0)), 1)})
            f = k + 1
        else: f += 1
    big = [m for m in moves if m['dist'] >= 8]
    holds = []; f = 0
    while f < n:
        if sp[f] < 0.25:
            k = f
            while k + 1 < n and sp[k + 1] < 0.25: k += 1
            if k - f + 1 >= 4: holds.append([f, k - f + 1])
            f = k + 1
        else: f += 1
    mv = sp > 0.6
    w = sum(m['dist'] for m in big) or 1
    return {'frames': n, 'speed': [round(float(x), 2) for x in sp], 'muzzle_speed': [round(float(x), 2) for x in ms], 'acc': [round(float(x), 2) for x in A],
            'moves': moves, 'big_moves': len(big), 'peak_speed': round(float(sp.max()), 1), 'p90_speed': round(float(np.percentile(sp[mv], 90)) if mv.any() else 0, 1),
            'mean_move_speed': round(float(sp[mv].mean()) if mv.any() else 0, 1),
            'peak_at': round(sum(m['peak_at'] * m['dist'] for m in big) / w, 2) if big else None,
            'attack_frames': round(float(np.mean([m['attack'] for m in big])), 1) if big else None,
            'stop': round(float(np.mean([m['stop'] for m in big])), 1) if big else None,
            'peak_acc': [round(float(A.max()), 1), int(np.argmax(A))], 'jerk_events': int((A > 2.5).sum()), 'jerk_frames': [int(x) for x in np.where(A > 2.5)[0]][:30],
            'holds': holds, 'hold_share': round(sum(h[1] for h in holds) / n, 2), 'moving_share': round(float(mv.mean()), 2),
            'whip': round(float(ms[mv].mean() / sp[mv].mean()), 2) if mv.any() else None, 'peak_muzzle_speed': round(float(ms.max()), 1)}


def plot(rows, out):
    """One strip per clip: grip speed (white), muzzle speed (orange), acceleration spikes (red ticks)."""
    from PIL import Image, ImageDraw, ImageFont
    try: ft = ImageFont.truetype('arial.ttf', 14); fb = ImageFont.truetype('arialbd.ttf', 15)
    except OSError: ft = fb = ImageFont.load_default()
    W, H, L = 1500, 120, 330; top = 44; S = Image.new('RGB', (W, top + H * len(rows)), (22, 24, 28)); d = ImageDraw.Draw(S)
    d.text((10, 6), 'Gun speed per frame (30 fps). White: grip, orange: muzzle, red ticks: speed vector changes over 2.5 cm/frame^2 (hits, hard stops). Scale: 12 cm/frame full height, 2 px per frame.', fill=(230, 230, 230), font=ft)
    d.text((10, 24), 'Numbers: peak grip speed | where in a big move the peak is (0 = start, 1 = end) | frames to 80 % of peak | jerk events | share of the clip standing still', fill=(170, 175, 185), font=ft)
    for r, (lab, s) in enumerate(rows):
        y0 = top + r * H; base = y0 + H - 14; d.line((L, base, W - 10, base), fill=(70, 74, 82))
        for v in (4, 8): d.line((L, base - v * 7.5, W - 10, base - v * 7.5), fill=(44, 47, 54)); d.text((L - 22, base - v * 7.5 - 7), str(v), fill=(110, 115, 125), font=ft)
        d.text((8, y0 + 8), lab, fill=(255, 220, 0), font=fb)
        d.text((8, y0 + 30), f"peak {s['peak_speed']}  peak at {s['peak_at']}  attack {s['attack_frames']} f", fill=(220, 220, 220), font=ft)
        d.text((8, y0 + 48), f"jerks {s['jerk_events']}  still {int(s['hold_share'] * 100)} %  whip {s['whip']}", fill=(220, 220, 220), font=ft)
        d.text((8, y0 + 66), f"{s['frames']} frames, {s['big_moves']} big moves", fill=(150, 155, 165), font=ft)
        for key, col in (('muzzle_speed', (240, 130, 50)), ('speed', (240, 240, 240))):
            pts = [(L + 2 * f, base - min(v, 13.5) * 7.5) for f, v in enumerate(s[key])]
            if len(pts) > 1: d.line(pts, fill=col, width=2 if key == 'speed' else 1)
        for f in s['jerk_frames']: d.line((L + 2 * f, base + 2, L + 2 * f, base + 10), fill=(230, 50, 50), width=2)
    S.save(out); print('wrote', out)


if __name__ == '__main__':
    argv = sys.argv[1:]; jo = common.opt(argv, '--json'); po = common.opt(argv, '--plot'); rows = []
    for a in argv:
        lab, rest = a.split('=', 1); parts = rest.rsplit(':', 3) if rest.count(':') >= 4 else rest.split(':')
        if len(parts[0]) == 1: parts = [parts[0] + ':' + parts[1]] + parts[2:]   # drive letter
        g, clip = parts[0], parts[1]; side = parts[2] if len(parts) > 2 else 'Right'; mz = float(parts[3]) if len(parts) > 3 else 0.55
        s = stats(g, clip, side, mz); rows.append((lab, s))
        print(f"{lab:34s} {s['frames']:4d}f peak {s['peak_speed']:5.1f} p90 {s['p90_speed']:4.1f} mean {s['mean_move_speed']:4.1f} peak_at {s['peak_at']} attack {s['attack_frames']} stop {s['stop']} "
              f"acc {s['peak_acc']} jerks {s['jerk_events']} still {s['hold_share']} moving {s['moving_share']} whip {s['whip']} muzzle peak {s['peak_muzzle_speed']}")
    if jo: json.dump({l: s for l, s in rows}, open(jo, 'w'))
    if po: plot(rows, po)
