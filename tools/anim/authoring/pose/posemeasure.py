"""Length and game-pose cover of one gun mesh (worker of checks.py: a module of its own so that the worker processes
find it by name whatever else is on sys.path)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
for _p in (os.path.join(common.HERE, 'lowered'), os.path.join(common.HERE, 'raised')):   # modules named like the gate's: last
    if _p not in sys.path: sys.path.append(_p)
import guns as GN                 # lowered/guns.py
import rautotune as RA            # raised/rautotune.py (imports rpose)


def measure(a):
    """(mesh, length cm, {body: idle cover %}) of the game's raised pose"""
    mesh, bodies = a
    return mesh, GN.length_cm(mesh), {b: round(RA.evaluate(b, mesh, None, 0.0)['idle']['Right']['cover'], 1) for b in bodies}
