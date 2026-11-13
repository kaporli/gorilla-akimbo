"""Minimal glb read/write for WolvenKit anim exports."""
import json, struct
import numpy as np

COMP = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8, 5122: np.int16}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def fit_track_keys(keys, n, fps=30.0):
    """The game clip's float track keys (per-frame values such as which magazine mesh shows) fitted to a clip of n
    keys: keys at or past the end are dropped, and each track holds its last value up to frame n-1. Without the hold
    the import fills missing frames with 0, which hid the rifles' magazine for the last padded frames."""
    keys = [k for k in keys or [] if k['time'] < n / fps - 1e-4]
    last = {}
    for k in keys:
        if k['trackIndex'] not in last or k['time'] >= last[k['trackIndex']]['time']:
            last[k['trackIndex']] = k
    for i, k in sorted(last.items()):
        f = int(round(k['time'] * fps))
        keys += [{**k, 'time': round(g / fps, 6)} for g in range(f + 1, n)]
    return sorted(keys, key=lambda k: (k['time'], k['trackIndex']))


class Glb:
    def __init__(self, path):
        b = open(path, 'rb').read()
        jl = struct.unpack('<I', b[12:16])[0]
        self.j = json.loads(b[20:20 + jl])
        o = 20 + jl
        bl = struct.unpack('<I', b[o:o + 4])[0]
        self.bin = bytearray(b[o + 8:o + 8 + bl])
        self.names = [n.get('name') for n in self.j['nodes']]

    def acc(self, i):
        a = self.j['accessors'][i]
        v = self.j['bufferViews'][a['bufferView']]
        n = NCOMP[a['type']]
        dt = COMP[a['componentType']]
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        arr = np.frombuffer(bytes(self.bin[off:off + a['count'] * n * np.dtype(dt).itemsize]), dtype=dt)
        return arr.reshape(a['count'], n).astype(np.float64) if n > 1 else arr.astype(np.float64)

    def add_acc(self, arr, kind):
        arr = np.asarray(arr, dtype=np.float32)
        while len(self.bin) % 4:
            self.bin.append(0)
        off = len(self.bin)
        self.bin += arr.tobytes()
        self.j['bufferViews'].append({'buffer': 0, 'byteOffset': off, 'byteLength': arr.nbytes})
        a = {'bufferView': len(self.j['bufferViews']) - 1, 'componentType': 5126,
             'count': int(arr.shape[0]), 'type': kind}
        if kind == 'SCALAR':
            a['min'] = [float(arr.min())]; a['max'] = [float(arr.max())]
        self.j['accessors'].append(a)
        return len(self.j['accessors']) - 1

    def anim(self, name):
        return next(a for a in self.j['animations'] if a['name'] == name)

    def tracks(self, name):
        """{(node name, path): (times, values)}"""
        a = self.anim(name)
        out = {}
        for c in a['channels']:
            s = a['samplers'][c['sampler']]
            out[(self.names[c['target']['node']], c['target']['path'])] = (self.acc(s['input']), self.acc(s['output']))
        return out

    def save(self, path):
        self.j['buffers'][0]['byteLength'] = len(self.bin)
        js = json.dumps(self.j, separators=(',', ':')).encode()
        js += b' ' * (-len(js) % 4)
        bn = bytes(self.bin) + b'\0' * (-len(self.bin) % 4)
        total = 12 + 8 + len(js) + 8 + len(bn)
        with open(path, 'wb') as f:
            f.write(struct.pack('<III', 0x46546C67, 2, total))
            f.write(struct.pack('<II', len(js), 0x4E4F534A)); f.write(js)
            f.write(struct.pack('<II', len(bn), 0x004E4942)); f.write(bn)
