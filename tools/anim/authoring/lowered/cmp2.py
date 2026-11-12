"""Side-by-side render of friendly_idlepose frame 0 of several clip glbs (first person over outside view).

usage: cmp2.py <out prefix> <right gun> <left gun> <body> <label>=<clip glb> ...
  guns: manifest id. Writes <out prefix>.png.
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
from PIL import Image, ImageDraw, ImageFont

SCENE = os.path.join(common.HERE, 'author', 'scene.py')
out, rg, lg, body = sys.argv[1:5]; items = [a.split('=', 1) for a in sys.argv[5:]]
procs = []
for k, (lab, glb) in enumerate(items):
    for v in ('fpp', 'out'):
        j = {"clip_glb": glb, "clip": "friendly_idlepose", "left_gun": common.gun(lg)['id'], "right_gun": common.gun(rg)['id'], "body": body,
             "left_mag_clip": None, "frames": [0], "out": f"{out}_{k}_{v}", "view": v, "fov": 68, "pitch": 0, "eye": [0, 1.605, 0],
             "res": [512, 384], "cam_loc": [-1.1, 1.6, 1.95], "cam_tgt": [0, 0.25, 1.4]}
        json.dump(j, open(f"{out}_{k}_{v}.json", 'w'))
        procs.append(subprocess.Popen([common.need(common.path('blender')), '-b', '--factory-startup', '--python', SCENE, '--', f"{out}_{k}_{v}.json"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
for p in procs: p.wait()
f = ImageFont.truetype('arialbd.ttf', 18); o = Image.new('RGB', (512 * len(items), 768))
for k, (lab, glb) in enumerate(items):
    for r, v in enumerate(('fpp', 'out')):
        im = Image.open(f"{out}_{k}_{v}_000.png").convert('RGB'); ImageDraw.Draw(im).text((8, 6), lab, fill=(255, 220, 0), font=f); o.paste(im, (512 * k, 384 * r))
o.save(out + '.png'); print(out + '.png')
