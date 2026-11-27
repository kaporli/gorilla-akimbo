"""R10 measure: peak swing speed (deg/f) of the four arm joints of an arm clip: clavicle (Shoulder), shoulder (Arm), elbow (ForeArm), wrist (Hand).
Swing of a joint = the direction of its child bone (the child's rest offset) in the joint's parent frame, per frame; speed = angle between consecutive
frames. Twist about the bone axis is dropped (the forearm twist flips by up to 150 deg in one frame on shipped clips with no visible change).
Sampled at 30 fps from the clip's keys (wclip.TClip), so a key spacing longer than 1 frame is interpolated."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)).replace(chr(92), '/')
sys.path.insert(0, os.path.join(HERE, '..', 'reload')); sys.path.insert(0, os.path.join(HERE, '..'))
import renv
import numpy as np
from glb import Glb
from wclip import TClip
from fk import qrot

JOINTS = (('clavicle', 'Shoulder', 'Arm'), ('shoulder', 'Arm', 'ForeArm'), ('elbow', 'ForeArm', 'Hand'), ('wrist', 'Hand', 'HandEnd'))


def swing_speeds(glb, clip, side):
    """-> {joint name: array (frames-1) of swing speed, deg/f}"""
    c = TClip(Glb(glb), clip); out = {}
    for name, jn, child in JOINTS:
        i = c.names.index(side + jn); k = c.names.index(side + child)
        off = np.array(c.nodes[k].get('translation', [0, 0, 0]), float)
        if (side + child, 'translation') in c.tr: off = c.tr[(side + child, 'translation')][1][0]
        off = off / np.linalg.norm(off)
        v = np.array([qrot(c.local(i, f / 30.0)[1], off) for f in range(c.frames)])
        out[name] = np.degrees(np.arccos(np.clip((v[1:] * v[:-1]).sum(1), -1, 1)))
    return out


def measure(glb, clip, side):
    """R10 measures: peak swing speed per joint (deg/f) and the frame of each peak."""
    s = swing_speeds(glb, clip, side)
    return {'peak_deg_f': {j: round(float(w.max()), 2) for j, w in s.items()}, 'peak_frame': {j: int(w.argmax()) + 1 for j, w in s.items()}}
