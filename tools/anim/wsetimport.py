"""Import path for weapon-side sets on the gun's own components (Barrel: handle sets, tube/break part sets).

The plain import broke these sets in game; the vanilla base1 set run through it with no edits broke the same way, the
same set through this path did not (cxpart null tests, 2026-11-26). Three changes:
- frame count: WolvenKit writes ceil(duration * 30) frames, so a clip whose last key time rounds just below an integer
  frame loses its last frame (vanilla reload 86 -> 85). The last key time is nudged up by 2e-6 relative.
- compression: a SIMD game clip comes back SIMD without rotation quantization (maxRotationCompression 0,
  simdQuantizationBits 0), as the magazine sets that work in game (the game's base1 sets use 12-bit quantization).
  A compressed game clip (Dian, Hercules, Masamune, Warden) keeps the compressed format and its own hints: converted
  to SIMD it broke in game (Hercules, round 9).
- metadata: isTrackConstant, motionExtraction and events back to the game set's clip of the same name; duration
  (clip and buffer) = (numFrames - 1) / 30.
field_diff() lists every CR2W field of the imported set that differs from the game set (the round trip check).
"""
import json, struct
import numpy as np

FPS = 30.0
# Fields that may differ from the game set: the clip's own length, the compression above, where the data is stored,
# and two encoder counts that follow from which joints move.
ALLOWED = ('.duration', '.numFrames', '.quantizationBits', '.dataAddress.', '.inplaceCompressedBuffer.',
           '.numTranslationsToCopy', '.numTranslationsToEvalAlignedToSimd',
           '.numAnimKeys', '.numAnimKeysRaw', '.numConstAnimKeys')      # key counts of the compressed format: follow the keys


def prep_glb(src, dst, keep=None):
    """keep: clip names to import; the others are left out (a clip the game set lacks stays the game's: no clip)."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from glb import Glb
    g = Glb(src)
    if keep is not None: g.j['animations'] = [a for a in g.j['animations'] if a['name'] in keep]
    for a in g.j['animations']:
        remap = {}
        for s in a['samplers']:
            i = s['input']
            if i not in remap:
                t = g.acc(i).copy(); n = int(round(t[-1] * FPS)); T = n / FPS
                if abs(t[-1] - T) < 1e-4: t[-1] = T * (1 + 2e-6)
                remap[i] = g.add_acc(t, 'SCALAR')
            s['input'] = remap[i]
        ex = a.setdefault('extras', {}); h = ex.get('optimizationHints') or {}
        if h.get('preferSIMD', True):
            ex['optimizationHints'] = dict(h, preferSIMD=True, maxRotationCompression=0, simdQuantizationBits=0)
        # else: a game clip in the compressed format keeps its own hints (the glb carries the game clip's extras); the
        # Hercules base1 set through this path comes back equal to the game's in every field (cxpart/herc, 2026-11-26)
    g.save(dst)


def _clips(p):
    r = json.load(open(p, encoding='utf-8'))['Data']['RootChunk']
    return r, {e['Data']['animation']['Data']['name']['$value']: e['Data'] for e in r['animations']}


def _ids(x, out):
    if isinstance(x, dict):
        if 'HandleId' in x: out.append(int(x['HandleId']))
        for v in x.values(): _ids(v, out)
    elif isinstance(x, list):
        for v in x: _ids(v, out)
    return out


def _renumber(x, nxt):
    """A copy of a subtree from another file with its handle ids moved past nxt[0] (references inside it follow)."""
    import copy
    x = copy.deepcopy(x); m = {}
    for i in _ids(x, []): m[str(i)] = str(nxt[0]); nxt[0] += 1
    def walk(y):
        if isinstance(y, dict):
            for k in ('HandleId', 'HandleRefId'):
                if k in y and str(y[k]) in m: y[k] = m[str(y[k])]
            for v in y.values(): walk(v)
        elif isinstance(y, list):
            for v in y: walk(v)
    walk(x); return x


def patch(imported_json, vanilla_json, out_json, keys=None):
    """keys: {clip: expected frame count}; raises when the import wrote another count."""
    j = json.load(open(imported_json, encoding='utf-8')); _, V = _clips(vanilla_json); nxt = [max(_ids(j, [0])) + 1]
    for e in j['Data']['RootChunk']['animations']:
        d = e['Data']; a = d['animation']['Data']; b = a['animBuffer']['Data']; name = a['name']['$value']
        if keys and name in keys and b['numFrames'] != keys[name]:
            raise SystemExit(f'{imported_json}: {name} has {b["numFrames"]} frames, {keys[name]} keys written')
        v = V.get(name)
        if v:
            vb = v['animation']['Data']['animBuffer']['Data']
            if 'isTrackConstant' in vb and 'isTrackConstant' in b: b['isTrackConstant'] = vb['isTrackConstant']      # a SIMD-only field
            a['motionExtraction'] = _renumber(v['animation']['Data']['motionExtraction'], nxt); d['events'] = _renumber(v.get('events'), nxt)
        dur = float(np.float32((b['numFrames'] - 1) / FPS)); a['duration'] = dur; b['duration'] = dur
    json.dump(j, open(out_json, 'w', encoding='utf-8'), indent=1)


def _flat(d, p=''):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            if k in ('Bytes', 'BufferId', 'HandleId'): continue
            out.update(_flat(v, p + '.' + k))
    elif isinstance(d, list):
        for i, v in enumerate(d): out.update(_flat(v, f'{p}[{i}]'))
    else:
        out[p] = d
    return out


def field_diff(vanilla_json, ours_json):
    """(bad, allowed): lists of (clip or 'set', field, game value, our value)."""
    rv, V = _clips(vanilla_json); ro, O = _clips(ours_json); bad, ok = [], []
    skip = ('animations', 'animationDataChunks')
    sv, so = _flat({k: v for k, v in rv.items() if k not in skip}), _flat({k: v for k, v in ro.items() if k not in skip})
    for k in sorted(set(sv) | set(so)):
        if sv.get(k) != so.get(k): bad.append(('set', k, sv.get(k), so.get(k)))
    for name, d in O.items():
        if name not in V: bad.append((name, 'clip not in the game set', None, None)); continue
        fv, fo = _flat(V[name]), _flat(d)
        for k in sorted(set(fv) | set(fo)):      # the buffer format must stay the game's (no exception)
            if fv.get(k) != fo.get(k):
                (ok if any(s in k for s in ALLOWED) else bad).append((name, k, fv.get(k), fo.get(k)))
    return bad, ok
