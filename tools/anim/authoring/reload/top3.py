"""SMG TOP family, round 3 (BRIEF-NEW-TECHNIQUES.md): one-handed reload drafts (ST31 on) on the Warden, take B heavy
(7.0 l), right hand, male V, empty reload; its own one-handed reload, not the Shingen two-arm knock. Round 2's
flip-and-drop, knock-off, tip-forward throw, jerk, shake and pour are banned or recycled; only mechanisms no banned
entry covers are kept (MECH: one sentence each, on the page).

The magazine lies on top behind the sight, 8 cm above the trigger finger, and lifts off forward-up (42 deg above the
barrel line), guided 8 cm (the axis rule is checked over 9 cm). Release mechanisms used here: the gun spun in the
hand (Gorilla Arms strength) about its barrel axis, so the magazine above the bore is thrown off its rail by
centrifugal force, or turned over slowly so it slides off by its weight as the top passes the side (r2lib well
model). Every throw was measured (measure/flight_round3.json): all go right, down or forward, 29 cm or more clear of the
other gun (the first spin directions threw two magazines into it and were reversed). Loading tricks (r3lib fresh
modes): the belt-front rig drops the fresh magazine onto the upright gun's top, a pop-up rig presses it up into the
turned-over gun, the thigh rig tosses it up to meet the turned-over gun, or the gun takes it half on and slaps it
home against the thigh. Gun and hand on the r3lib spring (heavy take); the seat is an impact.
Same beats for all (take B, 77 frames: release f21, seat f43, hit f61, idle f70). The cocking device (gun f95 to
119) is time-mapped onto the hit to the end.

usage: top3.py list | build [ids] [--jobs n] | stats | gates
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv
import numpy as np
import r3lib, author
from r3lib import seat, rack, PUNCH
from r2lib import opener
from fk import qrot

FAMILY = 'TOP'; GUN = 'warden'; TAKE = 'B'; PREFIX = 'ST'
_ex = np.array((0.0, 0.67, -0.74)); _ex /= np.linalg.norm(_ex)
AXES = {'exit': _ex, 'enter': np.array((0.0, -1.0, 0.0))}
STATIONS = {'stomach_up': ((0.18, 0.16, -0.24), (0, 20, 0)),       # upright under the belt-front rig: the top faces straight up
            'belt_flat': ((0.29, 0.16, -0.10), (0, -6, 0)),        # level at the belt (turned over in the fingers: top down)
            'belt_t': ((0.31, 0.20, -0.10), (-40, 0, 180)),        # turned over by the arm above a belt pouch
            'belt_tl': ((0.31, 0.15, -0.10), (-40, 0, 180)),       # the same, 5 cm lower (out of view with the 15 cm approach)
            'stomach_t': ((0.24, 0.25, -0.19), (-10, 20, 0)),     # upright, driven up under a magazine hanging from the belt front
            'hip_t': ((0.31, 0.20, -0.10), (-60, -10, 160)),
            'thigh_t': ((0.38, 0.18, -0.02), (-60, 0, 90))}        # muzzle down, top toward the leg
PIV = (0.0, -0.03, -0.02)
LIFT2 = {}      # set by smgprod.py --lift for a pick whose entry has stop_m: {'stop_m': [x, y, z], 'pitch_deg': dp, 'drop_m': D, 'lead': n} (ST38, ST40)
STOP_DRIVE = {'ST38': {'drop': 0.18, 'arrive': 7}, 'ST40': {'drop': 0.20, 'arrive': 6}, 'ST32': {'drop': None, 'arrive': 8}}      # the arm-driven stop of a pick: drive length (m) along the exit line, frames before the release at which the wind-up is reached (lift.py reads it)


def mag(c, fresh=None, **k):
    B = c.B; d = {'release': B['rel'], 'mode': 'well', 'out_len': 0.08, 'axis_check_m': 0.09, 'tumble': 2, 'appear': B['arr'] + 2, 'seated': B['seat'], 'floor': 0.08,
                  'fresh': fresh or {'mode': 'still'}}; d.update(k)
    return {'mag': d}


def hold_at(c, tl, f0, f1, pos, rot):
    tl.hold(f0); tl.to(f1, pos, rot, 'drive', rlag=1)


def slap_load(c, tl, rig, thigh, pick, part=0.04, rack_kind='punch'):
    """Slap home: the gun takes the fresh magazine half on at the rig on the pick frame (hand-guided), lifts it,
    then drives it magazine first into the thigh; it goes home on that impact (seat beat) and the gun jolts."""
    B = c.B; P = c.P; rp, rr = c.station(rig); tp, trot = c.station(thigh)
    pre = np.array(rp) + c.along(rr, c.v['enter'], 0.15 + part); at = np.array(rp) + c.along(rr, c.v['enter'], part)
    tl.to(pick - 5, pre, rr, 'ease', rlag=P['lag'] + 1); tl.to(pick, at, rr, 'slam', rlag=0); tl.locks.append((pick - 5, pick))
    up = np.array(tp) + c.along(trot, c.v['enter'], 0.12); tl.to(B['slam'], up, trot, 'ease', rlag=1)      # the top leads into the thigh
    tl.to(B['seat'], tp, trot, 'slam', rlag=0); tl.locks.append((B['slam'] + 2, B['seat']))
    tl.impulse(B['seat'], c.along(trot, c.v['enter'], 0.016), (-3, 0, 0)); tl.mark('pick', pick); tl.mark('seat', B['seat'])
    rack(c, tl, rack_kind)


def st31(c, tl):
    """Barrel spin. Up in front of the chest the gun is spun a full turn in the fingers about its own barrel; near
    full speed the magazine is thrown off its rail and flies out to the right and forward while the gun finishes the
    turn. Down in front of the stomach, upright, held still under the
    belt-front rig, which lets the fresh magazine drop onto the top (the gun jolts down as it lands). Up, cocked
    back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, 0.03, -0.06), (0, 0, 0))
    tl.spin(r - 4, r + 6, 360, (0, 0, 1), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'stomach_up', dep=r + 4, mode='drop', jolt_vec=(0, -0.016, 0)); rack(c, tl, 'punch')
    return mag(c, spin_release=True, fresh={'mode': 'drop', 'n': 5})


def st32(c, tl):
    """Slow roll-off. Low in front of the belly the gun is turned over in the fingers, slowly;
    as the top passes the side the magazine slides off its rail by its own weight and falls, and the gun ends upside
    down. Held level like that over the belt, a pop-up rig presses the fresh magazine up onto the turned-over top
    (the gun jolts up). The other half of the turn brings it upright on the way up. Up, held out in front and yanked
    back on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - STOP_DRIVE['ST32']['arrive'], tuple(np.array((0.04, -0.08, -0.06)) + (np.array(LIFT2['stop_m'], float) if LIFT2 else 0.0)), (-4, 0, 0))      # LIFT2: the hold of the in-hand turn moves by stop_m (lift.py hold)
    tl.spin(r - 8, r + 4, -180, (0, 0, 1), PIV, (2.0, 2.0)); tl.spin(B['rise'], B['mid'] + 2, -180, (0, 0, 1), PIV, (2.0, 2.0))
    tl.mark('release', r); tl.mark('cue', r - 8)
    seat(c, tl, 'belt_flat', dep=r + 4, mode='drop', jolt_vec=(0, 0.014, 0)); rack(c, tl, 'yank')
    return mag(c, spin_release=True, spin_why='released in a slow in-hand turn: it slides off by its weight as the top passes the side', appear=B['seat'] - 6, fresh={'mode': 'present', 'n': 6, 'from': (0.0, -0.12, 0.0)})


def st33(c, tl):      # rejected (NOTES.md): the slanted tumble keeps the magazine on its rail 8 frames, then throws it
                         # slowly through the view (in view 19 frames, hidden window 9)
    """Tumble toss. Out to the right the gun is tumbled a full turn in the fingers about a slanted axis; the
    magazine is thrown off its rail as the top swings out and away. The arm turns the gun over above the belt; the
    thigh rig tosses the fresh magazine straight up and the turned-over gun comes down onto it at the top of its rise
    (it jolts on the seat). Rolled upright on the way up, cocked low, a rising punch on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.13, 0.02, -0.04), (0, -10, 6))
    tl.spin(r - 3, r + 5, -360, (0.45, 0, 0.9), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'belt_t', dep=r + 4); rack(c, tl, 'upper')
    return mag(c, spin_release=True, fresh={'mode': 'toss', 'n': 7})


def st34(c, tl):      # off the page: a third spin (at most 2 spin-based drafts per family)
    """Drill spin, slap home. The arm drops the gun beside the thigh, muzzle down, and the fingers spin it a full
    turn about its barrel like a drill: the magazine on its top is thrown off horizontally, away from the leg. The
    gun takes the fresh magazine half on from the belt rig, swings over the thigh and slaps it home top first
    against the thigh (it seats on that impact). Up, held muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; low, lr = c.station('hip_t'); low = np.array(low) + (0.08, 0.10, -0.12)
    hold_at(c, tl, 2, r - 6, low, (-75, -10, 0))
    tl.spin(r - 4, r + 6, 360, (0, 0, 1), PIV, (1.6, 2.0)); tl.mark('release', r); tl.mark('cue', r - 4)
    tl.hold(r + 2); slap_load(c, tl, 'belt_t', 'thigh_t', B['arr'], rack_kind='nod')
    return mag(c, spin_release=True, appear=r + 4, fresh={'mode': 'slap', 'pick': B['arr'], 'part': 0.04})


def st35(c, tl):      # off the page: a fourth spin
    """Half-roll throw. Up in front of the chest the gun is snapped half a turn over in the fingers, fast: the magazine is thrown off the rail before the top faces down and falls away down and forward;
    the gun stays upside down. Down to the belt like that and pressed onto the fresh magazine standing in the pouch
    (it jolts on the seat). The other half of the turn brings it upright on the way up. Up, held muzzle-high, the
    muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, 0.03, -0.06), (0, 0, 0))
    tl.spin(r - 4, r + 4, -180, (0, 0, 1), PIV, (1.6, 2.0)); tl.spin(B['rise'], B['mid'] + 2, -180, (0, 0, 1), PIV, (2.0, 2.0))
    tl.mark('release', r); tl.mark('cue', r - 4)
    seat(c, tl, 'belt_flat', dep=r + 4, flip=True); rack(c, tl, 'nod')
    return mag(c, spin_release=True, fresh={'mode': 'still'})


def world_to_gun(c, rot, v):
    """A world vector in the gun's axes with the gun at angles rot."""
    q = author.qmul(c.q0, author.qeuler(*rot)); qi = np.array([-q[0], -q[1], -q[2], q[3]])
    return qrot(qi, np.array(v, float))


def st36(c, tl):
    """Pop and catch. Rolled onto its right side in front of the chest, the gun is popped up out of the palm while
    the arm drives it up along the magazine's line; the hand closes on it while it is still rising and stops it dead:
    the magazine carries on off the rail, out to the right and forward. The fresh magazine is taken half on at the belt rig and slapped home top
    first against the thigh (it seats on that impact). Up, cocked back, punched forward on the cocking device.
    Needs in-game check: the gun leaves the hand (the weapon bone is animated relative to the hand)."""
    B = c.B; r = B['rel']; rot = (-6, 0, -60); p0 = np.array((0.03, -0.13, 0.05)); e = c.along(rot, c.v['exit'], 1.0); hold_at(c, tl, 2, r - 7, p0, rot); tl.hold(r - 4)
    tl.hold(r - 3); tl.to(r, p0 + e * 0.14, rot, 'slam', rlag=0); tl.locks.append((r - 2, r + 1)); tl.impulse(r + 1, -e * 0.010, (2, 0, 0))      # the pop runs along the magazine's exit line
    for f, h in zip(range(r - 4, r + 1), (0.0, 0.015, 0.035, 0.03, 0.0)): tl.slot[f] = world_to_gun(c, rot, e * h)
    tl.mark('release', r); tl.mark('cue', r - 4); tl.nodrag.append((r - 4, r + 1))
    tl.hold(r + 2); slap_load(c, tl, 'belt_t', 'thigh_t', B['arr'])
    return mag(c, appear=r + 4, fresh={'mode': 'slap', 'pick': B['arr'], 'part': 0.04})


def st37(c, tl):
    """Finger hang. The grip is let go and the gun swings muzzle-down on the trigger finger, hanging from it with the
    top facing forward and down; the release is pressed and the magazine slides off the top by its own weight. The
    gun swings back up into the palm, goes down in front of the stomach and is driven up under the fresh magazine
    hanging from the belt-front rig (it jolts on the seat). Up, held muzzle-high, the muzzle thrown down on the
    cocking device. Needs in-game check: the gun hangs from the finger (the weapon bone is animated relative to the
    hand)."""
    B = c.B; r = B['rel']; hold_at(c, tl, 2, r - 8, (0.04, 0.0, -0.06), (0, 0, -4))
    tl.spin(r - 7, r - 2, -110, (1, 0, 0), PIV, (2.0, 2.0)); tl.spin(r + 4, r + 11, 110, (1, 0, 0), PIV, (2.0, 2.0))
    tl.mark('release', r); tl.mark('cue', r - 7)
    seat(c, tl, 'stomach_t', d=0.12, dep=r + 5); rack(c, tl, 'nod')
    return mag(c)


def st38(c, tl):
    """Thigh anvil, turned over. The arm turns the gun over beside the hip and drives it down, muzzle first, until
    the front of the gun lands on the thigh: the leg stops it dead and the magazine, now underneath, carries on down
    off the rail. Still turned over, the thigh rig holds the fresh magazine out and the gun comes down onto it
    (it jolts on the seat). Rolled upright on the way up, cocked low, a rising punch on the cocking
    device."""
    B = c.B; r = B['rel']; th, trot = c.station('thigh_t'); stop = np.array(th) + (0.0, 0.10, -0.10); sr = (-20, 0, 180); wr = (-12, 0, 176); drop = STOP_DRIVE['ST38']['drop']
    if LIFT2:      # raised discard (lift.py, plift2): the stop (the leg is no longer the anvil: the arm stops the gun) moves by stop_m, the pitch changes by pitch_deg, the drive is drop_m long
        stop = stop + np.array(LIFT2['stop_m'], float); dr = LIFT2.get('roll_deg', 0.0); sr = (sr[0] + LIFT2['pitch_deg'], sr[1], sr[2] + dr); wr = (wr[0] + LIFT2['pitch_deg'], wr[1], wr[2] + dr); drop = LIFT2['drop_m']
    wu = stop - c.along(sr, c.v['exit'], drop); hold_at(c, tl, 2, r - STOP_DRIVE['ST38']['arrive'], wu, wr); tl.hold(r - 5 - (LIFT2.get('lead', 0) if LIFT2 else 0))
    tl.to(r, r3lib.aligned(c, wu, wr, sr, drop), sr, 'slam', rlag=0); tl.locks.append((r - 1, r + 1)); tl.impulse(r + 1, -c.along(sr, c.v['exit'], 0.010), (3, 0, 0))
    tl.mark('release', r); tl.nodrag.append((r - 5, r + 1))
    seat(c, tl, 'belt_tl', dep=r + 4); rack(c, tl, 'upper')
    return mag(c, fresh={'mode': 'still'})


def st39(c, tl):
    """Flip and drop, caught upright. The arm turns the gun over and the magazine falls off its underside by its own
    weight (the round 2 flip and drop); new is the load: the gun turns back upright in front of the stomach, held
    still under the belt-front rig, which drops the fresh magazine onto the top (the gun jolts down as it lands).
    Up, held out in front and yanked back on the cocking device."""
    B = c.B; r = B['rel']; opener(c, tl, 'press'); tl.hold(B['cue'] + 2); tl.to(r - 4, (0.02, 0.0, -0.06), (0, 0, 172), 'drive', rlag=1); tl.hold(r); tl.mark('release', r)
    seat(c, tl, 'stomach_up', dep=r + 5, mode='drop', jolt_vec=(0, -0.016, 0)); rack(c, tl, 'yank')
    return mag(c, fresh={'mode': 'drop', 'n': 5})


def st40(c, tl):
    """Tip-forward throw, slapped home on the hip. Muzzle dipped and rolled out, the gun is thrust forward and stopped
    dead and the magazine flies off ahead (the round 2 tip-forward throw, a chop); new is the load: the fresh
    magazine is taken half on at the belt rig and the gun is slapped top first against the hip to seat it. Up, cocked
    back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; stop, sr, wr = np.array((0.05, -0.11, -0.04)), (-24, 0, -40), (-18, 0, -36); drop = STOP_DRIVE['ST40']['drop']; lead = 0
    if LIFT2:      # raised discard (lift.py, plift4): as st38, the stop moves by stop_m, the pitch and roll change, the drive is drop_m long
        stop = stop + np.array(LIFT2['stop_m'], float); dr = LIFT2.get('roll_deg', 0.0); sr = (sr[0] + LIFT2['pitch_deg'], sr[1], sr[2] + dr); wr = (wr[0] + LIFT2['pitch_deg'], wr[1], wr[2] + dr); drop = LIFT2['drop_m']; lead = LIFT2.get('lead', 0)
    wu = stop - c.along(sr, c.v['exit'], drop); tl.hold(3); tl.to(r - STOP_DRIVE['ST40']['arrive'], wu, wr, 'drive', rlag=1); tl.hold(r - 5 - lead)
    tl.to(r, r3lib.aligned(c, wu, wr, sr, drop), sr, 'slam', rlag=0); tl.locks.append((r - 1, r + 1)); tl.mark('release', r); tl.nodrag.append((r - 5, r + 1))
    tl.hold(r + 2); slap_load(c, tl, 'belt_t', 'hip_t', B['arr'])
    return mag(c, appear=r + 4, fresh={'mode': 'slap', 'pick': B['arr'], 'part': 0.04, 'carry': 0.03})


def st41(c, tl):
    """Jerk down into a scoop. Held still, the gun is jerked down, back and out from under the released magazine,
    which is left in the air and falls (the round 2 jerk down); new is the load: turned over by the arm, the gun dives
    to the belt pouch and scoops the fresh magazine on the move, the dive running straight into the seat (it jolts on
    the seat). Rolled upright on the way up, cocked back, punched forward on the cocking device."""
    B = c.B; r = B['rel']; p0 = np.array((0.0, 0.02, -0.02)); ru = (0, 0, -3); hold_at(c, tl, 2, r - 3, p0, ru); tl.hold(r)
    low = p0 - c.along(ru, c.v['exit'], 0.12) + (0.16, -0.04, 0.0); tl.to(r + 5, low, (-6, 0, -3), (1.3, 2.6), rlag=0); tl.mark('release', r); tl.nodrag.append((r - 1, r + 6))
    seat(c, tl, 'belt_t', dep=r + 6, arr=B['slam'], scoop=True); rack(c, tl, 'punch')
    return mag(c)


def st42(c, tl):
    """Belt knock-off, presented at the hip. Turned over at the belt, the magazine's front edge is set against the lip
    of the belt rig and the gun pulled back off it: the rig holds the magazine (the round 2 knock-off, a strip); new
    is the load: a pop-up rig at the hip presses the fresh magazine up into the turned-over gun. Rolled upright on the
    way up, held muzzle-high, the muzzle thrown down on the cocking device."""
    B = c.B; r = B['rel']; hook, rot = c.station('belt_t'); hook = np.array(hook) + (0.02, 0.10, -0.08)
    tl.hold(3); tl.to(r, hook, rot, 'heavy', rlag=1); tl.locks.append((r - 1, r + 5))
    off = hook - c.along(rot, c.v['exit'], 0.14); tl.to(r + 5, off, rot, PUNCH, rlag=0); tl.mark('release', r); tl.nodrag.append((r - 2, r + 7))
    seat(c, tl, 'hip_t', dep=r + 7, mode='drop', jolt_vec=(0, 0.012, 0)); rack(c, tl, 'nod')
    return mag(c, mode='hook', appear=B['seat'] - 6, fresh={'mode': 'present', 'n': 6, 'from': (0.0, -0.12, 0.0)})


def st43(c, tl):
    """Inverted shake, pressed into the pouch. Turned over by the arm and shaken out to the side twice, the magazine
    works loose and slides off by its weight (the round 2 inverted shake); new is the load: still turned over, the
    gun is pressed straight down onto the fresh magazine standing in the belt pouch (it jolts on the seat). Rolled
    upright on the way up, cocked low, a rising punch on the cocking device."""
    B = c.B; r = B['rel']; base = np.array((0.02, 0.0, -0.05)); inv = (0, 0, 172); tl.hold(2); tl.to(B['cue'] + 3, base, inv, 'drive', rlag=1); f = B['cue'] + 3; marks = []
    for dx in (0.03, -0.01, 0.03):
        tl.to(f + 2, base + (dx, 0, 0), (0, 0, 172 - dx * 200), PUNCH, rlag=0); marks.append(f + 2); f += 2
    tl.to(r - 2, base, inv, 'drive', rlag=0); tl.hold(r); tl.mark('release', r)
    seat(c, tl, 'belt_tl', dep=r + 4); rack(c, tl, 'upper')
    return mag(c, loosen=[[marks[0], 0.004], [marks[1], 0.008], [marks[2], 0.012]], spin_release=True, spin_why='a slide by its weight while the gun settles after the last shake, not a throw')


MECH = {'ST31': 'Release: centrifugal throw from a one-turn in-hand spin about the barrel, the magazine above the bore (spin 1 of 2). Load: the belt-front rig drops the fresh one onto the top.',
        'ST32': 'Release: a slow in-hand half turn, the magazine slides off by its weight as the top passes the side (spin 2 of 2). Load: a pop-up rig presses the fresh one up into the turned-over gun.',
        'ST36': 'Release: the gun is popped up out of the palm and the catch stops its rise; the magazine carries on off the rail (the catch, not an arm stop, is the stop). Load: slapped home on the thigh. Needs in-game check (gun leaves the hand).',
        'ST37': 'Release: the gun hangs muzzle-down from the trigger finger and the magazine slides off by its weight (a finger hang, not a press-and-drop pose or a flip). Load: driven up under the hanging fresh magazine. Needs in-game check (gun hangs from the finger).',
        'ST38': 'Release: the thigh is the anvil for the turned-over gun; the leg stops it and the magazine leaves downward off the underside (a body part as the tool, a downward exit). Load: the turned-over gun comes down onto a magazine held out by the thigh rig.',
        'ST39': 'Release: flip and drop (banned) kept as the release; new is the load, the gun turned upright and the fresh magazine dropped onto its top by the belt-front rig (a catch, not a drive onto).',
        'ST40': 'Release: tip-forward throw (a chop, banned) kept as the release; new is the load, slapped home top first against the hip (the body as the anvil for the seat).',
        'ST41': 'Release: jerk down (banned) kept as the release; new is the load, a scoop on the move into the belt pouch, the dive running straight into the seat.',
        'ST42': 'Release: knock-off on the belt rig (a strip, banned) kept as the release; new is the load, a pop-up rig at the hip presses the fresh one up into the turned-over gun.',
        'ST43': 'Release: inverted shake (banned) kept as the release; new is the load, the turned-over gun pressed straight down onto the magazine standing in the pouch.'}
PICKS = {'ST31': ('Barrel spin, drop-on', st31), 'ST32': ('Slow roll-off', st32), 'ST36': ('Pop and catch', st36), 'ST37': ('Finger hang', st37), 'ST38': ('Thigh anvil, turned over', st38),
         'ST39': ('Flip-drop, caught upright', st39), 'ST40': ('Tip throw, hip slap', st40), 'ST41': ('Jerk down, scoop', st41), 'ST42': ('Knock-off, hip pop-up', st42), 'ST43': ('Inverted shake, pouch', st43)}
PARAMS = {}

if __name__ == '__main__': r3lib.main(sys.modules[__name__], sys.argv[1:])
