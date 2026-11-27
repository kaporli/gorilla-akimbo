"""Parameter search for one FRONT pick on one gun: builds candidates into work/search/<tag>/ (not the clip folder)
and prints each one's fails. usage: fsearch.py <gun> <pick> <tag> '<json params>' [side] [body] [clip]"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, frontprod
gid, pick, tag, P = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4]); side = sys.argv[5] if len(sys.argv) > 5 else 'right'; body = sys.argv[6] if len(sys.argv) > 6 else 'pma'; clip = sys.argv[7] if len(sys.argv) > 7 else 'empty_reload'
P = {k: (tuple(v) if isinstance(v, list) else v) for k, v in P.items()}
frontprod.OUT = f'{renv.OUT}/work/search/{tag}'; frontprod.PARAMS[(pick, gid)] = P
spec, o = frontprod.build(gid, pick, clip, side, body, quiet=True)
print(tag, side, body, json.dumps(P), '| PEAK', o['motion']['peak_speed'], '| eye', o['eye_cm'], 'reach', o['reach'][0], 'sh', o['shoulder_pull_cm'], 'body', o['body_cm'], 'other', o['other_gun'], '| FAILS', o['fails'], flush=True)
