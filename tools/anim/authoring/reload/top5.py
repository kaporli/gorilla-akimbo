"""SMG TOP family, round 5: warden, take B, right hand, male V, empty reload. Replacement round for ST32B after round 4 (pst32) was rejected as too slow and too light.
Releases are arm mechanics only (no in-hand spins): the arm drives the gun along the magazine's exit line and stops it dead, as ST38B (onto the thigh) and ST40B (thrust forward) do,
so the magazine leaves at the gun's speed (r2lib well model). Loads as round 4: the fresh magazine waits on its carrier, is carried by the gun hand, or falls at g.
Stations are moved out of the body, never the travel shortened (R5, R8 bound the speed and path from below).
Same beats as round 3 (take B: release f21, seat f43, hit f61, idle f70).

usage: top5.py list | build [ids] [--jobs n] | stats | gates
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r3lib, author, top3, top4
from r3lib import seat, rack, PUNCH
from r2lib import opener
from top3 import PIV, hold_at, slap_load, mag, AXES, world_to_gun
from top4 import upright_add

FAMILY = 'TOP'; GUN = 'warden'; TAKE = 'B'; PREFIX = 'ST'
STATIONS = dict(top4.STATIONS)

def rot_for(c, direction, guess):
    """Station angles (deg) near `guess` whose magazine exit axis points along the world vector `direction` (the gun's other freedom, the roll about that axis, stays where the guess has it)."""
    from scipy.optimize import minimize
    t = np.array(direction, float); t = t / np.linalg.norm(t); g = np.array(guess, float)
    err = lambda a: float(np.linalg.norm(c.along(a, c.v['exit'], 1.0) - t)) + 1e-4 * float(np.linalg.norm(a - g))
    return tuple(minimize(err, g, method='Nelder-Mead', options={'xatol': 0.01, 'fatol': 1e-9, 'maxiter': 2000}).x)


def arm_release(c, tl, stop, sr, wr, drop=0.18, first=2, arrive=None, wind_hold=None, wait=0):
    """The arm winds the gun up to (stop - exit * drop, wr), holds, then drives it `drop` m along the magazine's exit line and stops it dead on the release frame at `stop`, angles sr
    (aligned: the magazine centre travels along the exit axis); the magazine keeps the gun's speed (well model). The hand guides the gun through the stop, a jolt follows (as ST38, ST40)."""
    B = c.B; r = B['rel']; stop = np.array(stop, float); wu = stop - c.along(sr, c.v['exit'], drop)
    tl.hold(first); tl.to(arrive or r - 7, wu, wr, 'drive', rlag=1); tl.hold(wind_hold or r - 5)
    tl.to(r, r3lib.aligned(c, wu, wr, sr, drop), sr, 'slam', rlag=0); tl.locks.append((r - 1, r + 1)); tl.impulse(r + 1, -c.along(sr, c.v['exit'], 0.010), (3, 0, 0))
    tl.mark('release', r); tl.nodrag.append((r - 5, r + 1)); return wu


def rack5(c, tl, kind, fast=0):
    """r2lib.rack with the rise from the seat to the held pose starting `fast` frames later (the same travel in fewer frames: faster; the gun stays down longer), the held pose, hit and idle on the same beats."""
    from r2lib import rack as _rack
    B = c.B; saved = B['rise']; B['rise'] = saved + fast
    try: _rack(c, tl, kind)
    finally: B['rise'] = saved


def slap_load5(c, tl, rig, thigh, pick, part=0.04, rack_kind='punch', fast=0):
    """top3.slap_load with rack5 (the gun takes the fresh magazine half on at the rig on the pick frame, lifts it, drives it magazine first into the anvil: it goes home on that impact)."""
    B = c.B; P = c.P; rp, rr = c.station(rig); tp, trot = c.station(thigh)
    pre = np.array(rp) + c.along(rr, c.v['enter'], 0.15 + part); at = np.array(rp) + c.along(rr, c.v['enter'], part)
    tl.to(pick - 5, pre, rr, 'ease', rlag=P['lag'] + 1); tl.to(pick, at, rr, 'slam', rlag=0); tl.locks.append((pick - 5, pick))
    up = np.array(tp) + c.along(trot, c.v['enter'], 0.12); tl.to(B['slam'], up, trot, 'ease', rlag=1)
    tl.to(B['seat'], tp, trot, 'slam', rlag=0); tl.locks.append((B['slam'] + 2, B['seat']))
    tl.impulse(B['seat'], c.along(trot, c.v['enter'], 0.016), (-3, 0, 0)); tl.mark('pick', pick); tl.mark('seat', B['seat'])
    rack5(c, tl, rack_kind, fast)


FAST = 4          # the rise to the held pose starts this many frames later than the beat (the same travel in fewer frames)
S = lambda c, n, d=(0, 0, 0): np.array(c.station(n)[0]) + d


def slapm(c, **k):
    B = c.B; return mag(c, appear=B['arr'] - 4, fresh={'mode': 'slap', 'pick': B['arr'], 'part': 0.04, 'carry': 0.03}, **k)


def drive(c, tl, stop, sr, add, drop=0.32, arr=11):
    """Long arm drive: wind-up to (stop - exit * drop) by release - arr, then the drive along the magazine's exit line, stopped dead on the release frame."""
    r = c.B['rel']; tl.mark('cue', 3); return arm_release(c, tl, stop, sr, np.array(sr) + add, arrive=r - arr, wind_hold=r - 7, drop=drop)


def fall(c, tl, r, dep=6):
    seat(c, tl, 'belt_flat', dep=r + dep, mode='drop', jolt_vec=(0, -0.016, 0), rot_add=upright_add(c, 'belt_flat'))


def st54(c, tl):
    """Low drive, pouch press. The arm lifts the gun, turned over, back and up beside the hip, then drives it down and forward along the magazine's line, stopping it dead low in front of the thigh: the magazine, now underneath, carries on down off the rail. Still turned over, the gun goes down onto the fresh magazine standing in the belt pouch (it jolts on the seat). Rolled upright on the way up, cocked low, a rising punch on the cocking device."""
    B = c.B; r = B['rel']; drive(c, tl, S(c, 'thigh_t', (0.0, 0.0, -0.14)), (-20, 0, 180), (8, 0, -4), 0.30)
    seat(c, tl, 'belt_tl', dep=r + 4); rack5(c, tl, 'upper', FAST); return mag(c, fresh={'mode': 'still'})


def st55(c, tl):
    """Belly drive, thigh slap. The gun, turned over and canted, is heaved back and up and driven steeply down in front of the belly, stopped dead: the magazine leaves downward off the underside. The gun takes the fresh magazine half on at the belt rig and is slapped top first against the thigh to seat it. Up, cocked low, a rising punch on the cocking device."""
    B = c.B; r = B['rel']; sr = rot_for(c, (-0.3, -0.94, -0.1), (-45, 0, 170)); drive(c, tl, S(c, 'belly_t', (0.0, 0.12, -0.14)), sr, (6, 0, -4))
    tl.hold(r + 2); slap_load5(c, tl, 'belt_t', 'thigh_m', B['arr'], rack_kind='upper', fast=FAST); return slapm(c)


def st56(c, tl):
    """Outward drive, pouch press. Turned over and canted out, the gun is swung back and up and driven down and out to the right along the magazine's line, stopped dead beside the hip: the magazine flies off to the right and down. The gun comes round and down onto the fresh magazine standing in the belt pouch (it jolts on the seat). Up, held muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; sr = rot_for(c, (0.6, -0.74, -0.21), (-43, -16, -123)); drive(c, tl, S(c, 'thigh_t', (0.12, -0.01, -0.16)), sr, (0, 0, 4), 0.34, 12)
    seat(c, tl, 'belt_tl', dep=r + 5); rack5(c, tl, 'nod', FAST); return mag(c, fresh={'mode': 'still'})


def st57(c, tl):
    """Forward lunge, fall-on. The gun is drawn back toward the chest and driven straight forward along the magazine's line, stopped dead at arm's length: the magazine flies on ahead. The gun goes down to the belt, turned upright and held still with the well up; a rig above lets go of the fresh magazine and it falls straight onto the top at g (the gun jolts down as it lands). Up, held out in front and yanked back on the cocking device."""
    B = c.B; r = B['rel']; sr = rot_for(c, (0, 0.1, -1), (-24, 0, -10)); drive(c, tl, (0.05, -0.14, 0.0), sr, (6, 0, 3), 0.32)
    fall(c, tl, r); rack5(c, tl, 'yank', FAST); return mag(c, fresh={'mode': 'fall', 'n': 5})


def st58(c, tl):
    """Overhand lunge, driven up under. The gun, turned over, is cocked back and up and thrown forward and down along the magazine's line, stopped dead: the magazine flies off forward and down. The gun goes down in front of the stomach and is driven up under the fresh magazine hanging still from the belt-front rig (it jolts on the seat). Up, held out in front and yanked back on the cocking device."""
    B = c.B; r = B['rel']; sr = rot_for(c, (0, -0.71, -0.71), (-4, 0, 191)); drive(c, tl, (0.10, -0.10, -0.04), sr, (6, 0, -4), 0.35, 12)
    seat(c, tl, 'under_t', d=0.12, dep=r + 5); rack5(c, tl, 'yank', FAST); return mag(c)


def st59(c, tl):
    """Overhand lunge, belly slap. The gun, turned over, is cocked back and up and thrown forward and down along the magazine's line, stopped dead: the magazine flies off forward and down. The gun takes the fresh magazine half on at the belt rig and is slapped top first against the belly in front of the buckle to seat it. Up, cocked back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; sr = rot_for(c, (0, -0.71, -0.71), (-4, 0, 191)); drive(c, tl, (0.10, -0.10, -0.04), sr, (6, 0, -4))
    tl.hold(r + 2); slap_load5(c, tl, 'belt_t', 'belly_t', B['arr'], rack_kind='punch', fast=FAST); return slapm(c)


def st60(c, tl):
    """Hip drive, driven up under. The gun, turned over, is swung back and up and driven down in front of the hip along the magazine's line, stopped dead: the magazine leaves downward off the underside. The gun is brought upright in front of the stomach and driven up under the fresh magazine hanging still from the belt-front rig (it jolts on the seat). Up, held muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; drive(c, tl, S(c, 'thigh_t', (0.03, 0.07, -0.10)), (-20, 0, 180), (8, 0, -4), 0.30)
    seat(c, tl, 'under_t', d=0.12, dep=r + 5); rack5(c, tl, 'nod', FAST); return mag(c)


def st61(c, tl):
    """Forward lunge, driven up under. The gun is drawn back toward the chest and driven straight forward along the magazine's line, stopped dead at arm's length: the magazine flies on ahead. The gun goes down in front of the stomach and is driven up under the fresh magazine hanging still from the belt-front rig (it jolts on the seat). Up, cocked low, a rising punch on the cocking device."""
    B = c.B; r = B['rel']; sr = rot_for(c, (0, 0.1, -1), (-24, 0, -10)); drive(c, tl, (0.05, -0.14, 0.0), sr, (6, 0, 3), 0.32)
    seat(c, tl, 'under_t', d=0.12, dep=r + 5); rack5(c, tl, 'upper', FAST); return mag(c)


def st62(c, tl):
    """Belly drive, fall-on. The gun, turned over and canted, is heaved back and up and driven steeply down in front of the belly, stopped dead: the magazine leaves downward off the underside. The gun is turned back upright at the belt and held still with the well up; a rig above lets go of the fresh magazine and it falls straight onto the top at g (the gun jolts down as it lands). Up, cocked low, a rising punch on the cocking device."""
    B = c.B; r = B['rel']; sr = rot_for(c, (-0.3, -0.94, -0.1), (-45, 0, 170)); drive(c, tl, S(c, 'belly_t', (0.0, 0.12, -0.14)), sr, (6, 0, -4), 0.35, 12)
    fall(c, tl, r, 7); rack5(c, tl, 'upper', FAST); return mag(c, fresh={'mode': 'fall', 'n': 5})


def st63(c, tl):
    """Cross lunge, pouch press. The gun is drawn back and driven forward and slightly across the body along the magazine's line, stopped dead at arm's length: the magazine flies on ahead. The gun turns over on the way down and is pressed onto the fresh magazine standing in the belt pouch (it jolts on the seat). Rolled upright on the way up, cocked back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; sr = rot_for(c, (-0.15, -0.1, -0.98), (-30, 5, -10)); drive(c, tl, (0.02, -0.14, 0.0), sr, (6, 0, 3), 0.32)
    seat(c, tl, 'belt_t', dep=r + 6); rack5(c, tl, 'punch', FAST); return mag(c, appear=B['arr'] - 4)


MECH = {'ST54': 'Release: the arm drives the turned-over gun down and forward and stops it dead low in front of the thigh; the magazine carries on down off the rail. Load: the turned-over gun is pressed down onto the magazine standing in the belt pouch.',
        'ST55': 'Release: the arm drives the turned-over gun steeply down in front of the belly and stops it dead; the magazine leaves downward. Load: the gun carries the fresh magazine half on and slaps it home on the thigh.',
        'ST56': 'Release: the arm drives the turned-over gun down and out to the right and stops it dead beside the hip; the magazine flies off right and down. Load: the gun is pressed down onto the magazine standing in the belt pouch.',
        'ST57': "Release: the arm drives the gun straight forward and stops it dead at arm's length; the magazine flies on ahead. Load: the gun waits upright at the belt and the rig above lets go of the fresh magazine, which falls onto the top at g.",
        'ST58': 'Release: the arm throws the turned-over gun forward and down and stops it dead; the magazine flies forward and down. Load: the gun is driven up under the fresh magazine hanging still from the belt-front rig.',
        'ST59': 'Release: the arm throws the turned-over gun forward and down and stops it dead; the magazine flies forward and down. Load: the gun carries the fresh magazine half on and slaps it home against the belly.',
        'ST60': 'Release: the arm drives the turned-over gun down in front of the hip and stops it dead; the magazine leaves downward. Load: the gun is driven up under the fresh magazine hanging still from the belt-front rig.',
        'ST61': "Release: the arm drives the gun straight forward and stops it dead at arm's length; the magazine flies on ahead. Load: the gun is driven up under the fresh magazine hanging still from the belt-front rig.",
        'ST62': 'Release: the arm drives the turned-over gun steeply down in front of the belly and stops it dead; the magazine leaves downward. Load: the gun waits upright at the belt and the rig above lets go of the fresh magazine, which falls onto the top at g.',
        'ST63': "Release: the arm drives the gun forward and slightly across the body and stops it dead at arm's length; the magazine flies on ahead. Load: the turned-over gun is pressed down onto the magazine standing in the belt pouch."}
PICKS = {'ST54': ('Low drive, pouch press', st54), 'ST55': ('Belly drive, thigh slap', st55), 'ST56': ('Outward drive, pouch press', st56), 'ST57': ('Forward lunge, fall-on', st57),
         'ST58': ('Overhand lunge, driven up under', st58), 'ST59': ('Overhand lunge, belly slap', st59), 'ST60': ('Hip drive, driven up under', st60), 'ST61': ('Forward lunge, driven up under', st61),
         'ST62': ('Belly drive, fall-on', st62), 'ST63': ('Cross lunge, pouch press', st63)}
PARAMS = {}

if __name__ == '__main__': r3lib.main(sys.modules[__name__], sys.argv[1:])
