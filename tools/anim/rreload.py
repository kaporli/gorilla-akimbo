"""Build step `rreload` (part of `all`): the guns' own one-handed reload sets (rifles, and SMGs and shotguns).

Per gun that owns a model variable and has guns[].reload.slots in weapons.json, per body and hand:
  arm set       <body>_dual_wield_<side>_rreload_<gun>.anims: a copy of the per-hand reload set the gun has today
                (its own raised-pose reload set when it has a raised pose, else the shared one; both built by the
                `reload` step, which must have run) with the six reload clips replaced by the pick clips
                (reload.clips names the paths entry of the clip folder, default paths.rreload_clips; rarmset.py).
                It takes that set's place for the gun's model variable: genxl.py leaves the variable out,
                genrxl.py enters it at priority 63. Equip, unequip, melee and the recoil additives stay as they were.
  magazine set  <gun>__rmag_<body>_<side>.anims: the clips' magazine tracks under the same six names in a copy of
                the gun's own magazine set (rmagset.py; rmagset2.py for reload.magazine.builder "rmagset2", the
                SMG and shotgun tracks where both magazines are in view at once). None for reload.magazine null
                (shell-by-shell tube guns).
Each gun's sets go into reload.archive (default GorillaAkimboRifles), with its .archive.xl (genrxl.py). Clips are
padded to rarmset.good_keys. Then every built set is exported back and compared with what went in (key counts, SIMD
buffers, gun path, magazine path, magazine float tracks); report in WORK/rreload/roundtrip.txt.

Additive: build.py only registers the step. Sets go to SETS/<archive>.
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
    # A gun whose own reload is parked (reload.parked) plays the generic reload clips: no own sets are built or wired.
    return [g for g in manifest.guns() if g.get('reload', {}).get('slots') and not g['reload'].get('parked')]


def archive(g): return g['reload'].get('archive', ARCHIVE)
def archives(): return list(dict.fromkeys(archive(g) for g in owners()))
def arm_set(body, side, gid): return f'{body}_dual_wield_{side}_rreload_{gid}'
def mag_set(body, side, gid): return f'{gid}__rmag_{body}_{side}'
def wrapper(body, side, gid): return f'gorillaakimbo_rmag_{gid}_{body}_{side}'
def has_magazine(g): return bool(g['reload'].get('magazine'))
def quick_set(gid): return f'{gid}__rmagq'
def quick_wrapper(gid): return f'gorillaakimbo_rmagq_{gid}'
FALLBACK = ('reload_start', 'reload_loop')


def fallback_files(g, body, side):
    """The quick-drop fallback clip and its idle hold (reload.fallback; authoring/reload/fallback.py)."""
    d = manifest.path(g['reload']['fallback'].get('clips', 'smg_fallback_clips'))
    return f'{d}/{body}/{g["id"]}_{side}_FB_reload.glb', f'{d}/{body}/{g["id"]}_{side}_FBloop_reload.glb'


def clip_file(d, body, gid, side, pick, take, clip, ext='.glb'):
    p = f'{d}/{body}/{gid}_{side}_{pick}{take}_{clip}{ext}'
    if not os.path.exists(p):      # a gun whose two clips are the same has one (named after either)
        other = 'reload' if clip == 'empty_reload' else 'empty_reload'
        q = f'{d}/{body}/{gid}_{side}_{pick}{take}_{other}{ext}'
        if os.path.exists(q): p = q
    return p


def has_parts(g): return bool(g['reload'].get('parts'))
def has_shells(g): return bool(g['reload']['parts'].get('shell_set'))
def ships_barrels(g): return g['reload']['parts'].get('barrels', True)      # false: built and checked, not packed (see the manifest note)
def part_sets(body, side, g): return f'{g["id"]}__rpart_{body}_{side}', (f'{g["id"]}__rshell_{body}_{side}' if has_shells(g) else None)
def quick_part_sets(g): return f'{g["id"]}__rpartq', (f'{g["id"]}__rshellq' if has_shells(g) else None)


def parts_plan():
    """[(gun, body, side, barrel set, shell set, [(clip name, spec json, keys, (hide start, hide end))])]: the gun part
    sets of shell-fed guns (reload.parts, rpartset.py), same slots and key counts as the arm set."""
    out = []
    for g, body, side, aname, mname, items in plan():
        if not has_parts(g): continue
        r = g['reload']; take = TAKE[r['weight']]; d = manifest.path(r.get('clips', 'rreload_clips')); rows = []
        for names, clip in ((SLOTS, 'reload'), (EMPTY, 'empty_reload')):
            for name, pick in zip(names, r['slots']):
                L = r['layout'][pick + take][clip]; k = next(x[3] for x in items if x[0] == name)
                rows.append((name, clip_file(d, body, g['id'], side, pick, take, clip, '.json'), k, (L['hide_start'], L['hide_end'])))
        out.append((g, body, side, *part_sets(body, side, g), rows))
    return out


def quick_parts_plan():
    """[(gun, barrel set, shell set, [(clip name, 'idle', keys, None)])]: the parts at the idle in every slot the
    weapon may play during the quick-drop fallback (the six reload slots, reload_start, reload_loop)."""
    out = []
    for g in owners():
        if not (has_parts(g) and g['reload'].get('fallback')): continue
        k = g['reload']['fallback']['layout']['keys']
        loop = json.load(open(fallback_files(g, 'pma', 'right')[1][:-4] + '.json'))['frames']
        rows = [(n, 'idle', k, None) for n in SLOTS + EMPTY] + [('reload_start', 'idle', k, None), ('reload_loop', 'idle', rarmset.good_keys(loop), None)]
        out.append((g, *quick_part_sets(g), rows))
    return out


def missing_parts(g):
    """Draft files whose part motion has no set: every drafted file when the gun has no part set; the files with
    drafted shells when it has a barrel set but no shell set."""
    d = drafted_parts(g)
    if not has_parts(g) if g.get('reload') else True: return d
    out = [] if ships_barrels(g) else [p for p in d if p.endswith('_phys.json')]
    if not has_shells(g): out += [p for p in d if p.endswith('_objects.json') and json.load(open(p)).get('names')]
    return out


def drafted_parts(g):
    """Draft files with gun part motion (_objects.json, _phys.json) of a gun's own clips without a magazine set: the
    build check fails when such a gun has no part set."""
    r = g.get('reload') or {}
    if not r.get('slots') or r.get('magazine') or r.get('parked'): return []   # parked: plays its quick drop only
    d = manifest.path(r.get('clips', 'rreload_clips')); take = TAKE[r['weight']]; out = []
    for body in manifest.bodies():
        for side in ('right', 'left'):
            for clip in ('reload', 'empty_reload'):
                for pick in r['slots']:
                    b = clip_file(d, body, g['id'], side, pick, take, clip, '.json')[:-5]
                    out += [p for p in (b + '_objects.json', b + '_phys.json') if os.path.exists(p)]
    return sorted(set(out))


def plan():
    """[(gun, body, side, arm set name, magazine set name or None, [(clip name, clip glb, track json, keys)])]"""
    out = []
    for g in owners():
        r = g['reload']; take = TAKE[r['weight']]; d = manifest.path(r.get('clips', 'rreload_clips'))
        for body in manifest.bodies():
            for side in ('right', 'left'):
                items = []
                for names, clip in ((SLOTS, 'reload'), (EMPTY, 'empty_reload')):
                    for name, pick in zip(names, r['slots']):
                        glb = clip_file(d, body, g['id'], side, pick, take, clip); tr = glb[:-4] + '_track.json'
                        n = json.load(open(glb[:-4] + '.json'))['frames'] if os.path.exists(glb[:-4] + '.json') else 0
                        items.append((name, glb, tr, rarmset.good_keys(n) if n else 0))
                if r.get('fallback'):
                    # the quick-drop fallback in the graph's shell-loop slots (reload_start, then reload_loop)
                    for name, glb in zip(FALLBACK, fallback_files(g, body, side)):
                        n = json.load(open(glb[:-4] + '.json'))['frames'] if os.path.exists(glb[:-4] + '.json') else 0
                        items.append((name, glb, None, rarmset.good_keys(n) if n else 0))
                out.append((g, body, side, arm_set(body, side, g['id']), mag_set(body, side, g['id']) if has_magazine(g) else None, items))
    return out


def quick_plan():
    """[(gun, quick magazine set name)]: one magazine set per gun with a fallback and a magazine (body and hand do not
    matter: the magazine stays seated, the old and fresh mesh swap at the fallback's swap frame, out of view)."""
    return [(g, quick_set(g['id'])) for g in owners() if g['reload'].get('fallback') and has_magazine(g)]


def today_set(body, side, g):
    """The per-hand reload set the gun's model variable gets from genxl.py today."""
    r = g.get('raised') or {}
    return manifest.raised_reload_set(body, side, r['pose']) if r.get('family', 'none') != 'none' else manifest.reload_set(body, side)


def variables():
    """Model variables whose per-hand reload set this step replaces (genxl.py skips them)."""
    return {v for g in owners() for v in manifest.gun_vars(g)}


def gamefile(depot, key='rreload_gamefiles'):
    """A game file by depot path: the first of the paths entry's folders that holds it."""
    rel = depot.replace('\\', '/')
    for d in manifest.paths(key):
        if os.path.exists(f'{d}/{rel}'):
            return f'{d}/{rel}'
    return manifest.paths(key)[0] + '/' + rel


def gameglb(raw):
    """The glb export of a game anim set: next to it, else by name in paths.weapon_anims."""
    if os.path.exists(raw + '.glb'):
        return raw + '.glb'
    return manifest.find('weapon_anims', os.path.basename(raw) + '.glb') or raw + '.glb'


def gun_map(clip_glb):
    """The gun's own frame for each frame of the clip (its parts time-mapped onto the clip's beats), from the clip's
    spec: _part_frames (FRONT) or _gun_map (GRIP, BULLPUP, TOP), as production built the magazine sets."""
    s = json.load(open(clip_glb[:-4] + '.json'))
    return s.get('_part_frames') or s.get('_gun_map')


def step(B):
    """B: the build module (its helpers and folders)."""
    if not plan():
        print('rreload: no gun of this build has reload slots, nothing to build'); return
    tmp = B.fresh(B.WORK + '/tmp_rreload')
    for a in archives(): os.makedirs(f'{B.SETS}/{a}', exist_ok=True)
    keep = list(SLOTS + EMPTY)

    def one(g, body, side, aname, mname, items):
        sets = f'{B.SETS}/{archive(g)}'
        miss = [p for _, p, t, _ in items for p in ((p, t) if mname and t else (p,)) if not os.path.exists(p)]
        if miss: B.die(f'rreload: missing clip {miss[0]} (authoring/reload/prod.py build, fallback.py build)')
        suf = '' if side == 'right' else '_l'; base = today_set(body, side, g); d = f'{tmp}/{aname}'; os.makedirs(d)
        ph = ['--phases'] if g['reload'].get('fallback') else []
        B.py('rarmset.py', B.need(f'{B.WORK}/tmp_reload/{base}/{base}.glb'), f'{d}/{aname}.glb', *[f'{p}={n}{suf}:{k}' for n, p, _, k in items], *ph)
        B.import_set(f'{d}/{aname}.glb', B.need(f'{B.SETS}/GorillaAkimbo/{base}.anims'), None, f'{sets}/{aname}.anims')
        if not mname:
            return
        items = [x for x in items if x[0] in keep]
        m = g['reload']['magazine']; key = m.get('gamefiles', 'rreload_gamefiles'); van = B.need(gamefile(m['set'], key)); d = f'{tmp}/{mname}'; os.makedirs(d)
        wset = B.need(gameglb(gamefile(m['weapon_set'], key)))
        mesh = manifest.find('weapon_meshes', g['mesh'] + '__mag_std_01.glb')
        if m.get('builder') == 'rmagset2':
            args = []
            for n, p, t, k in items:
                mp = f'{d}/{n}_map.json'; json.dump(gun_map(p), open(mp, 'w')); args.append(f'{t}={n}:{k}:{mp}')
            B.py('rmagset2.py', B.need(gameglb(van)), wset, B.need(mesh), f'{d}/{mname}.glb', *args, '--report', f'{d}/{mname}_check.json')
        else:
            B.py('rmagset.py', B.need(gameglb(van)), wset, B.need(mesh), f'{d}/{mname}.glb', *[f'{t}={n}:{k}' for n, _, t, k in items])
        B.import_set(f'{d}/{mname}.glb', van, keep, f'{sets}/{mname}.anims')

    def quick(g, qname):
        # every slot: seated, the swap at the fallback's swap frame (out of view), seated
        r = g['reload']; fb = r['fallback']['layout']; take = TAKE[r['weight']]; d = f'{tmp}/{qname}'; os.makedirs(d)
        m = r['magazine']; key = m.get('gamefiles', 'rreload_gamefiles'); van = B.need(gamefile(m['set'], key))
        wset = B.need(gameglb(gamefile(m['weapon_set'], key))); mesh = manifest.find('weapon_meshes', g['mesh'] + '__mag_std_01.glb')
        cd = manifest.path(r.get('clips', 'rreload_clips')); args = []
        for names, clip in ((SLOTS, 'reload'), (EMPTY, 'empty_reload')):
            for name, pick in zip(names, r['slots']):
                tr = json.load(open(clip_file(cd, 'pma', g['id'], 'right', pick, take, clip)[:-4] + '_track.json'))
                row = dict(tr['frames'][-1]); row['state'] = 'seated'; row.pop('m2', None); row.pop('s2', None)
                syn = {'frames': [row] * fb['length'], 'release': fb['swap'] - 1, 'clip': tr['clip']}
                tp = f'{d}/{name}_track.json'; json.dump(syn, open(tp, 'w')); args.append(f'{tp}={name}:{fb["keys"]}')
        B.py('rmagset2.py', B.need(gameglb(van)), wset, B.need(mesh), f'{d}/{qname}.glb', *args, '--report', f'{d}/{qname}_check.json')
        B.import_set(f'{d}/{qname}.glb', van, keep, f'{B.SETS}/{archive(g)}/{qname}.anims')

    def parts(g, bname, sname, rows):
        # gun part sets (rpartset.py): pump and shells as the drafts show them, or every part at the idle (quick)
        pr = g['reload']['parts']; key = pr.get('gamefiles', 'rreload_gamefiles'); d = f'{tmp}/{bname}'; os.makedirs(d)
        bvan = B.need(gamefile(pr['barrel_set'], key))
        args = [f'{p}={n}:{k}' + (f':{h[0]}:{h[1]}' if h else '') for n, p, k, h in rows]
        if sname:
            svan = B.need(gamefile(pr['shell_set'], key)); mesh = B.need(manifest.find('weapon_meshes', pr.get('shell_mesh', g['mesh']) + '__mag_std_01.glb'))
            B.py('rpartset.py', B.need(gameglb(bvan)), B.need(gameglb(svan)), mesh, f'{d}/{bname}.glb', f'{tmp}/{sname}.glb', *args, '--report', f'{d}/{bname}_check.json')
        else:
            B.py('rpartset.py', B.need(gameglb(bvan)), '-', '-', f'{d}/{bname}.glb', '-', *args, '--report', f'{d}/{bname}_check.json')
        kp = [n for n, _, _, _ in rows]; sets = f'{B.SETS}/{archive(g)}'
        if ships_barrels(g):
            base = bvan
            if pr.get('strip_set'):
                # WolvenKit's import fails into some game sets (Satara base1: "Index was out of range", its own reload
                # clip too); a copy with only the reload clips imports. The other clips fall through to the game's set.
                x = f'{d}/strip'; os.makedirs(x); base = f'{x}/{os.path.basename(bvan)}'; shutil.copyfile(bvan, base)
                B.wk('convert', 's', base, '-o', x); js = base + '.json'; j = json.load(open(js, encoding='utf-8'))
                j['Data']['RootChunk']['animations'] = [e for e in j['Data']['RootChunk']['animations'] if e['Data']['animation']['Data']['name']['$value'] in SLOTS + EMPTY]
                json.dump(j, open(js, 'w', encoding='utf-8'), indent=1); os.remove(base); B.wk('convert', 'd', js, '-o', x); B.need(base)
            B.import_set(f'{d}/{bname}.glb', base, kp, f'{sets}/{bname}.anims')
        if sname:
            os.makedirs(f'{tmp}/{sname}'); shutil.move(f'{tmp}/{sname}.glb', f'{tmp}/{sname}/{sname}.glb')
            B.import_set(f'{tmp}/{sname}/{sname}.glb', svan, kp, f'{sets}/{sname}.anims')

    # GA_REUSE_SETS=1: sets already in SETS are kept (a part-set-only rebuild; their round trip is the earlier build's)
    reuse = os.environ.get('GA_REUSE_SETS') == '1'
    have = lambda g, n: reuse and os.path.exists(f'{B.SETS}/{archive(g)}/{n}.anims')
    B.parallel([lambda a=a: one(*a) for a in plan() if not (have(a[0], a[3]) and (not a[4] or have(a[0], a[4])))]
               + [lambda a=a: quick(*a) for a in quick_plan() if not have(a[0], a[1])]
               + [lambda a=a: parts(a[0], a[3], a[4], a[5]) for a in parts_plan()] + [lambda a=a: parts(*a) for a in quick_parts_plan()])
    for a in archives():
        sets = f'{B.SETS}/{a}'
        stage = B.fresh(f'{B.WORK}/pack/{a}'); os.makedirs(stage + '/gorillaakimbo/animations')
        names = [n for g, _, _, an, mn, _ in plan() if archive(g) == a for n in (an, mn) if n] + [q for g, q in quick_plan() if archive(g) == a]
        names += [n for x in parts_plan() if archive(x[0]) == a for n in (x[3] if ships_barrels(x[0]) else None, x[4]) if n]
        names += [n for x in quick_parts_plan() if archive(x[0]) == a for n in (x[1] if ships_barrels(x[0]) else None, x[2]) if n]
        for n in names: shutil.copyfile(B.need(f'{sets}/{n}.anims'), f'{stage}/gorillaakimbo/animations/{n}.anims')
        B.wk('pack', stage, '-o', B.WORK + '/pack'); os.makedirs(B.OUT_ARCHIVE, exist_ok=True)
        shutil.copyfile(B.need(f'{B.WORK}/pack/{a}.archive'), f'{B.OUT_ARCHIVE}/{a}.archive')
        print(f'packed {B.OUT_ARCHIVE}/{a}.archive ({len(names)} sets)')
        print(f'{a}.archive.xl:', B.py('genrxl.py', f'{B.OUT_ARCHIVE}/{a}.archive.xl', sets).strip())
    magchecks(B)
    partchecks(B)
    roundtrip(B)


def partchecks(B):
    """rpartset check results in one report (WORK/rreload_mag/partcheck.txt); stops the build when a clip misses."""
    rows = []; bad = 0
    names = [(x[3], x[0]) for x in parts_plan()] + [(x[1], x[0]) for x in quick_parts_plan()]
    for bname, g in names:
        f = f'{B.WORK}/tmp_rreload/{bname}/{bname}_check.json'
        if not os.path.exists(f):
            rows.append(f'BAD {bname} no check report'); bad += 1; continue
        r = json.load(open(f)); sl = {x['name']: x for x in r['slots']}
        for c in r['check']:
            s = sl[c['name']]; e = c['end']
            ok = (c['float_keys_per_track_equal_keys'] and e.get('magazine_cm', 0) < 0.05 and e.get('magazine_deg', 0) < 0.5 and e.get('magazine_shown', 1) == 1
                  and e.get('reload_shown', 0) == 0 and e['base_joints_cm'] < 0.1 and e['base_joints_deg'] < 0.5 and c.get('shell_worst_cm', 0) < 0.05
                  and c.get('shell_worst_deg', 0) < 0.5 and c.get('part_worst', 0) < (0.1 if c.get('part_unit') == 'cm' else 0.5) and s.get('hand_back_in_hidden', True))
            bad += not ok
            rows.append(f"{'ok ' if ok else 'BAD'} {bname:28s} {c['name']:16s} shells {c.get('shell_worst_cm', '-')} cm {c.get('shell_worst_deg', '-')} deg, "
                        f"part {c.get('part_joint')} {c.get('part_worst', '-')} {c.get('part_unit', '')}, end {e}, hand-back f{s.get('hand_back')}, "
                        f"shells left out in view f{s.get('dropped_frames_in_view', [])}, joints {s.get('assign')}")
    if rows:
        os.makedirs(B.WORK + '/rreload_mag', exist_ok=True)
        open(B.WORK + '/rreload_mag/partcheck.txt', 'w').write('\n'.join(rows) + '\n')
        print(f'part sets rebuilt from their keys: {len(rows)} clips, {bad} bad; report {B.WORK}/rreload_mag/partcheck.txt')
    if bad:
        B.die(f'rreload: {bad} part set clips miss their draft or the idle ({B.WORK}/rreload_mag/partcheck.txt)')


def magchecks(B):
    """rmagset2 check results (every mesh matrix rebuilt from the written keys against the track) in one report."""
    rows = []
    for g, body, side, aname, mname, _ in plan():
        f = f'{B.WORK}/tmp_rreload/{mname}/{mname}_check.json' if mname else None
        if f and os.path.exists(f):
            r = json.load(open(f))
            for c in r['check']:
                rows.append(f"{mname:28s} {c['name']:16s} worst {c['worst_cm']:.4f} cm, float keys per track = keys {c['float_keys_per_track_equal_keys']}, last float {c['last_float']}")
    for g, q in quick_plan():
        f = f'{B.WORK}/tmp_rreload/{q}/{q}_check.json'
        if os.path.exists(f):
            for c in json.load(open(f))['check']:
                rows.append(f"{q:28s} {c['name']:16s} worst {c['worst_cm']:.4f} cm, float keys per track = keys {c['float_keys_per_track_equal_keys']}, last float {c['last_float']}")
    if rows:
        os.makedirs(B.WORK + '/rreload_mag', exist_ok=True)
        open(B.WORK + '/rreload_mag/magcheck.txt', 'w').write('\n'.join(rows) + '\n')
        print(f'magazine sets rebuilt from their keys: {len(rows)} clips; report {B.WORK}/rreload_mag/magcheck.txt')


def floats(extras, keys):
    """Per float track, its value on each of keys frames (a key holds until the next; a constant track holds its one
    value over the whole clip, whatever its key time)."""
    out = {}
    for k in extras.get('constTrackKeys') or []:
        out[k['trackIndex']] = [k['value']] * keys
    for k in sorted(extras.get('trackKeys') or [], key=lambda k: k['time']):
        f = int(round(k['time'] * 30.0))
        row = out.setdefault(k['trackIndex'], [None] * keys)
        for g in range(max(f, 0), keys): row[g] = k['value']
    return out


def roundtrip(B):
    """Every built set exported back by WolvenKit and compared with the glb it was imported from."""
    sys.path.insert(0, HERE + '/authoring/reload')
    from glb import Glb
    from fk import Clip
    out = B.fresh(B.WORK + '/rreload'); rows = []; bad = 0
    jobs = [(g, body, side, aname, 'arm', items) for g, body, side, aname, mname, items in plan()]
    jobs += [(g, body, side, mname, 'mag', [x for x in items if x[0] in SLOTS + EMPTY]) for g, body, side, aname, mname, items in plan() if mname]
    jobs += [(g, 'pma', 'right', q, 'mag', [(n, None, None, g['reload']['fallback']['layout']['keys']) for n in SLOTS + EMPTY]) for g, q in quick_plan()]
    for x in parts_plan() + [(q[0], 'pma', 'right', q[1], q[2], q[3]) for q in quick_parts_plan()]:
        prow = [(n, None, None, k) for n, _, k, _ in x[5]]
        jobs += ([(x[0], x[1], x[2], x[3], 'part', prow)] if ships_barrels(x[0]) else []) + ([(x[0], x[1], x[2], x[4], 'mag', prow)] if x[4] else [])
    if os.environ.get('GA_REUSE_SETS') == '1':
        jobs = [j for j in jobs if os.path.exists(f'{B.WORK}/tmp_rreload/{j[3]}/{j[3]}.glb')]
    for g, body, side, name, kind, items in jobs:
        sets = f'{B.SETS}/{archive(g)}'
        if True:
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
            nodes = [node]
            if kind == 'part':      # the pump or barrel joint; every base joint is checked by partchecks
                nodes = [g['reload']['parts']['joint']]
            elif kind == 'mag' and node not in src.names:     # break-open shell sets: every shell joint
                nodes = [n for n in ('left_magazine', 'left_magazine_reload', 'right_magazine', 'right_magazine_reload', 'l_bullet', 'l_bullet_reload', 'r_bullet', 'r_bullet_reload') if n in src.names]
            node = nodes[0]
            for cn, _, _, keys in items:
                cn2 = cn + suf; a, b = Clip(src, cn2), Clip(back, cn2); dev = 0.0
                for nd in nodes:
                    i, k = src.names.index(nd), back.names.index(nd)
                    for f in range(min(a.frames, b.frames)):
                        dev = max(dev, float(np.linalg.norm(np.array(a.world(f)[i][0]) - np.array(b.world(f)[k][0]))) * 100)
                simd = meta[cn2]['$type'] == 'animAnimationBufferSimd'; ok = b.frames == keys and simd and dev < (0.85 if kind == 'arm' else 0.5)
                fl = ''
                if kind == 'mag':
                    # which magazine mesh shows: every frame of each float track as written, held to the last key
                    fa, fb = floats(src.anim(cn2).get('extras') or {}, keys), floats(back.anim(cn2).get('extras') or {}, keys)
                    diff = sum(1 for t in fa for f in range(keys) if fa[t][f] is not None and (fb.get(t, [None] * keys)[f] is None or abs(fa[t][f] - fb[t][f]) > 1e-4))
                    ok = ok and diff == 0 and len(fa) == len(fb); fl = f' float tracks {len(fa)}/{len(fb)}, {diff} frames differ'
                if kind == 'arm' and cn == 'reload' and g['reload'].get('fallback'):
                    # the shell-loop End state plays the LoopEnd phase of this clip: it must come back as written
                    ent = next(e for e in j['Data']['RootChunk']['animations'] if e['Data']['animation']['Data']['name']['$value'] == cn2)
                    evs = (((ent['Data'].get('events') or {}).get('Data') or {}).get('events')) or []
                    ph = sorted((x['Data']['eventName']['$value'], x['Data']['startFrame'], x['Data']['durationInFrames']) for x in evs if x['Data']['$type'] == 'animAnimEvent_Phase')
                    want = sorted([('Loop', 0, keys - 2), ('LoopEnd', keys - 2, 2)]); ok = ok and ph == want; fl += f' phases {ph}'
                bad += not ok
                rows.append(f"{'ok ' if ok else 'BAD'} {name:44s} {cn2:18s} keys {keys} back {b.frames} numFrames {meta[cn2].get('numFrames')} {'SIMD' if simd else meta[cn2]['$type']} {node} path dev {dev:.3f} cm{fl}{via}")
    open(f'{out}/roundtrip.txt', 'w').write('\n'.join(rows) + '\n')
    print(f'round trip: {len(rows)} clips, {bad} bad; report {out}/roundtrip.txt')
    return bad
