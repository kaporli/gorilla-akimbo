"""Blender preview: V's arms posed from an arm clip (glb), guns on the hand bones, magazines on their slots.

usage: blender -b --factory-startup --python scene.py -- config.json
Writes <out>_<frame>.png per frame (or <out>_<k>.png per seq entry). scene_bake.py saves a .blend instead.

config keys (only clip_glb, clip, frames, out are required; with seq only out):
  clip_glb, clip     arm clip glb and the animation name in it
  frames             list of clip frames to render
  seq                instead of frames: [[clip glb, clip name, frame, magazine frame], ...], one picture per entry;
                     frames may be fractional; implies one_mag
  out                output prefix
  left_gun, right_gun  manifest gun id (draws the gun's "parts" of weapons.json, else base1_01) or mesh stem (base1_01)
  left_parts, right_parts  mesh names (no .glb) drawn on that gun instead
  left_mag_clip, right_mag_clip  magazine animation to play (null: magazine stays seated)
  left_mag_offset, right_mag_offset  frames the magazine animation starts after the clip (frames mode)
  left_mag_glb, right_mag_glb  glb used for the magazine animation instead of the gun's mag_std set (magtrack set)
  one_mag            draw mag_std_01 only (default: also mag_stdr_01)
  wa_dirs            {mesh stem: folder} weapon anim folder for that gun instead of weapons.json weapon_anims
  body               pma (default) or pwa; female: true is the same as body pwa
  view               fpp (default) or out (3/4 outside view)
  eye, fov, pitch    fpp camera: eye point (glTF, default by body), horizontal fov 80, pitch down 0
  cam_loc, cam_tgt, angle, shift  outside camera: location, target (Blender axes), fov 50, lens shift
  res                [w, h], default [640, 360]
  bg, alpha          background colour, transparent film
  mask               only the right gun, white on black, flat
  mag_time           magazine animation sampled by time (weapon sets keep reduced keys) and the two magazine joints
                     merged: the one nearer its seat is drawn (rifles: the leaving and the incoming magazine)
  left_mag_track, right_mag_track   json of an own magazine track (reload/magtrack2.py): per frame the 4x4 of the
                     magazine mesh in gun axes and a scale; replaces the magazine animation
  left_parts_anim, right_parts_anim  draw the gun's moving parts (handle, bolt, latch): the body meshes keep their
                     skin and are posed from the gun's own anim set, clip = <side>_mag_clip
  proxy              outside view: grey blocks for torso, hips and thighs (from the rig joints), to read contacts
  blend              scene_bake.py: path of the .blend to save
"""
import os, sys, math, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import manifest
import numpy as np
import bpy
from glb import Glb
from fk import Clip
from mathutils import Matrix, Vector, Quaternion

EYE = {'pma': [0, 1.693, -0.044], 'pwa': [0, 1.6947, -0.0372]}
C = Matrix.Rotation(math.radians(90), 4, 'X'); Ci = C.inverted()


def m4(t, r): return Matrix.Translation(Vector(t)) @ Quaternion((r[3], r[0], r[1], r[2])).to_matrix().to_4x4()
def bl(M): return C @ M @ Ci


def imp(p):
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=p); new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.name.startswith('Icosphere'): o.hide_render = True
    return new


class Rigged:
    """Objects from one skinned glb, posed by world matrices (glTF space) per joint name."""
    def __init__(self, path, color=None):
        self.objs = imp(path); self.g = Glb(path)
        self.arm = next((o for o in self.objs if o.type == 'ARMATURE'), None)
        sk = self.g.j['skins'][0]; ibm = self.g.acc(sk['inverseBindMatrices'])
        self.bind = {}
        for k, j in enumerate(sk['joints']):
            M = Matrix([list(ibm[k][c::4]) for c in range(4)]).inverted()  # column-major -> rows
            self.bind[self.g.names[j]] = M
        self.corr = {}
        for b in self.arm.data.bones:
            if b.name in self.bind:
                self.corr[b.name] = bl(self.bind[b.name]).inverted() @ (self.arm.matrix_world @ b.matrix_local)
        for o in self.objs:
            if o.type == 'MESH' and color: o.color = color

    def pose(self, W, rigpar):
        """W: {joint: 4x4 glTF world}; rigpar: {joint: parent joint} of the animated rig. Joints missing from W follow
        the proximal joint of the nearest rig bone segment (mesh glbs store joints flat)."""
        if not hasattr(self, 'driver'):
            self.driver = {}
            have = [n for n in self.bind if n in W]
            segs = []
            for n in have:
                p = rigpar.get(n)
                if p in self.bind and p in W: segs.append((p, self.bind[p].translation, self.bind[n].translation))
                segs.append((n, self.bind[n].translation, self.bind[n].translation))
            for n in self.bind:
                if n in W: continue
                x = self.bind[n].translation; best = None
                for d, A, B in segs:
                    ab = B - A; t = 0 if ab.length < 1e-9 else max(0, min(1, (x - A).dot(ab) / ab.length_squared))
                    dist = (A + ab * t - x).length
                    if best is None or dist < best[0]: best = (dist, d)
                self.driver[n] = best[1] if best else None
        aw_i = self.arm.matrix_world.inverted()
        for b in self.arm.data.bones:
            n = b.name
            if n not in self.corr: continue
            if n in W: G = W[n]
            elif self.driver.get(n): d = self.driver[n]; G = W[d] @ self.bind[d].inverted() @ self.bind[n]
            else: G = self.bind[n]
            self.arm.pose.bones[n].matrix = aw_i @ bl(G) @ self.corr[n]
            bpy.context.view_layer.update()


_clips, _glbs = {}, {}


def glb(p):
    if p not in _glbs: _glbs[p] = Glb(p)
    return _glbs[p]


def clipworld(g, clip, f):
    """{joint: 4x4 glTF world} at frame f (clamped to the clip; a fractional f blends the two frames)."""
    key = (id(g), clip)
    if key not in _clips: _clips[key] = Clip(g, clip)
    c = _clips[key]; f = max(0.0, min(float(f), c.frames - 1))
    f0 = int(math.floor(f)); f1 = min(f0 + 1, c.frames - 1); w = f - f0
    W0 = c.world(f0)
    if w < 1e-6 or f1 == f0: return {g.names[i]: m4(t, r) for i, (t, r) in W0.items()}
    W1 = c.world(f1); out = {}
    for i, (t0, r0) in W0.items():
        t1, r1 = W1[i]; r0 = np.asarray(r0, float); r1 = np.asarray(r1, float)
        if np.dot(r0, r1) < 0: r1 = -r1
        q0 = Quaternion((r0[3], r0[0], r0[1], r0[2])); q1 = Quaternion((r1[3], r1[0], r1[1], r1[2]))
        q = q0.slerp(q1, w); tt = np.asarray(t0, float) * (1 - w) + np.asarray(t1, float) * w
        out[g.names[i]] = Matrix.Translation(Vector(tt)) @ q.to_matrix().to_4x4()
    return out


_tclips = {}


def magworld(g, clip, f):
    """{joint: 4x4} of a magazine set at 30 fps frame f, sampled by time; mag_std follows the magazine joint that is
    nearer its seat (frame 0), so one mesh shows the leaving and then the incoming magazine."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reload'))
    from wclip import TClip
    key = (id(g), clip)
    if key not in _tclips: _tclips[key] = TClip(g, clip)
    c = _tclips[key]; W = c.wf(int(f)); W0 = c.wf(0); out = {g.names[i]: m4(t, r) for i, (t, r) in W.items()}
    if 'magazine' in g.names and 'magazine_reload' in g.names and 'mag_stdr' in g.names and 'magazine_reload' in c.moved():
        d = {j: float(np.linalg.norm(W[g.names.index(j)][0] - W0[g.names.index(j)][0])) for j in ('magazine', 'magazine_reload')}
        if d['magazine_reload'] < d['magazine']:
            out['mag_std'] = out['mag_stdr']; out['magazine'] = out['magazine_reload']
    return out


def partworld(g, clip, f):
    """{joint: 4x4} of a gun's own anim set at 30 fps frame f, by time; clip None: the rest pose of the nodes."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reload'))
    from wclip import TClip
    key = (id(g), clip)
    if key not in _tclips: _tclips[key] = TClip(g, clip or g.j['animations'][0]['name'])
    c = _tclips[key]; W = c.wf(int(f) if clip else 0)
    return {g.names[i]: m4(t, r) for i, (t, r) in W.items()}


def proxies(W):
    """Grey blocks for the body, from rig joint positions (glTF world)."""
    def cyl(a, b, r, name):
        a = C @ Vector(a).to_4d(); b = C @ Vector(b).to_4d(); a = a.to_3d(); b = b.to_3d()
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=(b - a).length, location=(a + b) / 2)
        o = bpy.context.object; o.name = name; o.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler(); o.color = (0.36, 0.38, 0.42, 1)
    p = lambda n: W[n].translation
    cyl(p('Hips'), p('Spine3') + Vector((0, 0.12, 0)), 0.15, 'torso')
    cyl(p('Hips') + Vector((-0.17, -0.02, 0)), p('Hips') + Vector((0.17, -0.02, 0)), 0.12, 'belt')
    for s in ('Left', 'Right'): cyl(p(f'{s}UpLeg'), p(f'{s}Leg'), 0.085, f'thigh_{s}')


def gun_meshes(key):
    """cfg gun value -> (mesh stem, part names). A manifest id gives the gun's parts; a mesh stem gives base1_01."""
    for g in manifest.guns(all_=True):
        if g['id'] == key and g.get('mesh'):
            return g['mesh'], list(g.get('parts') or [g['mesh'] + '__base1_01'])
    return key, [key + '__base1_01']


def mesh_file(name):
    p = common.find('weapon_meshes', name + '.glb')
    if not p: raise SystemExit(f'no mesh {name}.glb in weapons.json paths weapon_meshes')
    return p


def anim_file(cfg, G, name):
    d = cfg.get('wa_dirs', {}).get(G)
    if d:
        p = d.rstrip('/\\') + '/' + name
        return p if os.path.exists(p) else None
    return common.find('weapon_anims', name)


def load_gun(cfg, side):
    """(mesh stem, body objects, magazine slot or None, magazines, magazine anim glb or None)"""
    s = side.lower()
    G, parts = gun_meshes(cfg[f'{s}_gun'])
    parts = cfg.get(f'{s}_parts') or parts
    body = []
    if cfg.get(f'{s}_parts_anim'):
        # skinned body parts, each with the anim glb that owns its joints (base1, or the shared receiver set)
        fam = G.split('__')[0]; rig = []
        for pn in parts:
            r = Rigged(mesh_file(pn), (0.55, 0.57, 0.6, 1)); best = None
            for an in (f'{G}__base1.anims.glb', f'{G}__rcv1.anims.glb', f'{fam}__rcv1.anims.glb'):
                f = anim_file(cfg, G, an)
                if not f: continue
                n = len([j for j in r.bind if j in Glb(f).names])
                if n and (best is None or n > best[0]): best = (n, f)
            rig.append((r, Glb(best[1]) if best else None))
        cfg[f'_{s}_rig'] = rig
    else:
        for pn in parts: body += imp(mesh_file(pn))
    for o in body:
        if o.type == 'ARMATURE': o.hide_render = True
        if o.type == 'MESH':
            o.modifiers.clear(); o.parent = None; o.color = (0.55, 0.57, 0.6, 1)
    meshes = [o for o in body if o.type == 'MESH']
    # the slot the magazine hangs on: in the gun's weapon anims, else in its receiver anims; none = no magazine
    wa = anim_file(cfg, G, f'{G}__base1.anims.glb')
    if not wa: return G, meshes, None, [], None
    gw = Glb(wa)
    if 'mag_slot' not in gw.names:
        wr = anim_file(cfg, G, f'{G}__rcv1.anims.glb')
        if wr: gw = Glb(wr)
    if 'mag_slot' not in gw.names: return G, meshes, None, [], None
    an = [a['name'] for a in gw.j['animations']]
    slot = clipworld(gw, 'reload' if 'reload' in an else an[0], 0)['mag_slot']
    ma = anim_file(cfg, G, f'{G}__mag_std.anims.glb')
    mg = Glb(ma) if ma else None
    if mg is None and not cfg.get(f'{s}_mag_glb'): return G, meshes, slot, [], None
    mags = []
    sufs = (('mag_std_01', (1, 0.35, 0.1, 1)), ('mag_stdr_01', (0.2, 0.8, 1, 1)))
    for suf, col in sufs[:1] if cfg.get('one_mag', 'seq' in cfg) else sufs:
        mp = common.find('weapon_meshes', f'{G}__{suf}.glb')
        if mp: mags.append(Rigged(mp, col))
    return G, meshes, slot, mags, mg


def build(cfg):
    """Loads arms and guns, sets camera and render settings. Returns the state used by frames()."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene; sc.render.fps = 30
    body = 'pwa' if cfg.get('female') else cfg.get('body', 'pma')
    arms = [Rigged(common.need(common.arm_mesh(body, s)), (0.85, 0.65, 0.5, 1)) for s in ('l', 'r')]
    guns = {}
    for side in ('Left', 'Right'):
        if cfg.get(f'{side.lower()}_gun'): guns[side] = load_gun(cfg, side)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'OBJECT'
    sc.display.shading.show_shadows = True
    sc.world = bpy.data.worlds.new('w'); sc.world.color = tuple(cfg.get('bg', [0.12, 0.13, 0.15]))
    if cfg.get('mask'):
        keep = set(guns['Right'][1])
        for o in bpy.data.objects:
            if o.type == 'MESH' and o not in keep: o.hide_render = True
        for o in keep: o.color = (1, 1, 1, 1)
        sc.display.shading.light = 'FLAT'; sc.display.shading.show_shadows = False; sc.world.color = (0, 0, 0)
        sc.view_settings.view_transform = 'Standard'
    sc.render.resolution_x, sc.render.resolution_y = cfg.get('res', [640, 360])
    if cfg.get('alpha'): sc.render.film_transparent = True; sc.render.image_settings.color_mode = 'RGBA'
    if cfg.get('view', 'fpp') == 'fpp':  # eyes, looking -Z (glTF forward)
        cam.data.sensor_fit = 'HORIZONTAL'; cam.data.angle = math.radians(cfg.get('fov', 80))
        cam.matrix_world = Matrix.Translation((C @ Vector(cfg.get('eye', EYE[body])).to_4d()).to_3d()) @ Matrix.Rotation(math.radians(90 - cfg.get('pitch', 0)), 4, 'X'); cam.data.clip_start = 0.02
    else:  # 3/4 view from the front left, above
        cam.data.sensor_fit = 'HORIZONTAL'; cam.data.angle = math.radians(cfg.get('angle', 50)); cam.data.shift_x, cam.data.shift_y = cfg.get('shift', [0, 0])
        loc = Vector(cfg.get('cam_loc', [-0.9, -1.3, 1.9])); tgt = Vector(cfg.get('cam_tgt', [0, -0.35, 1.45]))
        cam.location = loc; cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
    return sc, arms, guns


def entries(cfg):
    """[(file tag, clip glb, clip name, frame, {side: magazine frame})]"""
    if 'seq' in cfg:
        return [(k, gp, cn, f, {'left': mf, 'right': mf}) for k, (gp, cn, f, mf) in enumerate(cfg['seq'])]
    return [(f, cfg['clip_glb'], cfg['clip'], f, {s: max(0, f - cfg.get(f'{s}_mag_offset', 0)) for s in ('left', 'right')})
            for f in cfg['frames']]


def frames(cfg, state):
    """Poses the scene for each entry and yields its file tag."""
    sc, arms, guns = state
    par = {}
    for tag, gp, cn, f, mf in entries(cfg):
        ag = glb(gp)
        if gp not in par:
            par[gp] = {}
            for i, n in enumerate(ag.j['nodes']):
                for c in n.get('children', []): par[gp][ag.names[c]] = ag.names[i]
        W = clipworld(ag, cn, f)
        if cfg.get('proxy') and cfg.get('view') == 'out' and not bpy.data.objects.get('torso'): proxies(W)
        for r in arms: r.pose(W, par[gp])
        for side, (G, body, slot, mags, mg) in guns.items():
            s = side.lower(); Wg = W[f'Weapon{side}']
            for o in body: o.matrix_world = bl(Wg)
            for r, ga in cfg.get(f'_{s}_rig', []):
                PW = {}
                if ga is not None:
                    an = [a['name'] for a in ga.j['animations']]; cn = cfg.get(f'{s}_mag_clip')
                    PW = partworld(ga, cn if cn in an else None, mf[s])
                r.pose({k: Wg @ v for k, v in PW.items() if k in r.bind} or {k: Wg @ v for k, v in r.bind.items()}, {})
            if not mags: continue
            tr = cfg.get(f'{s}_mag_track')
            if tr:
                if isinstance(tr, str): tr = cfg[f'{s}_mag_track'] = json.load(open(tr))
                row = tr['frames'][min(int(mf[s]), len(tr['frames']) - 1)]
                M = Matrix([row['m'][0:4], row['m'][4:8], row['m'][8:12], row['m'][12:16]]) @ Matrix.Scale(max(row['s'], 1e-4), 4)
                for m in mags: m.pose({k: Wg @ M @ b for k, b in m.bind.items()}, {})
                continue
            wf = cfg.get(f'{s}_mag_clip'); mo = cfg.get(f'{s}_mag_glb'); mgx = glb(mo) if mo else mg
            if cfg.get('mag_time') and mgx and wf: MW = magworld(mgx, wf, mf[s])
            else: MW = clipworld(mgx, wf, mf[s]) if (mgx and wf) else (clipworld(mg, 'reload', 0) if mg else {})
            for m in mags: m.pose({k: Wg @ slot @ v for k, v in MW.items()}, {})
        bpy.context.view_layer.update()
        yield tag


def render(cfg):
    state = build(cfg); sc = state[0]; n = 0
    for tag in frames(cfg, state):
        sc.render.filepath = f"{cfg['out']}_{tag:03d}.png"; bpy.ops.render.render(write_still=True); n += 1
    print('DONE', n)


def config():
    return json.load(open(sys.argv[sys.argv.index('--') + 1]))


if __name__ == '__main__':
    render(config())
