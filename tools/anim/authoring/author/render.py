"""Preview renders of an arm clip through scene.py (Blender in background mode) and ffmpeg.

usage:
  render.py sheet <clip glb> <clip> <name> <frames csv>   contact sheet of chosen frames (first person row, outside row)
  render.py gif   <clip glb> <clip> <name> [frame count]  first person | outside view, every 2nd frame, 15 fps
  render.py mp4   <clip glb> <clip> <name> [frame count]  the same as MP4, every frame, 30 fps
  render.py strip <clip glb> <clip> <name> <frame>=<label> ...   labelled first-person key frames, 4 per row
  render.py compare <name> <before glb> <after glb>       2x2 before | after video at half speed and a strip: the end
                                                          of the clip, then the idle pose the graph returns to
options:
  --left G, --right G   guns: manifest id (all parts of weapons.json) or mesh stem (base1_01 only);
                        default w_smg__arasaka_shingen and w_smg__militech_saratoga
  --body pma|pwa        V's arms (default pma)
  --reload left|right|both|none   gun whose magazine plays its reload animation (default left)
  --cam author|game     first-person camera: author = fov 80, pitched 18 down from V's eyes (shows the whole motion);
                        game = the in-game fit, eye [0, 1.605, 0], level, fov 97
  --views fpp,out       views to render
  --res W,H             size of one view (sheet 480,270; compare 960,540; else 640,360)
  --step N, --fps N     gif, mp4: frame step and frame rate (fps default 30 / step)
  --set key=json        any other scene.py config key, repeatable (e.g. --set cam_loc=[-1.1,1.6,1.95])
  --dir D               output folder (default <authoring_work>/author/prev)
  compare: --clip smack, --from 50, --to last frame, --idle 20 (idle frames appended), --labels "BEFORE|AFTER"
Frames are kept in <dir>/<name>/."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
from glb import Glb
from fk import Clip
from PIL import Image, ImageDraw, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__)).replace('\\', '/')
CAMS = {'author': {'fov': 80, 'pitch': 18}, 'game': {'fov': 97, 'pitch': 0, 'eye': [0, 1.605, 0]}}
OUT_CAM = {'cam_loc': [-1.1, 1.6, 1.95], 'cam_tgt': [0, 0.25, 1.4]}


def font(size, bold=True):
    try: return ImageFont.truetype('arialbd.ttf' if bold else 'arial.ttf', size)
    except OSError: return ImageFont.load_default()


class Job:
    def __init__(self, argv, res):
        o = lambda n, d=None: common.opt(argv, n, d)
        self.base = {'left_gun': o('--left', 'w_smg__arasaka_shingen'), 'right_gun': o('--right', 'w_smg__militech_saratoga'),
                     'body': o('--body', 'pma')}
        rl = o('--reload', 'left')
        for s in ('left', 'right'):
            self.base[f'{s}_mag_clip'] = 'reload' if rl in (s, 'both') else None
        self.cam = CAMS[o('--cam', 'author')]
        self.views = o('--views', 'fpp,out').split(',')
        self.res = [int(x) for x in o('--res', res).split(',')]
        self.step = o('--step'); self.fps = o('--fps')
        self.dir = o('--dir') or common.work('author', 'prev')
        self.clip = o('--clip', 'smack'); self.first = int(o('--from', 50)); self.last = o('--to')
        self.idle = int(o('--idle', 20)); self.labels = o('--labels', 'BEFORE|AFTER').split('|')
        self.extra = {}
        while '--set' in argv:
            k, v = o('--set').split('=', 1); self.extra[k] = json.loads(v)

    def frames_dir(self, name):
        d = f'{self.dir}/{name}'; os.makedirs(d, exist_ok=True)
        return d

    def cfg(self, view, out, **kw):
        j = dict(self.base); j.update({'view': view, 'res': self.res, 'out': out})
        j.update(self.cam if view == 'fpp' else OUT_CAM); j.update(kw); j.update(self.extra)
        return j

    def run(self, cfgs):
        """Renders the configs, one Blender process each, side by side."""
        procs = []
        for c in cfgs:
            p = c['out'] + '.json'; json.dump(c, open(p, 'w'))
            procs.append((p, subprocess.Popen([common.need(common.path('blender')), '-b', '--factory-startup', '--python',
                                               HERE + '/scene.py', '--', p], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                              text=True, errors='replace')))
        for p, pr in procs:
            log = pr.communicate()[0]
            if 'DONE' not in log:
                raise SystemExit(f'scene.py failed for {p}:\n' + '\n'.join(log.splitlines()[-12:]))

    def render(self, name, tag, glb, clip, frames):
        """Renders the frames in each view; returns {view: {frame: png}}."""
        d = self.frames_dir(name); files = {v: {f: f'{d}/{tag}{v}_{f:03d}.png' for f in frames} for v in self.views}
        self.run([self.cfg(v, f'{d}/{tag}{v}', clip_glb=glb, clip=clip, frames=frames) for v in self.views])
        return files


def ffmpeg(args):
    subprocess.run([common.need(common.path('ffmpeg')), '-y', '-loglevel', 'error'] + args, check=True)


def clip_frames(glb, clip):
    return Clip(Glb(glb), clip).frames


def sheet(argv):
    job = Job(argv, '480,270'); glb, clip, name, fr = argv[:4]; fr = [int(x) for x in fr.split(',')]
    files = job.render(name, 'sheet_', glb, clip, fr); W, H = job.res; nv = len(job.views)
    o = Image.new('RGB', (W * min(len(fr), 6), H * nv * ((len(fr) + 5) // 6)))
    for k, f in enumerate(fr):
        for r, v in enumerate(job.views):
            im = Image.open(files[v][f]).convert('RGB'); ImageDraw.Draw(im).text((6, 6), f'{f}', fill=(255, 255, 0))
            o.paste(im, ((k % 6) * W, ((k // 6) * nv + r) * H))
    out = f'{job.dir}/{name}_sheet.png'; o.save(out); print('wrote', out)


def movie(argv, kind):
    job = Job(argv, '640,360'); glb, clip, name = argv[:3]
    n = int(argv[3]) if len(argv) > 3 else clip_frames(glb, clip)
    step = int(job.step or (2 if kind == 'gif' else 1)); fps = str(job.fps or 30 // step)
    fr = list(range(0, n, step)); files = job.render(name, '', glb, clip, fr); W, H = job.res; d = job.frames_dir(name)
    for k, f in enumerate(fr):
        o = Image.new('RGB', (W * len(job.views), H))
        for c, v in enumerate(job.views): o.paste(Image.open(files[v][f]).convert('RGB'), (c * W, 0))
        o.save(f'{d}/c_{k:03d}.png')
    out = f'{job.dir}/{name}.{kind}'; src = ['-framerate', fps, '-i', f'{d}/c_%03d.png', '-frames:v', str(len(fr))]
    if kind == 'gif':
        ffmpeg(src + ['-filter_complex', 'split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=none', out])
    else:
        ffmpeg(src + ['-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '20', out])
    print('wrote', out, len(fr), 'frames', os.path.getsize(out), 'bytes')


def strip(argv):
    job = Job(argv, '640,360'); glb, clip, name = argv[:3]; job.views = ['fpp']
    labels = dict(a.split('=', 1) for a in argv[3:]); fr = [int(k) for k in labels]
    files = job.render(name, 'strip_', glb, clip, fr)['fpp']; W, H = job.res; cols = 4; ft = font(22)
    o = Image.new('RGB', (W * cols, H * ((len(fr) + cols - 1) // cols)), (20, 20, 24))
    for k, f in enumerate(fr):
        im = Image.open(files[f]).convert('RGB'); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, W, 34), fill=(0, 0, 0)); d.text((10, 5), f'frame {f}: {labels[str(f)]}', fill=(255, 220, 0), font=ft)
        o.paste(im, ((k % cols) * W, (k // cols) * H))
    out = f'{job.dir}/{name}_strip.png'; o.save(out); print('wrote', out)


def compare(argv):
    """Before | after of a clip's end and the idle pose that follows (in-game camera unless --cam is given)."""
    if '--cam' not in argv: argv += ['--cam', 'game']
    job = Job(argv, '960,540'); name, before, after = argv[:3]; W, H = job.res; d = job.frames_dir(name)
    idle = common.need(common.idle_glb(job.base['body'])); cfgs = []
    for tag, glb in (('before', before), ('after', after)):
        last = int(job.last) if job.last else clip_frames(glb, job.clip) - 1
        seq = [[glb, job.clip, f, f] for f in range(job.first, last + 1)] + [[idle, 'idlepose_shoulder', 0, last]] * job.idle
        cfgs += [job.cfg(v, f'{d}/{tag}_{v}', seq=seq) for v in job.views]
    job.run(cfgs)
    nc = last - job.first + 1; n = nc + job.idle; big, small = font(26), font(22, False)
    lab = lambda k: f'clip f{job.first + k}' if k < nc else f'idle +{k - nc + 1}'
    get = lambda tag, v, k: Image.open(f'{d}/{tag}_{v}_{k:03d}.png').convert('RGB')
    for k in range(n):
        g = Image.new('RGB', (2 * W, H * len(job.views)))
        for c, tag in enumerate(('before', 'after')):
            for r, v in enumerate(job.views):
                im = get(tag, v, k); dr = ImageDraw.Draw(im)
                if r == 0: dr.text((14, 10), job.labels[c], font=big, fill=(255, 230, 0))
                dr.text((14, H - 36), lab(k) + ('   graph back in idle' if k >= nc else ''), font=small, fill=(255, 255, 255))
                g.paste(im, (c * W, r * H))
        g.save(f'{d}/g_{k:03d}.png')
    mp4 = f'{job.dir}/{name}_compare.mp4'
    ffmpeg(['-framerate', '15', '-i', f'{d}/g_%03d.png', '-frames:v', str(n), '-vf', 'format=yuv420p', '-c:v', 'libx264', '-crf', '18', mp4])
    # strip: three late clip frames, the first idle frame, and the change at the switch to idle (x4)
    cols = sorted({max(0, nc - 26), max(0, nc - 11), nc - 1, min(nc, n - 1)}); v0 = job.views[0]; tw, th = 480, 480 * H // W
    S = Image.new('RGB', (tw * (len(cols) + 1), th * 2 + 40), (20, 20, 20))
    for r, tag in enumerate(('before', 'after')):
        for c, k in enumerate(cols):
            im = get(tag, v0, k).resize((tw, th)); ImageDraw.Draw(im).text((8, 6), f'{tag}: {lab(k)}', font=small, fill=(255, 230, 0))
            S.paste(im, (c * tw, 40 + r * th))
        df = ImageChops.difference(get(tag, v0, nc - 1), get(tag, v0, min(nc, n - 1))).point(lambda x: min(255, x * 4)).resize((tw, th))
        ImageDraw.Draw(df).text((8, 6), f'{tag}: last clip frame vs idle (x4)', font=small, fill=(255, 230, 0))
        S.paste(df, (len(cols) * tw, 40 + r * th))
    ImageDraw.Draw(S).text((10, 8), f'{name}: {v0} view. Last column: change at the switch to idle.', font=small, fill=(255, 255, 255))
    png = f'{job.dir}/{name}_strip.png'; S.save(png); print('wrote', mp4, png)


if __name__ == '__main__':
    cmds = {'sheet': sheet, 'gif': lambda a: movie(a, 'gif'), 'mp4': lambda a: movie(a, 'mp4'), 'strip': strip, 'compare': compare}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        raise SystemExit(__doc__)
    cmds[sys.argv[1]](sys.argv[2:])
