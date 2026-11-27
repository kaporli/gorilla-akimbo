"""Does a tune pass every lowered check (authoring/lowered/checks.py, build.sh check --only lowered)? The clips of a
candidate are made in a scratch folder and run through the same preview sequence and limits as the check: the gun with the
reference gun (checks.lowered.pair_reference) both ways and two of the gun, per body.

  failures(gun id, family, tune, bodies)  -> [(check, value, limit)] of the limits it misses (empty: passes)
Used by autotune.py (the pose rule: a family applies only when a tune passes every check) and authoring/pose/checks.py.
The reference gun's own clip is made from weapons.json (lowered family and tune), so no clip folder is needed.
Scratch files go to the authoring work folder (paths.authoring_work, env AUTHORING).
"""
import importlib.util, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import common
import poses, lauthor as A

_spec = importlib.util.spec_from_file_location('lowered_checks', os.path.join(HERE, 'checks.py'))
LC = importlib.util.module_from_spec(_spec); sys.modules['lowered_checks'] = LC; _spec.loader.exec_module(LC)
T = common.manifest.load()['checks']['lowered']
_ref = {}


def make(fam, body, tune, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    A.build(poses.spec(fam, body, out, {'d': list(tune)} if tune is not None else None))
    return out


def ref_clip(body):
    if body not in _ref:
        g = common.gun(T['pair_reference']); low = g['lowered']
        _ref[body] = make(low['family'], body, low.get('tune'), f'{common.work("lowfit", "ref_" + str(os.getpid()))}/{body}/ref.glb')
    return _ref[body]


def failures(gid, fam, tune, bodies=None):
    bodies = bodies or common.BODIES; ref = T['pair_reference']; out = []
    with tempfile.TemporaryDirectory(prefix='cand_', dir=common.work('lowfit')) as tmp:
        for body in bodies:
            glb = make(fam, body, tune, f'{tmp}/{body}/g.glb'); rglb = ref_clip(body)
            res = [LC._pair(a)[1] for a in ((glb, rglb, gid, ref, body, None), (rglb, glb, ref, gid, body, None), (glb, glb, gid, gid, body, None))]
            w = LC.wrists(glb, body)
            seam = max(max(s[0], s[1]) for r in res for s in r['seam'].values())
            checks = [('seam', seam, T['seam_max'], seam <= T['seam_max']),
                      ('eye', min(r['labels']['lowered idle']['eye'] for r in res), T['eye_min_cm'], min(r['labels']['lowered idle']['eye'] for r in res) >= T['eye_min_cm']),
                      ('eye closer than raised', max(LC.eye_short(T, r) for r in res), T['eye_closer_than_raised_max_cm'], round(max(LC.eye_short(T, r) for r in res), 2) <= T['eye_closer_than_raised_max_cm']),
                      ('gun gap short', max(LC.gap_short(T, r) for r in res), 0, round(max(LC.gap_short(T, r) for r in res), 2) <= 0),
                      ('wrist idle', max(w['friendly_idlepose'].values()), T['wrist_idle_max_deg'], round(max(w['friendly_idlepose'].values()), 1) <= T['wrist_idle_max_deg']),
                      ('wrist any clip', max(max(v.values()) for v in w.values()), T['wrist_max_deg'], round(max(max(v.values()) for v in w.values()), 1) <= T['wrist_max_deg'])]
            out += [(f'{body} {n}', round(float(v), 2), lim) for n, v, lim, ok in checks if not ok]
    return out


def _job(a):
    return a, failures(*a)


def search(gid, fam, cands, bodies=None, jobs=None, first=False):
    """cands: [tune] best first. -> [(tune, failures)] in order; first=True stops at the first passing batch."""
    import concurrent.futures
    jobs = jobs or int(os.environ.get('JOBS', '4')); res = []
    with concurrent.futures.ProcessPoolExecutor(jobs) as ex:
        for i in range(0, len(cands), jobs):
            batch = cands[i:i + jobs]
            for t, f in zip(batch, ex.map(_job2, [(gid, fam, t, bodies) for t in batch])):
                res.append((t, f))
            if first and any(not f for _, f in res): break
    return res


def _job2(a):
    return failures(*a)
