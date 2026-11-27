"""Real-speed renders of the Carnage flick-cock clips (flickprod.py): every frame, first person and the outside view, per hand.
usage: flickrender.py render <body> [res WxH]      frames under <OUT>/flick/<body>/frames/<stem>/
       flickrender.py video <body>                 30 fps mp4 per hand and view, plus a left/right side by side
Take the render lock first (mkdir C:/Modding/gg-work/renderlock)."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import tube1, tubeprod, flickprod, flick2
import rrender
from rrender import SCENE, CAM, OUTCAM


FP = flickprod


def render(body, res=(960, 540)):
    tubeprod.use_gun('carnage'); cfgs = []
    for side in ('right', 'left'):
        base = f'{FP.OUT}/{body}/{FP.stem(side)}'; spec = json.load(open(base + '.json')); d = f'{os.path.dirname(base)}/frames/{os.path.basename(base)}'; os.makedirs(d, exist_ok=True)
        s = spec['_side'].lower(); o = 'left' if s == 'right' else 'right'
        for view, cam in (('fpp', CAM), ('out', OUTCAM)):
            cfg = {'clip_glb': spec['out'], 'clip': spec['clip'], 'frames': list(range(spec['frames'])), 'out': f'{d}/{view}', 'body': body, 'view': view, 'res': list(res),
                   'right_gun': 'carnage', 'left_gun': 'carnage', 'right_parts': common.gun('carnage').get('parts'), 'left_parts': common.gun('carnage').get('parts'),
                   f'{s}_mag_clip': spec['_gun_clip'], f'{o}_mag_clip': None, 'one_mag': True, 'mag_time': True, 'proxy': True, 'bg': [0.33, 0.36, 0.40],
                   f'{s}_parts_anim': True, f'{s}_mag_track': spec['_track'], f'{s}_parts_frames': spec['_part_frames']}
            tube1.GID = 'carnage'; cfg['objects'] = tube1.objects(spec); cfg['objects_side'] = spec['_side']; cfg.update(cam); cfgs.append(cfg)
    c = f'{renv.OUT}/work/render_flick_{body}.json'; json.dump(cfgs, open(c, 'w'))
    r = subprocess.run([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', c], capture_output=True, text=True, errors='replace')
    n = r.stdout.count('DONE ')
    if 'ALLDONE' not in r.stdout or n != len(cfgs): raise SystemExit(f'scene.py rendered {n} of {len(cfgs)}:\n' + '\n'.join((r.stdout + r.stderr).splitlines()[-15:]))
    print('rendered', n, 'views', flush=True)


def video(body):
    for side in ('right', 'left'):
        d = f'{FP.OUT}/{body}/frames/{FP.stem(side)}'
        for view in ('fpp', 'out'):
            rrender.ffmpeg(['-framerate', '30', '-i', f'{d}/{view}_%03d.png', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '14', f'{d}/../{FP.stem(side)}_{view}.mp4'])


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--v2' in a:
        a.remove('--v2'); flick2.__dict__.setdefault('stem', None)
        class FP2:
            OUT = flick2.OUT
            @staticmethod
            def stem(side): return f'carnage_{side}_FC02A_cycle'
        FP = FP2
    if a[0] == 'render': render(a[1], tuple(int(x) for x in a[2].split('x')) if len(a) > 2 else (960, 540))
    elif a[0] == 'video': video(a[1])
