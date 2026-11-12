"""Partner categories of the single picks: how far a partner gun is from touching the magazine in each pick, and the
category that fits it.
usage: partner.py measure <gun id>[,<gun id>]   contact table of the guns and their nearest categories
       partner.py split [K]                     categories recomputed from data/table_<pick>.json (default K 3)
measure: per pick and contact frame, the signed distance (cm) of the gun (with V's hand on it) to the magazine box
along the pick's striking axis: + = it penetrates and must back out, - = it misses and must advance. Plus the deepest
penetration into the top-magazine gun's body and the clearances (other arm, own forearm beyond the grip, eye) over the
strike window f12-34. The nearest category per family is the one whose shifts leave the smallest residual; put the
three names in the gun's weapons.json "partner" row (flip, doubletap, uppercut). A residual above the family's
max_residual_cm in data/categories.json calls for a new category: add it there (name, shift_cm per column, members)
and build its clips with gen_smg.py --cats <name>.
split: 1D minimax grouping per family from the recorded tables (the source of data/categories.json)."""
import os, sys, json, itertools
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
from geo import (load_spec, pick_spec, gunM, magJ, app, box_signed, shingen_depth, segdist, load, hand, M4,
                 PICKS, SIDES, EYES, DATA)
import gen_smg

WIN = range(12, 35)
# family -> its columns (pick, contact frame); the order of shift_cm in data/categories.json
FAM = {'09': [('v09', 'c15'), ('v09', 'c25'), ('m09', 'c15'), ('m09', 'c25')], '06': [('v06', 'c25'), ('m06', 'c25')],
       '10': [('v10', 'c25'), ('m10', 'c25')]}
FAMPICK = {'10': 'flip', '09': 'doubletap', '06': 'uppercut'}


def along(P, u):
    """+ m the gun must back out along -u to clear the magazine box (penetration), - m it must advance along u to touch"""
    def hit(s): return (box_signed(P + s * u) > 0).any()
    if hit(0):
        s = 0.0
        while hit(-s) and s < 0.3: s += 0.002
        return s
    for s in np.arange(0.002, 0.3, 0.002):
        if hit(s): return -s
    return -0.3


def measure(pid, guns, body='pma'):
    """{gun: row} for one pick; 'hand' is V's bare hand"""
    side, _, fr, _ = PICKS[pid]; sh, st = SIDES[side]
    ns = load_spec(pick_spec(pid, body))
    Wc = {f: ns['solveW'](f) for f in WIN}; W0 = ns['solveW'](0)
    G = {f: gunM(ns, st, f) for f in WIN}; GS = {f: gunM(ns, sh, f) for f in WIN}; MJ = {f: magJ(ns, sh, f) for f in WIN}
    ix = ns['idx']; res = {}
    U = {}
    for c in fr:
        kind, v = gen_smg.AX[pid]; v = np.array(v, float); v /= np.linalg.norm(v)
        wv = G[c][:3, :3] @ v if kind == 'local' else v
        U[c] = np.linalg.inv(MJ[c])[:3, :3] @ wv
    HAND = hand(body, st)[::2]
    for key in guns:
        V = HAND if key == 'hand' else np.vstack([load(key)['all'][::2], HAND])
        row = {}
        for c in fr:
            P = app(np.linalg.inv(MJ[c]) @ G[c], V); d = box_signed(P); k = np.argmax(d)
            row[f'c{c}'] = round(float(along(P, U[c])) * 100, 1); row[f'c{c}_pt'] = np.round(V[k], 3).tolist()
        body_ = 0; arm = ownarm = eye = 9
        P0w = app(M4(*ns['gun_pose'](st, 0)), V); wr0, el0 = W0[ix[f'{st}Hand']][0], W0[ix[f'{st}ForeArm']][0]
        far0 = np.linalg.norm(P0w - wr0, axis=1) > 0.10
        own0 = segdist(P0w[far0], el0, wr0).min() - 0.04 if far0.any() else 9
        for f in WIN:
            Pw = app(G[f], V); W = Wc[f]
            body_ = max(body_, shingen_depth(app(np.linalg.inv(GS[f]), Pw)))
            wr, el, kn = W[ix[f'{sh}Hand']][0], W[ix[f'{sh}ForeArm']][0], W[ix[f'{sh}HandMiddle1']][0]
            arm = min(arm, segdist(Pw, wr, kn).min() - 0.045, segdist(Pw, el, wr).min() - 0.04)
            wr2, el2 = W[ix[f'{st}Hand']][0], W[ix[f'{st}ForeArm']][0]
            far = np.linalg.norm(Pw - wr2, axis=1) > 0.10
            if far.any(): ownarm = min(ownarm, segdist(Pw[far], el2, wr2).min() - 0.04)
            eye = min(eye, np.linalg.norm(Pw - EYES[body], axis=1).min())
        row.update(body=round(body_ * 100, 1), arm=round(arm * 100, 1), ownarm=round(ownarm * 100, 1),
                   own_idle=round(min(own0, 9) * 100, 1), eye=round(eye * 100, 1))
        res[key] = row
    return res


def tables():
    return {p: json.load(open(DATA + f'table_{p}.json')) for p in PICKS}


def split(fam, K, T=None):
    """minimax grouping of the partners by needed shift: (max residual cm, groups, group shifts)"""
    T = T or tables()
    keys = [k for k in T['v10'] if k != 'hand']
    X = np.array([[T[p][k][c] for p, c in FAM[fam]] for k in keys]); x = X.mean(1); o = np.argsort(x); n = len(o); best = None
    for cuts in itertools.combinations(range(1, n), K - 1):
        b = [0, *cuts, n]; sc = 0
        for i in range(K):
            S = X[o[b[i]:b[i + 1]]]; sc = max(sc, ((S.max(0) - S.min(0)) / 2).max())
        if best is None or sc < best[0]: best = (sc, b)
    sc, b = best
    groups = [[keys[j] for j in o[b[i]:b[i + 1]]] for i in range(K)]
    mids = [((X[o[b[i]:b[i + 1]]].max(0) + X[o[b[i]:b[i + 1]]].min(0)) / 2) for i in range(K)]
    return sc, groups, mids


def nearest(fam, x):
    """(category name, residual cm) for a gun's shifts x (one per column of the family)"""
    best = None
    for c in gen_smg.categories()[fam]['cats']:
        r = float(np.abs(np.array(x) - np.array(c['shift_cm'])).max())
        if best is None or r < best[1]: best = (c['name'], r)
    return best


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == 'measure':
        guns = a[1].split(',')
        T = {p: measure(p, guns) for p in PICKS}
        for g in guns:
            print(g)
            for p in PICKS:
                print(f'  {p} ({PICKS[p][0]} {PICKS[p][1]}):', ' '.join(f'{k}={v}' for k, v in T[p][g].items() if not k.endswith('_pt')))
            row = []
            for fam in ('10', '09', '06'):
                x = [T[p][g][c] for p, c in FAM[fam]]
                name, r = nearest(fam, x); row.append(name)
                lim = gen_smg.categories()[fam]['max_residual_cm']
                print(f'  {FAMPICK[fam]:9s} shifts {x} -> {name}, residual {r:.1f} cm (family limit {lim})' + ('  NEW CATEGORY?' if r > lim + 1e-9 else ''))
            print(f'  weapons.json: "partner": {{"{common.gun("shingen")["topmag"]["clip_name"]}": {json.dumps(row)}}}')
    elif a and a[0] == 'split':
        K = int(a[1]) if len(a) > 1 else 3
        for fam in ('09', '06', '10'):
            sc, groups, mids = split(fam, K)
            print(f'{FAMPICK[fam]} K={K} max residual {sc:.1f} cm')
            for g, m in zip(groups, mids): print('   shift', np.round(m, 2).tolist(), ', '.join(g))
    else:
        print(__doc__)
