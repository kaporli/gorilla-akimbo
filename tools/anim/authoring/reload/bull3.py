"""SMG BULLPUP family, round 3 (BRIEF-NEW-TECHNIQUES.md): one-handed reload drafts (SB31 on) on the Pulsar, take A
snappy (light, 2.2 l), right hand, male V, empty reload. Round 2's strip, jerk, shake, flick, press-and-drop and
pouch dump are banned; only mechanisms no banned entry covers are kept (MECH: one sentence each, on the page).

The magazine sits behind the hand under the stock and leaves down along its well (14 deg forward), 7 cm in the
well (the rule that it leaves along its axis is checked over those 7 cm: past them it is clear and a spinning gun
turns away from it). Release mechanisms used here: the gun spun in the hand (Gorilla Arms strength) so the magazine, out at the end
of a lever from the spin's pivot, is flung down its well by centrifugal force (r2lib well model: the seat point's
acceleration includes the spin), with the spin's axis and its moment chosen so the fling points away from V and
the other gun. Loading tricks for the fresh one (r3lib fresh modes): the rig presents it, tosses it up to meet the
gun, drops it into the upturned well, or the gun takes it half in and is slapped against the thigh to seat it.
Gun and hand on the r3lib spring (overshoot, rebound, rotation lag; no authored kicks); the seat is an impact.
Same beats for all (take A, 68 frames: release f18, seat f38, hit f53, idle f61).

usage: bull3.py list | build [ids] [--jobs n] | stats | gates
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r3lib, author
import r2lib as R2
from r3lib import seat, rack, PUNCH
from fk import qrot

FAMILY = 'BULLPUP'; GUN = 'pulsar'; TAKE = 'A'; PREFIX = 'SB'
_ex = np.array((0.0, -0.97, -0.24)); _ex /= np.linalg.norm(_ex)
AXES = {'exit': _ex, 'enter': -_ex}
STATIONS = {'belt_b': ((0.27, 0.22, -0.11), (-16, -6, 4)), 'thigh_b': ((0.28, 0.14, -0.09), (-24, -8, 6)), 'hip_b': ((0.30, 0.23, -0.05), (-20, -12, 10)),
            'stomach_b': ((0.16, 0.24, -0.17), (-16, 10, -6)), 'rear_b': ((0.29, 0.23, 0.02), (-22, -14, 10)),
            'belt_up': ((0.26, 0.20, -0.12), (25, -6, -14)),       # muzzle 14 deg up: turned over in the fingers, the well axis is vertical
            'belt_inv': ((0.27, 0.22, -0.12), (14, -6, 180))}       # turned over by the arm above the belt: the well faces up
PIV = (0.0, -0.03, -0.02)        # trigger finger, gun axes: the pivot of every in-hand spin
UP = -14                         # pitch that puts the well vertical (muzzle a little down)
BASE = np.array((-0.007, -0.185, 0.018))      # magazine foot, gun axes


def place(c, rot, local, world):
    """Grip offset that puts a point of the gun (gun axes) on a world point with the gun at angles rot."""
    return np.array(world, float) - c.g0 - qrot(author.qmul(c.q0, author.qeuler(*rot)), np.array(local, float))


def mag(c, fresh=None, **k):
    B = c.B; d = {'release': B['rel'], 'mode': 'well', 'out_len': 0.07, 'axis_check_m': 0.07, 'tumble': 2, 'appear': B['arr'] + 2, 'seated': B['seat'], 'floor': 0.08,
                  'fresh': fresh or {'mode': 'still'}}; d.update(k)
    return {'mag': d}


def hold_at(c, tl, f0, f1, pos, rot):
    tl.hold(f0); tl.to(f1, pos, rot, 'drive', rlag=1)


def sb31(c, tl):
    """Barrel spin. The gun is brought up in front of the chest and spun a full turn outward around the trigger
    finger, about its own barrel axis; near full speed, a quarter turn in, with the magazine swinging out to the right, it is flung from
    its well and flies off to the right while the gun finishes the turn. Down to the belt, where the rig pops
    the fresh magazine up into reach and the gun is driven onto it (it jolts on the seat). Up, cocked low, a rising
    punch on the cocking handle."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 7, (0.04, 0.05, -0.05), (0, 0, -6))
    tl.spin(r - 4, r + 8, -360, (0, 0, 1), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'belt_b', dep=r + 4); rack(c, tl, 'upper')
    return mag(c, spin_release=True, appear=c.B['arr'] - 4, fresh={'mode': 'present', 'n': 4, 'from': (0.0, -0.10, 0.02)})


def slap_load(c, tl, rig, thigh, pick, part=0.04, rack_kind='punch'):
    """Slap home: the gun takes the fresh magazine half in at the rig on the pick frame (hand-guided), lifts it,
    then drives it foot first into the thigh; the magazine goes home on that impact (seat beat) and the gun jolts."""
    B = c.B; P = c.P; rp, rr = c.station(rig); tp, trot = c.station(thigh)
    pre = np.array(rp) + c.along(rr, c.v['enter'], 0.15 + part); at = np.array(rp) + c.along(rr, c.v['enter'], part)
    tl.to(pick - 4, pre, rr, 'ease', rlag=P['lag'] + 1); tl.to(pick, at, rr, 'slam', rlag=0); tl.locks.append((pick - 4, pick))
    up = np.array(tp) - c.along(trot, c.v['exit'], 0.12); tl.to(B['slam'], up, trot, 'ease', rlag=1)
    tl.to(B['seat'], tp, trot, 'slam', rlag=0); tl.locks.append((B['slam'] + 2, B['seat']))
    tl.impulse(B['seat'], -c.along(trot, c.v['exit'], 0.014), (-3, 0, 0)); tl.mark('pick', pick); tl.mark('seat', B['seat'])
    rack(c, tl, rack_kind)


def sb32(c, tl):
    """Revolver spin. Up in front of the chest, the gun is spun end over end one full turn around the trigger
    finger, muzzle up and over backward; near full speed the magazine is flung out of its well and drops down and
    back past the forearm while the gun completes the turn. Down beside the thigh: the thigh rig tosses
    the fresh magazine straight up and the gun comes down onto it at the top of its rise (it jolts on the seat). Up,
    held out in front and yanked back on the cocking handle."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 7, (0.03, 0.06, -0.06), (2, 0, -4))
    tl.spin(r - 4, r + 8, 360, (1, 0, 0), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'thigh_b', dep=r + 4); rack(c, tl, 'yank')
    return mag(c, spin_release=True, fresh={'mode': 'toss', 'n': 7})


def sb33(c, tl):      # off the page: a third spin (at most 2 spin-based drafts per family)
    """Tumble. The gun is held out to the right and tumbled a full turn in the fingers about a slanted axis (barrel
    and side together), a corkscrew; the magazine is flung out of its well and drops down and back under the
    gun. The gun takes the fresh magazine half in from the belt rig, swings it over the thigh and slaps it
    home foot first against the thigh (it seats on that impact). Up, cocked back, punched forward on the cocking
    handle."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 7, (0.07, 0.04, -0.04), (0, -6, 8))
    tl.spin(r - 4, r + 8, 360, (0.7, 0, 0.7), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    tl.hold(r); slap_load(c, tl, 'belt_b', 'thigh_b', B['arr'] - 2)
    return mag(c, spin_release=True, appear=r + 4, fresh={'mode': 'slap', 'pick': B['arr'] - 2, 'part': 0.04})


def sb34(c, tl):      # rejected (NOTES.md): the fling needs 3 to 4 frames to clear the well; by then the half roll
                         # has turned the gun over and it throws the magazine up to eye height (1.71 m)
    """Half-roll catch. Up in front of the chest the gun is rolled half a turn in the fingers, fast: the magazine is
    flung down and out a third of the way into the roll, and the gun ends upside down, well facing up. Down to the
    belt like that, held still under the chest rig, which lets the fresh magazine fall into the open well (it knocks
    the gun down as it lands). The second half of the roll brings it upright on the way up. Up, held muzzle-high,
    the muzzle thrown down on the cocking handle."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 7, (0.04, 0.05, -0.05), (0, 0, -6))
    tl.spin(r - 2, r + 2, 180, (0, 0, 1), PIV, (2.0, 2.0)); tl.spin(B['rise'], B['mid'] + 2, 180, (0, 0, 1), PIV, (2.0, 2.0))
    tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'belt_up', dep=r + 4, mode='drop'); rack(c, tl, 'nod')
    return mag(c, spin_release=True, fresh={'mode': 'drop', 'n': 5})


def sb35(c, tl):      # off the page: a fourth spin
    """Drill spin. The arm drops the gun beside the thigh, muzzle down, and the fingers spin it a full turn about
    its own barrel like a drill: the magazine, sticking out sideways from the vertical gun, is flung out horizontally
    away from the leg and drops. The gun swings up onto the fresh magazine on the hip rig and is driven onto it (it
    jolts on the seat). Up, cocked low, a rising punch on the cocking handle."""
    B = c.B; r = B['rel']; low, lr = c.station('thigh_b'); low = np.array(low) + (0.06, 0.06, -0.10)
    hold_at(c, tl, 2, r - 5, low, (-75, -10, 10))
    tl.spin(r - 4, r + 8, -360, (0, 0, 1), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'hip_b', dep=r + 6); rack(c, tl, 'upper')
    return mag(c, spin_release=True)


def body_slap(c, tl, rig, target, pick, part=0.04, rack_kind='punch'):
    """Slap home on any body rig (thigh, stomach): slap_load with the target station."""
    slap_load(c, tl, rig, target, pick, part, rack_kind)


def toss_offsets(c, f0, f1, catch, rise=True):
    """In-hand offsets (gun axes, m) of a toss out of the palm: ballistic from f0, caught on frame catch (offset 0)."""
    T = f1 - f0; v0 = 0.5 * r3lib.G_ACC * T; off = np.zeros((c.N, 3))
    for f in range(f0, catch + 1):
        t = f - f0; off[f, 1] = max(v0 * t - 0.5 * r3lib.G_ACC * t * t, 0.0)
    off[catch:] = 0.0
    return off


def sb36(c, tl):
    """Toss and catch. In front of the chest the hand opens and flips the gun straight up out of the palm, 11 cm;
    it falls back and the hand closes on it on the release frame: the catch stops the gun dead and the magazine,
    falling with it, carries on down out of the well and drops. The fresh magazine is taken half in at the belt and
    slapped home foot first on the thigh (it seats on that impact). Up, cocked back, punched forward on the cocking
    handle. Needs in-game check: the gun leaves the hand (the weapon bone is animated relative to the hand)."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 11, (0.03, 0.02, -0.05), (UP, 0, -4))
    off = toss_offsets(c, r - 9, r + 1, r); tl.slot += off; tl.impulse(r, (0, -0.012, 0), (-2, 0, 0)); tl.mark('release', r); tl.mark('cue', r - 9)
    tl.hold(r + 1); slap_load(c, tl, 'belt_b', 'thigh_b', B['arr'] - 2)
    return mag(c, appear=r + 4, fresh={'mode': 'slap', 'pick': B['arr'] - 2, 'part': 0.04})


def sb37(c, tl):
    """Finger pivot. Muzzle dipped, the grip is let go and the gun pivots muzzle-up on the trigger finger, a quarter turn in three
    frames, until the palm slaps shut on it and stops it dead: the magazine, swinging down and forward behind the
    finger, carries on out of its well and drops. The gun pivots back into the palm on the way down to the belt rig
    and is driven onto the fresh magazine (it jolts on the seat). Up, cocked low, a rising punch on the cocking
    handle. Needs in-game check: the gun turns on the finger (the weapon bone is animated relative to the hand)."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 7, (0.03, 0.06, -0.06), (-40, 0, -4))      # arm dipped: the pivot throws down and forward
    tl.spin(r - 3, r, 90, (1, 0, 0), PIV, (2.6, 1.3)); tl.spin(r + 4, r + 11, -90, (1, 0, 0), PIV, (2.0, 2.0))
    tl.impulse(r, (0, 0.006, 0), (3, 0, 0)); tl.mark('release', r); tl.mark('cue', r - 3)
    seat(c, tl, 'belt_b', dep=r + 4); rack(c, tl, 'upper')
    return mag(c, spin_release=True, spin_why='released at the end of an in-hand pivot: the swing adds centrifugal push as it slides out')


def sb38(c, tl):
    """Thigh anvil. The arm swings the gun down beside the thigh, muzzle dipped, and the front of the gun lands on
    the top of the thigh: the leg stops it dead and the magazine, behind the hand, carries on down out of its well
    past the knee. The hip rig holds the fresh magazine out in reach and the gun is driven onto it (it jolts on the
    seat). Up, held out in front and yanked back on the cocking handle."""
    B = c.B; r = B['rel']; th, trot = c.station('thigh_b'); stop = np.array(th) + (0.03, 0.07, -0.12); sr = (-35, -8, 6); wr = (-28, -6, 4)
    wu = stop - c.along(sr, c.v['exit'], 0.20); hold_at(c, tl, 2, r - 6, wu, wr); tl.hold(r - 5)
    tl.to(r, r3lib.aligned(c, wu, wr, sr, 0.20), sr, 'slam', rlag=0); tl.locks.append((r - 1, r + 1)); tl.impulse(r + 1, -c.along(sr, c.v['exit'], 0.010), (3, 0, 0))
    tl.mark('release', r); tl.nodrag.append((r - 5, r + 1))
    seat(c, tl, 'hip_b', dep=r + 3); rack(c, tl, 'yank')
    return mag(c, appear=B['arr'] - 4, fresh={'mode': 'still'})


def sb39(c, tl):
    """Buckle anvil. The gun is swung down and in across the belt line, muzzle dipped, and the front of the gun lands
    on the belt buckle: the body stops it dead and the magazine, behind the hand, carries on down out of its well and
    drops past the hip. Down beside the thigh: the thigh rig holds the fresh magazine out and the gun comes down onto
    it (it jolts on the seat). Up, held muzzle-high, the muzzle thrown down on the cocking
    handle. (A hook on the left gun's barrel was tried first: the reach pulled the shoulder 27.6 cm.)"""
    B = c.B; r = B['rel']; bp, br = c.station('stomach_b'); stop = np.array(bp) + (0.02, 0.06, -0.10); sr = (-30, 12, -6); wr = (-22, 8, -4)
    wu = stop - c.along(sr, c.v['exit'], 0.18); hold_at(c, tl, 2, r - 6, wu, wr); tl.hold(r - 5)
    tl.to(r, r3lib.aligned(c, wu, wr, sr, 0.18), sr, 'slam', rlag=0); tl.locks.append((r - 1, r + 1)); tl.impulse(r + 1, -c.along(sr, c.v['exit'], 0.010), (3, 0, 0))
    tl.mark('release', r); tl.nodrag.append((r - 5, r + 1))
    seat(c, tl, 'thigh_b', dep=r + 4); rack(c, tl, 'nod')
    return mag(c, tumble=3, fresh={'mode': 'still'})


def sb40(c, tl):
    """Chop into the stomach. A wind-up and one chop down the well that stops dead throws the magazine out (the
    round 1 chop); new is the load: the fresh magazine is taken half in at the belt rig and the gun is slapped
    against the stomach, magazine first, to seat it on that impact. Up, cocked back, punched forward on the cocking
    handle."""
    B = c.B; r = B['rel']; R2.chop(c, tl, (0.0, 0.03, 0.02), (-4, 0, 0), (16, 0, -3), 0.17)
    tl.hold(r + 1); slap_load(c, tl, 'belt_b', 'stomach_b', B['arr'] - 2)
    return mag(c, appear=r + 4, fresh={'mode': 'slap', 'pick': B['arr'] - 2, 'part': 0.04})


def sb41(c, tl):
    """Jerk up into a scoop. The gun is held still and jerked straight up from under the released magazine, which
    is left behind and drops (the round 2 jerk); new is the load: the gun dives to the belt rig and scoops the fresh
    magazine on the move, the dive running straight into the seat without a pause (it jolts on the seat). Up, cocked
    low, a rising punch on the cocking handle."""
    B = c.B; r = B['rel']; low = np.array((0.01, -0.02, -0.03)); ru = (UP + 4, 0, -4)
    hold_at(c, tl, 2, r - 3, low, ru); tl.hold(r)
    top = low - c.along(ru, c.v['exit'], 0.15); tl.to(r + 4, top, ru, (1.3, 2.6), rlag=0); tl.mark('release', r); tl.nodrag.append((r - 1, r + 5))
    seat(c, tl, 'belt_b', dep=r + 5, arr=B['slam'], scoop=True); rack(c, tl, 'upper')
    return mag(c)


def sb42(c, tl):
    """Press and drop, then catch. Held still with the well hanging straight down, the release is pressed and the
    magazine slides out by its own weight (the round 2 press-and-drop); new is the load: the arm turns the gun over
    above the belt, well facing up, and the chest rig lets the fresh magazine fall into it (it knocks the gun down
    as it lands). Rolled upright on the way up, held out in front and yanked back on the cocking handle."""
    B = c.B; r = B['rel']; up = (0.01, 0.07, -0.04); ru = (UP, 0, -4)
    hold_at(c, tl, 2, r - 6, up, ru); tl.hold(r); tl.mark('release', r)
    seat(c, tl, 'belt_inv', dep=r + 4, mode='drop'); rack(c, tl, 'yank')
    return mag(c, fresh={'mode': 'drop', 'n': 5})


def sb43(c, tl):
    """Tilt and shake, presented behind the hip. Canted inward and shaken three times, the magazine works loose and
    slides out (the round 2 tilt and shake); new is the load: the rear rig behind the hip holds the fresh magazine up
    and the gun is driven back onto it there (it jolts on the seat). Up, cocked back, punched forward on the cocking
    handle."""
    B = c.B; r = B['rel']; base = np.array(c.P.get('base', (0.0, 0.05, -0.04))); tl.hold(2); tl.to(B['cue'] + 4, base, (UP - 4, 0, -40), 'drive', rlag=1)   # production: base per body (smgprod.BODY_PARAMS)
    f = B['cue'] + 4; marks = []
    for dx, roll in ((0.025, -18), (-0.02, -44), (0.025, -16)):
        tl.to(f + 2, base + (dx, 0, 0), (UP - 4, 0, roll), PUNCH, rlag=0); marks.append(f + 2); f += 2
    tl.to(r - 1, base + (0.0, 0.01, 0), (UP, 0, -4), 'drive', rlag=0); tl.hold(r); tl.mark('release', r)
    seat(c, tl, 'rear_b', dep=r + 4); rack(c, tl, 'punch')
    return mag(c, loosen=[[marks[0], 0.01], [marks[1], 0.02], [marks[2], 0.035]], appear=B['arr'] - 4, fresh={'mode': 'still'},
               spin_release=True, spin_why='a slide by its weight while the gun settles after the last shake, not a throw')


MECH = {'SB31': 'Release: centrifugal fling from a one-turn in-hand spin about the barrel (spin 1 of 2). Load: a pop-up rig presents the fresh magazine.',
        'SB32': 'Release: centrifugal fling from an end-over-end in-hand spin about the trigger finger (spin 2 of 2). Load: throw-and-meet, the thigh rig tosses it up and the gun comes down on it.',
        'SB36': 'Release: the gun is tossed out of the palm and caught; the catch is the stop that throws the magazine on (not an arm stop: no banned chop or drop stop). Load: slapped home on the thigh. Needs in-game check (gun leaves the hand).',
        'SB37': 'Release: the gun pivots a quarter turn on the trigger finger and the palm slaps it to a stop; the magazine carries on along its well (a partial pivot, not a spin, a flick or an arm stop). Load: driven onto the belt rig. Needs in-game check (gun turns on the finger).',
        'SB38': 'Release: the thigh is the anvil, the front of the gun lands on it and the leg stops it (a body part as the tool, not an arm stop). Load: a hip rig holds the fresh magazine out and the gun is driven onto it.',
        'SB39': 'Release: the belt buckle is the anvil, the front of the gun swung down and in onto it (the body as the tool, a different place and direction from SB38: across the body, magazine thrown down past the hip). Load: the gun comes down onto a magazine held out by the thigh rig.',
        'SB40': 'Release: the wind-up chop (banned) kept as the release; new is the load, slapped home magazine first against the stomach (the body as the anvil for the seat).',
        'SB41': 'Release: jerk up (banned) kept as the release; new is the load, a scoop on the move: the dive runs straight into the seat without a pause.',
        'SB42': 'Release: press-and-drop (banned) kept as the release; new is the load, a catch: the gun turned over, well up, and the chest rig drops the fresh magazine into it.',
        'SB43': 'Release: tilt and shake (banned) kept as the release; new is the load, a rig behind the hip holds the fresh magazine and the gun is driven back onto it there.'}
PICKS = {'SB31': ('Barrel spin', sb31), 'SB32': ('Revolver spin', sb32), 'SB36': ('Toss and catch', sb36), 'SB37': ('Finger pivot', sb37), 'SB38': ('Thigh anvil', sb38),
         'SB39': ('Buckle anvil', sb39), 'SB40': ('Chop, stomach slap', sb40), 'SB41': ('Jerk, scoop', sb41), 'SB42': ('Press-drop, catch', sb42), 'SB43': ('Tilt-shake, rear rig', sb43)}
PARAMS = {}

if __name__ == '__main__': r3lib.main(sys.modules[__name__], sys.argv[1:])
