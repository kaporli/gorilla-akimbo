"""SMG TOP family, round 4: warden, take B, right hand, male V, empty reload. Replacement round for ST32B (the pop-up
rig pushed the fresh magazine 12 cm into a gun waiting at the seat pose). Here the fresh magazine is never moved by
anything that does not touch it: it waits still on its carrier (rig), is carried by the gun's hand, or falls at g
(fall mode: a rig above lets go of it from rest over the waiting gun). The gun comes onto it.
Releases and load beats are round 3's (same beats: release f21, seat f43, hit f61, idle f70).

usage: top4.py list | build [ids] [--jobs n] | stats | gates
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r3lib, author, top3
from r3lib import seat, rack, PUNCH
from r2lib import opener
from top3 import PIV, hold_at, slap_load, mag, AXES

FAMILY = 'TOP'; GUN = 'warden'; TAKE = 'B'; PREFIX = 'ST'
STATIONS = dict(top3.STATIONS)
STATIONS.update({'belly_t': ((0.20, 0.17, -0.16), (-30, 0, 170)),
                 'under_t': ((0.35, 0.25, -0.19), (-10, 20, 0)),                   # upright, driven up under a magazine hanging from the belt front (stomach_t, 11 cm further out: clear of the body)
                 'thigh_m': ((0.36, 0.19, -0.03), (-60, 0, 90))})                # the thigh anvil, 2 cm further out than thigh_t        # in front of the belly, turned over: the anvil of a slap


def upright_add(c, station, down=(0.0, -1.0, 0.0)):
    """Extra station angles (deg) that turn the well's entry axis onto the vertical: a magazine falling at g falls straight down, so the gun waiting for it must have its well vertical."""
    from scipy.optimize import minimize
    pos, rot = c.station(station); rot = np.array(rot, float); t = np.array(down, float)
    err = lambda a: float(np.linalg.norm(c.along(rot + a, c.v['enter'], 1.0) - t))
    return tuple(minimize(err, np.zeros(3), method='Nelder-Mead', options={'xatol': 0.01, 'fatol': 1e-9}).x)


def st44(c, tl):
    """Slow roll-off, down onto the pouch. Low in front of the belly the gun is turned over in the fingers, slowly; as the top passes the side the magazine slides off its rail by its own weight
    and falls. The gun stays upside down, goes down to the belt and is driven down onto the fresh magazine standing in the pouch (it jolts on the seat). The other half of the turn
    brings it upright on the way up. Up, held out in front and yanked back on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, -0.04, -0.06), (-4, 0, 0))
    tl.spin(r - 8, r + 4, -180, (0, 0, 1), PIV, (2.0, 2.0)); tl.spin(B['rise'], B['mid'] + 2, -180, (0, 0, 1), PIV, (2.0, 2.0))
    tl.mark('release', r); tl.mark('cue', r - 8)
    seat(c, tl, 'belt_flat', d=0.15, dep=r + 8, flip=True); rack(c, tl, 'yank')
    return mag(c, spin_release=True, spin_why='released in a slow in-hand turn: it slides off by its weight as the top passes the side', appear=B['arr'] - 2, fresh={'mode': 'still'})


def st45(c, tl):
    """Barrel spin, fall-on. Up in front of the chest the gun is spun a full turn in the fingers about its own barrel; near full speed the magazine is thrown off its rail and flies out to the right and forward.
    Down at the belt, upright and held still, a rig above lets go of the fresh magazine and it falls straight onto the top (the gun jolts down as it lands).
    Up, cocked back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, 0.03, -0.06), (0, 0, 0))
    tl.spin(r - 4, r + 6, 360, (0, 0, 1), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'belt_flat', dep=r + 5, mode='drop', jolt_vec=(0, -0.016, 0), rot_add=upright_add(c, 'belt_flat')); rack(c, tl, 'punch')
    return mag(c, spin_release=True, fresh={'mode': 'fall', 'n': 5})


def st46(c, tl):
    """Finger hang, driven up under the hanging magazine. The grip is let go and the gun swings muzzle-down on the trigger finger, hanging from it with the top facing forward and down; the release is pressed
    and the magazine slides off the top by its own weight. The gun swings back up into the palm, goes down in front of the stomach and is driven up under the fresh magazine hanging still from the
    belt-front rig (it jolts on the seat). Up, held muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, 0.0, -0.06), (0, 0, -4))
    tl.spin(r - 7, r - 2, -110, (1, 0, 0), PIV, (2.0, 2.0)); tl.spin(r + 4, r + 11, 110, (1, 0, 0), PIV, (2.0, 2.0))
    tl.mark('release', r); tl.mark('cue', r - 7)
    seat(c, tl, 'under_t', d=0.12, dep=r + 5); rack(c, tl, 'nod')
    return mag(c)


def _pop(c, tl, dist=0.10):
    """Pop and catch: the gun is rolled onto its right side, popped up out of the palm along the magazine's line and caught dead; the magazine carries on off the rail."""
    B = c.B; r = B['rel']; rot = (-6, 0, -60); p0 = np.array((0.03, -0.13, 0.05)); e = c.along(rot, c.v['exit'], 1.0); hold_at(c, tl, 2, r - 7, p0, rot); tl.hold(r - 4)
    tl.hold(r - 3); tl.to(r, p0 + e * dist, rot, 'slam', rlag=0); tl.locks.append((r - 2, r + 1)); tl.impulse(r + 1, -e * 0.010, (2, 0, 0))
    for f, h in zip(range(r - 4, r + 1), (0.0, 0.015, 0.035, 0.03, 0.0)): tl.slot[f] = top3.world_to_gun(c, rot, e * h)
    tl.mark('release', r); tl.mark('cue', r - 4); tl.nodrag.append((r - 4, r + 1))


def st47(c, tl):
    """Pop and catch, thigh slap. Rolled onto its right side in front of the chest, the gun is popped up out of the palm while the arm drives it up along the magazine's line; the hand closes on it while it
    is still rising and stops it dead: the magazine carries on off the rail, out to the right and forward. The gun takes the fresh magazine half on at the belt rig and is slapped top first against the
    thigh to seat it. Up, cocked back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; _pop(c, tl)
    tl.hold(r + 2); slap_load(c, tl, 'belt_t', 'thigh_m', B['arr'])
    return mag(c, appear=B['arr'] - 4, fresh={'mode': 'slap', 'pick': B['arr'], 'part': 0.04, 'carry': 0.03})


def st48(c, tl):
    """Half-roll throw, scoop through the pouch. Up in front of the chest the gun is snapped half a turn over in the fingers, fast: the magazine is thrown off the rail before the top faces down and falls away.
    The gun stays upside down and dives to the belt in one move that runs straight onto the fresh magazine standing in the pouch, with no stop above it (it jolts on the seat). The other half of the turn
    brings it upright on the way up. Up, held muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, 0.03, -0.06), (0, 0, 0))
    tl.spin(r - 4, r + 4, -180, (0, 0, 1), PIV, (1.6, 2.0)); tl.spin(B['rise'], B['mid'] + 2, -180, (0, 0, 1), PIV, (2.0, 2.0))
    tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'belt_flat', dep=r + 7, flip=True, scoop=True); rack(c, tl, 'nod')
    return mag(c, spin_release=True, appear=B['arr'] - 2, fresh={'mode': 'still'})


def _flip(c, tl):
    B = c.B; r = B['rel']; opener(c, tl, 'press'); tl.hold(B['cue'] + 2); tl.to(r - 4, (0.02, 0.0, -0.06), (0, 0, 172), 'drive', rlag=1); tl.hold(r); tl.mark('release', r)


def st49(c, tl):
    """Flip and drop, buckle slap. The arm turns the gun over and the magazine falls off its underside by its own weight. Still turned over, the gun takes the fresh magazine half on at the belt rig
    and is slapped top first against the belly in front of the buckle to seat it. Rolled upright on the way up, held out in front and yanked back on the cocking device."""
    B = c.B; r = B['rel']; _flip(c, tl)
    tl.hold(r + 2); slap_load(c, tl, 'belt_t', 'belly_t', B['arr'], rack_kind='yank')
    return mag(c, appear=B['arr'] - 4, fresh={'mode': 'slap', 'pick': B['arr'], 'part': 0.04, 'carry': 0.03})


def st50(c, tl):
    """Flip and drop, caught upright at the belt. The arm turns the gun over and the magazine falls off its underside by its own weight. The gun turns back upright and goes down to the belt, where it is held still with
    the well up; a rig above lets go of the fresh magazine and it falls straight onto the top (the gun jolts down as it lands). Up, held out in front and yanked back on the cocking device."""
    B = c.B; r = B['rel']; _flip(c, tl)
    seat(c, tl, 'belt_flat', dep=r + 6, mode='drop', jolt_vec=(0, -0.016, 0), rot_add=upright_add(c, 'belt_flat')); rack(c, tl, 'yank')
    return mag(c, fresh={'mode': 'fall', 'n': 5})


def st51(c, tl):
    """Flip and drop, set down onto the pouch. The arm turns the gun over and the magazine falls off its underside by its own weight. Still turned over, the arm carries the gun above the belt pouch and presses it
    down onto the fresh magazine standing in it (it jolts on the seat). Rolled upright on the way up, cocked low, a rising punch on the cocking device."""
    B = c.B; r = B['rel']; _flip(c, tl)
    seat(c, tl, 'belt_t', dep=r + 9); rack(c, tl, 'yank')
    return mag(c, appear=B['arr'] - 4)


def st52(c, tl):
    """Barrel spin, driven up under the hanging magazine. Up in front of the chest the gun is spun a full turn in the fingers about its own barrel; near full speed the magazine is thrown off its rail and flies out to the
    right and forward. The gun goes down in front of the stomach and is driven up under the fresh magazine hanging still from the belt-front rig (it jolts on the seat). Up, held muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, 0.03, -0.06), (0, 0, 0))
    tl.spin(r - 4, r + 6, 360, (0, 0, 1), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'under_t', d=0.12, dep=r + 5); rack(c, tl, 'nod')
    return mag(c, spin_release=True)


def st53(c, tl):
    """Barrel spin, belly slap. Up in front of the chest the gun is spun a full turn in the fingers about its own barrel; near full speed the magazine is thrown off its rail and flies out to the right and forward.
    The gun takes the fresh magazine half on at the belt rig and is slapped top first against the belly in front of the buckle to seat it. Up, cocked back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, 0.03, -0.06), (0, 0, 0))
    tl.spin(r - 4, r + 6, 360, (0, 0, 1), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    tl.hold(r + 2); slap_load(c, tl, 'belt_t', 'belly_t', B['arr'], rack_kind='punch')
    return mag(c, spin_release=True, appear=B['arr'] - 4, fresh={'mode': 'slap', 'pick': B['arr'], 'part': 0.04, 'carry': 0.03})


MECH = {'ST44': 'Release: slow in-hand half turn, the magazine slides off by its weight. Load: the turned-over gun is driven down onto the magazine standing still in the belt pouch.',
        'ST45': 'Release: centrifugal throw from a one-turn spin about the barrel. Load: the gun waits upright and still; the rig above lets go of the fresh magazine and it falls onto the top at g.',
        'ST46': 'Release: the gun hangs from the trigger finger and the magazine slides off by its weight. Load: the gun is driven up under the fresh magazine hanging still from the belt-front rig.',
        'ST47': 'Release: pop up out of the palm and catch; the magazine carries on off the rail. Load: the gun carries the fresh magazine half on and slaps it home on the thigh.',
        'ST48': 'Release: fast half-roll throw. Load: the turned-over gun dives onto the magazine standing in the pouch, one move with no stop above it.',
        'ST49': 'Release: the gun is turned over and the magazine falls off its underside. Load: the gun carries the fresh magazine half on and slaps it home against the belly.',
        'ST50': 'Release: the gun is turned over and the magazine falls off its underside. Load: the gun waits upright at the belt and the rig above lets go of the fresh magazine, which falls onto the top at g.',
        'ST51': 'Release: the gun is turned over and the magazine falls off its underside. Load: the turned-over gun is pressed down onto the magazine standing still in the pouch.',
        'ST52': 'Release: centrifugal throw from a one-turn spin about the barrel. Load: the gun is driven up under the fresh magazine hanging still from the belt-front rig.',
        'ST53': 'Release: centrifugal throw from a one-turn spin about the barrel. Load: the gun carries the fresh magazine half on and slaps it home against the belly.'}
PICKS = {'ST44': ('Roll-off, down onto the pouch', st44), 'ST45': ('Barrel spin, fall-on', st45), 'ST46': ('Finger hang, driven up under', st46), 'ST47': ('Pop and catch, thigh slap', st47),
         'ST48': ('Half-roll throw, scoop through the pouch', st48), 'ST49': ('Flip, buckle slap', st49), 'ST50': ('Flip, caught upright, fall-on', st50), 'ST51': ('Flip, set down onto the pouch', st51),
         'ST52': ('Barrel spin, driven up under', st52), 'ST53': ('Barrel spin, belly slap', st53)}
PARAMS = {}

if __name__ == '__main__': r3lib.main(sys.modules[__name__], sys.argv[1:])
