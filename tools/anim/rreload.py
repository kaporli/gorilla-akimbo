"""Build step `rreload` (part of `all`): the rifles' own one-handed reload sets.

Per rifle that owns a model variable and has guns[].reload.slots in weapons.json, per body and hand:
  arm set       <body>_dual_wield_<side>_rreload_<gun>.anims: a copy of the per-hand reload set the gun has today
                (its own raised-pose reload set when it has a raised pose, else the shared one; both built by the
                `reload` step, which must have run) with the six reload clips replaced by the pick clips
                (paths.rreload_clips, made by authoring/reload/prod.py; rarmset.py). It takes that set's place for
                the gun's model variable: genxl.py leaves the variable out, genrxl.py enters it at priority 64.
                Equip, unequip, melee and the recoil additives stay as they were.
  magazine set  <gun>__rmag_<body>_<side>.anims: the clips' magazine tracks under the same six names in a copy of
                the gun's own magazine set (rmagset.py)
then GorillaAkimboRifles.archive and its .archive.xl (genrxl.py). Clips are padded to rarmset.good_keys.
`rreload check` in WORK: every built set is exported back and compared with what went in (key counts, SIMD buffers,
gun path, magazine path); report in WORK/rreload/roundtrip.txt.

Additive: build.py only registers the step. Sets go to SETS/GorillaAkimboRifles.
"""
import os, sys, json, shutil, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
sys.path.insert(0, HERE)
import manifest, rarmset

ARCHIVE = 'GorillaAkimboRifles'
SLOTS = ('reload', 'reload_01', 'reload_02')
EMPTY = ('empty_reload', 'empty_reload_01', 'empty_reload_02')
TAKE = {'light': 'A', 'heavy': 'B'}


def owners():
    return [g for g in manifest.guns() if g.get('reload', {}).get('slots')]


def arm_set(body, side, gid): return f'{body}_dual_wield_{side}_rreload_{gid}'
def mag_set(body, side, gid): return f'{gid}__rmag_{body}_{side}'
def wrapper(body, side, gid): return f'gorillaakimbo_rmag_{gid}_{body}_{side}'


def clip_file(d, body, gid, side, pick, take, clip, ext='.glb'):
    p = f'{d}/{body}/{gid}_{side}_{pick}{take}_{clip}{ext}'
    if not os.path.exists(p) and clip == 'empty_reload':      # a gun whose two clips are the same has one
        p = f'{d}/{body}/{gid}_{side}_{pick}{take}_reload{ext}'
    return p


def plan():
    """[(gun, body, side, arm set name, magazine set name, [(clip name, clip glb, track json, keys)])]"""
    d = manifest.path('rreload_clips'); out = []
    for g in owners():
        r = g['reload']; take = TAKE[r['weight']]
        for body in manifest.bodies():
            for side in ('right', 'left'):
                items = []
                for names, clip in ((SLOTS, 'reload'), (EMPTY, 'empty_reload')):
                    for name, pick in zip(names, r['slots']):
                        glb = clip_file(d, body, g['id'], side, pick, take, clip); tr = glb[:-4] + '_track.json'
                        n = json.load(open(glb[:-4] + '.json'))['frames'] if os.path.exists(glb[:-4] + '.json') else 0
                        items.append((name, glb, tr, rarmset.good_keys(n) if n else 0))
                out.append((g, body, side, arm_set(body, side, g['id']), mag_set(body, side, g['id']), items))
    return out


def today_set(body, side, g):
    """The per-hand reload set the gun's model variable gets from genxl.py today."""
    r = g.get('raised') or {}
    return manifest.raised_reload_set(body, side, r['pose']) if r.get('family', 'none') != 'none' else manifest.reload_set(body, side)


def variables():
    """Model variables whose per-hand reload set this step replaces (genxl.py skips them)."""
    return {v for g in owners() for v in manifest.gun_vars(g)}


def gamefile(depot):
    return manifest.path('rreload_gamefiles') + '/' + depot.replace('\\', '/')


def step(B):
    """B: the build module (its helpers and folders)."""
    if not plan():
        print('rreload: no gun of this build has reload slots, nothing to build'); return
    tmp = B.fresh(B.WORK + '/tmp_rreload'); sets = f'{B.SETS}/{ARCHIVE}'; os.makedirs(sets, exist_ok=True)
    keep = list(SLOTS + EMPTY)

    def one(g, body, side, aname, mname, items):
        miss = [p for _, p, t, _ in items for p in (p, t) if not os.path.exists(p)]
        if miss: B.die(f'rreload: missing clip {miss[0]} (authoring/reload/prod.py build)')
        suf = '' if side == 'right' else '_l'; base = today_set(body, side, g); d = f'{tmp}/{aname}'; os.makedirs(d)
        B.py('rarmset.py', B.need(f'{B.WORK}/tmp_reload/{base}/{base}.glb'), f'{d}/{aname}.glb', *[f'{p}={n}{suf}:{k}' for n, p, _, k in items])
        B.import_set(f'{d}/{aname}.glb', B.need(f'{B.SETS}/GorillaAkimbo/{base}.anims'), None, f'{sets}/{aname}.anims')
        m = g['reload']['magazine']; van = B.need(gamefile(m['set'])); d = f'{tmp}/{mname}'; os.makedirs(d)
        mesh = manifest.find('weapon_meshes', g['mesh'] + '__mag_std_01.glb')
        B.py('rmagset.py', B.need(van + '.glb'), B.need(gamefile(m['weapon_set']) + '.glb'), B.need(mesh), f'{d}/{mname}.glb', *[f'{t}={n}:{k}' for n, _, t, k in items])
        B.import_set(f'{d}/{mname}.glb', van, keep, f'{sets}/{mname}.anims')

    B.parallel([lambda a=a: one(*a) for a in plan()])
    stage = B.fresh(f'{B.WORK}/pack/{ARCHIVE}'); os.makedirs(stage + '/gorillaakimbo/animations')
    names = [n for _, _, _, a, m, _ in plan() for n in (a, m)]
    for n in names: shutil.copyfile(B.need(f'{sets}/{n}.anims'), f'{stage}/gorillaakimbo/animations/{n}.anims')
    B.wk('pack', stage, '-o', B.WORK + '/pack'); os.makedirs(B.OUT_ARCHIVE, exist_ok=True)
    shutil.copyfile(B.need(f'{B.WORK}/pack/{ARCHIVE}.archive'), f'{B.OUT_ARCHIVE}/{ARCHIVE}.archive')
    print(f'packed {B.OUT_ARCHIVE}/{ARCHIVE}.archive ({len(names)} sets)')
    print(f'{ARCHIVE}.archive.xl:', B.py('genrxl.py', f'{B.OUT_ARCHIVE}/{ARCHIVE}.archive.xl', sets).strip())
    roundtrip(B, sets)


def roundtrip(B, sets):
    """Every built set exported back by WolvenKit and compared with the glb it was imported from."""
    sys.path.insert(0, HERE + '/authoring/reload')
    from glb import Glb
    from fk import Clip
    out = B.fresh(B.WORK + '/rreload'); rows = []; bad = 0
    for g, body, side, aname, mname, items in plan():
        for name, kind in ((aname, 'arm'), (mname, 'mag')):
            d = f'{out}/{name}'; os.makedirs(d); shutil.copyfile(f'{sets}/{name}.anims', f'{d}/{name}.anims')
            B.run([B.WK, 'export', f'{d}/{name}.anims', '-o', d, '-gp', B.GAME], check=False); B.wk('convert', 's', f'{d}/{name}.anims', '-o', d); via = ''
            if not os.path.exists(f'{d}/{name}.anims.glb'):
                # WolvenKit cannot export the gun's raised-pose reload set this one is a copy of (the base set fails the
                # same way): the six clips are checked through a copy of the Lexington set instead, metadata on the real set.
                src = B.source_set('reload_source', body=body, side=side); x = f'{d}/lex'; os.makedirs(x); shutil.copyfile(src, f'{x}/{name}.anims')
                o = B.run(['pwsh', '-NoProfile', '-File', f'{HERE}/animimport.ps1', f'{B.WORK}/tmp_rreload/{name}/{name}.glb'.replace('/', chr(92)), f'{x}/{name}.anims'.replace('/', chr(92))])
                B.wk('export', f'{x}/{name}.anims', '-o', x, '-gp', B.GAME); shutil.copyfile(f'{x}/{name}.anims.glb', f'{d}/{name}.anims.glb'); via = ' (path through a Lexington set copy: the real set does not export)'
            back = Glb(f'{d}/{name}.anims.glb'); src = Glb(f'{B.WORK}/tmp_rreload/{name}/{name}.glb'); j = json.load(open(f'{d}/{name}.anims.json', encoding='utf-8'))
            meta = {e['Data']['animation']['Data']['name']['$value']: e['Data']['animation']['Data']['animBuffer']['Data'] for e in j['Data']['RootChunk']['animations']}
            suf = '_l' if (side == 'left' and kind == 'arm') else ''; node = ('Weapon' + side.capitalize()) if kind == 'arm' else 'magazine'
            for cn, _, _, keys in items:
                cn2 = cn + suf; a, b = Clip(src, cn2), Clip(back, cn2); i, k = src.names.index(node), back.names.index(node); dev = 0.0
                for f in range(min(a.frames, b.frames)):
                    dev = max(dev, float(np.linalg.norm(np.array(a.world(f)[i][0]) - np.array(b.world(f)[k][0]))) * 100)
                simd = meta[cn2]['$type'] == 'animAnimationBufferSimd'; ok = b.frames == keys and simd and dev < (0.85 if kind == 'arm' else 0.5)
                bad += not ok
                rows.append(f"{'ok ' if ok else 'BAD'} {name:44s} {cn2:18s} keys {keys} back {b.frames} numFrames {meta[cn2].get('numFrames')} {'SIMD' if simd else meta[cn2]['$type']} {node} path dev {dev:.3f} cm{via}")
    open(f'{out}/roundtrip.txt', 'w').write('\n'.join(rows) + '\n')
    print(f'round trip: {len(rows)} clips, {bad} bad; report {out}/roundtrip.txt')
    return bad
