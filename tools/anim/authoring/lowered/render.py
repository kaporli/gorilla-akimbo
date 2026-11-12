"""Renders a lowered stance preview sequence (seq.py output) to an MP4 (first person | outside view, every 2nd frame,
15 fps) and a PNG strip of labelled first-person key frames. Guns and body come from the sequence json.
Blender scene: ../author/scene.py.

usage: render.py <prefix> <title>
  reads <prefix>_seq.glb and <prefix>_seq.json, writes <prefix>.mp4, <prefix>_strip.png, frames in <prefix>_frames
usage: render.py --pair <right gun> <left gun> <body> <prefix> <title> [--clips <dir>]
  runs seq.py for the two guns' manifest poses first (guns by id)
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = os.path.join(common.HERE, 'author', 'scene.py')
CAM = {"fov": 68, "pitch": 0, "eye": [0, 1.605, 0], "res": [512, 384], "cam_loc": [-1.1, 1.6, 1.95], "cam_tgt": [0, 0.25, 1.4]}


def blender(cfg):
    return subprocess.Popen([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', cfg],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def render(pre, title):
    meta = json.load(open(pre + '_seq.json')); lab = meta['labels']; N = len(lab)
    fdir = pre + '_frames'; os.makedirs(fdir, exist_ok=True)
    frames = list(range(0, N, 2)); procs = []
    for v in ('fpp', 'out'):
        for part in range(2):  # two Blender processes per view
            j = dict(CAM, clip_glb=pre + '_seq.glb', clip='seq', left_gun=common.gun(meta['left_gun'])['id'],
                     right_gun=common.gun(meta['right_gun'])['id'], body=meta.get('body', 'pma'), left_mag_clip=None,
                     frames=frames[part::2], out=f'{fdir}/{v}', view=v)
            cfg = f'{fdir}/{v}{part}.json'; json.dump(j, open(cfg, 'w'))
            procs.append(blender(cfg))
    for p in procs: p.wait()
    font = ImageFont.truetype('arialbd.ttf', 17)
    for k, f in enumerate(frames):
        a = Image.open(f'{fdir}/fpp_{f:03d}.png').convert('RGB'); b = Image.open(f'{fdir}/out_{f:03d}.png').convert('RGB')
        o = Image.new('RGB', (1024, 420), (20, 20, 24)); o.paste(a, (0, 36)); o.paste(b, (512, 36))
        ImageDraw.Draw(o).text((8, 7), f'{title}   f{f:03d}   {lab[f]}', fill=(255, 220, 0), font=font)
        o.save(f'{fdir}/c_{k:03d}.png')
    subprocess.run([common.need(common.path('ffmpeg')), '-y', '-loglevel', 'error', '-framerate', '15', '-i', f'{fdir}/c_%03d.png',
                    '-c:v', 'libx264', '-crf', '20', '-pix_fmt', 'yuv420p', pre + '.mp4'], check=True)
    # strip: the first frame of each segment plus one inside the longer ones (first person view)
    segs = []
    for i in range(0, N, 2):
        if not segs or lab[i] != segs[-1][0]: segs.append([lab[i], i, i])
        else: segs[-1][2] = i
    picks = []
    for l, s, e in segs:
        picks += [s] if e - s < 12 else [s, (s + e) // 2 // 2 * 2]
    picks = sorted(set(picks + [segs[-1][2]]))
    W, H, cols = 384, 288, 6
    st = Image.new('RGB', (W * cols, (H + 30) * ((len(picks) + cols - 1) // cols)), (20, 20, 24))
    small = ImageFont.truetype('arialbd.ttf', 14)
    for k, f in enumerate(picks):
        im = Image.open(f'{fdir}/fpp_{f:03d}.png').convert('RGB').resize((W, H)); x, y = (k % cols) * W, (k // cols) * (H + 30)
        st.paste(im, (x, y + 30)); ImageDraw.Draw(st).text((x + 6, y + 6), f'f{f} {lab[f]}'[:44], fill=(255, 220, 0), font=small)
    st.save(pre + '_strip.png')
    print('wrote', pre + '.mp4', pre + '_strip.png', len(frames), 'frames')


if __name__ == '__main__':
    argv = sys.argv[1:]
    clips = common.opt(argv, '--clips')
    if argv and argv[0] == '--pair':
        if HERE not in sys.path: sys.path.insert(0, HERE)
        import seq, checks
        rg, lg, body, pre, title = argv[1:6]
        glb = lambda g: common.need(checks.clip_of(common.gun(g)['lowered']['pose'], body, clips))
        res = seq.run(glb(rg), glb(lg), rg, lg, body, pre)
        print(res['lines'][-1])
    else:
        pre, title = argv[:2]
    render(pre, title)
