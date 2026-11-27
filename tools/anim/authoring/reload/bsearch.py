"""Parameter search for one BREAK pick on one gun: candidates into work/search/<tag>/ (not the clip folder).
usage: bsearch.py <gun> <pick> <tag> '<json params>' [side] [body] [clip]"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, breakprod
gid, pick, tag, P = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4]); side = sys.argv[5] if len(sys.argv) > 5 else 'right'; body = sys.argv[6] if len(sys.argv) > 6 else 'pma'; clip = sys.argv[7] if len(sys.argv) > 7 else 'empty_reload'
P = {k: (tuple(v) if isinstance(v, list) else v) for k, v in P.items()}
breakprod.OUT = f'{renv.OUT}/work/search/{tag}'; breakprod.PARAMS[(pick, gid)] = P
spec, o = breakprod.build(gid, pick, clip, side, body, quiet=True); p = o['phys']
print(tag, side, body, json.dumps(P), '| hulls seen', o.get('shells_seen'), 'trip', p['trip_f'], '| latch', p['latch'], p['latch_w_deg_f'], '| other', o['hulls_to_other_gun_cm'], '| end', o['end_transition']['last3_step_cm'],
      '| eye', o['eye_cm'][0], 'reach', o['reach'][0], 'sh', o['shoulder_pull_cm'], '| FAILS', o['fails'], flush=True)
