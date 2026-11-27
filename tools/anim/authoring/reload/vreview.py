"""Game-camera review of the vanilla-reference drafts in the lowered stance: one MP4 per draft, a contact sheet (key frames, one row per draft) and a grid MP4 (all drafts side by side).

usage: vreview.py <clips dir (<body>/warden_right_<id>B_empty_reload.json)> <out dir> [--ids SV03,SV04] [--fps 15]
The drafts are the lowered builds (smgprod --lowered): they start and end in the lowered idle and play as the graph plays them (rrender3.stance_frames, game camera, fov from checks.draft.r9).
Frames are 640x360; the MP4s run at --fps (default 15, half speed) with the frame number and phase burned in. One Blender at a time.
"""
import os, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import rrender3 as RR
from PIL import Image, ImageDraw, ImageFont

W, H = 640, 360


def low_glb(body, gun='warden'):
    return f"{common.path('low_clips')}/{body}/lowered_{common.gun(gun)['lowered']['pose']}.glb"


def render(clips, out, rid, body='pma'):
    sp = f'{clips}/{body}/warden_right_{rid}B_empty_reload.json'; N = json.load(open(sp))['frames']
    return RR.stance_frames(sp, 'lowered', low_glb(body), list(range(N)), f'{out}/frames/{rid}', res=(W, H)), json.load(open(sp)), json.load(open(sp[:-5] + '_gate.json'))


def phase(spec, gate, f):
    return RR.phase(spec, gate, f)


def main(argv):
    o = lambda n, d=None: (argv.pop(argv.index(n) + 1), argv.remove(n))[0] if n in argv else d
    ids = (o('--ids') or '').split(',') if '--ids' in argv else None; fps = int(o('--fps', 15)) if '--fps' in argv else 15
    clips, out = argv[0], argv[1]; os.makedirs(out, exist_ok=True)
    if ids is None: ids = sorted({f.split('_')[2][:-1] for f in os.listdir(f'{clips}/pma') if f.endswith('_empty_reload.json') and '_SV' in f and 'gate' not in f and 'draft' not in f and 'track' not in f})
    ff = common.path('ffmpeg'); fnt = ImageFont.truetype('arialbd.ttf', 18); small = ImageFont.truetype('arialbd.ttf', 14)
    data = {}
    for rid in ids:
        frames, spec, gate = render(clips, out, rid); N = spec['frames']; data[rid] = (frames, spec, gate); d = f'{out}/frames/{rid}/cap'; os.makedirs(d, exist_ok=True)
        for f in range(N):
            im = Image.open(frames[f]).convert('RGB'); dr = ImageDraw.Draw(im); dr.rectangle((0, 0, W, 26), fill=(0, 0, 0))
            dr.text((8, 4), f'{rid} {spec.get("_name", "")}  f{f}/{N - 1}  {phase(spec, gate, f)}', fill=(255, 220, 0), font=small); im.save(f'{d}/{f:03d}.png')
        mp4 = f'{out}/{rid}_lowered.mp4'
        subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', f'{d}/%03d.png', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', mp4], check=True); print(mp4, flush=True)
    # contact sheet: release, magazine out of view (hidden start), hidden end, seat, hit, last
    w, h = 320, 180; cols = ['release', 'hide start', 'hide end', 'seat', 'hit', 'end']
    sheet = Image.new('RGB', (w * len(cols), (h + 20) * len(ids) + 34), (18, 18, 22)); dr = ImageDraw.Draw(sheet)
    dr.text((8, 8), 'Warden empty_reload drafts from vanilla reloads, lowered stance, game camera. Columns: ' + ', '.join(cols), fill=(255, 220, 0), font=fnt)
    for r, rid in enumerate(ids):
        frames, spec, gate = data[rid]; L = gate['layout']; N = spec['frames']
        fs = [L['mag_out'], L['hide_start'] or L['mag_out'] + 4, L['hide_end'] or L['seated'], L['seated'], L['handle'] or L['seated'] + 14, N - 1]
        for c, f in enumerate(fs):
            f = min(f, N - 1); y = 34 + r * (h + 20); sheet.paste(Image.open(frames[f]).convert('RGB').resize((w, h)), (c * w, y + 20)); dr.text((c * w + 4, y + 2), f'{rid} {cols[c]} f{f}', fill=(255, 255, 255), font=small)
    sheet.save(f'{out}/contact_sheet.png'); print(f'{out}/contact_sheet.png', sheet.size, flush=True)
    # grid MP4: every draft at 320x180, 3 columns, same frame number
    n = len(ids); cc = 3; rr = (n + cc - 1) // cc; N = max(data[i][1]['frames'] for i in ids); gd = f'{out}/frames/grid'; os.makedirs(gd, exist_ok=True)
    for f in range(N):
        g = Image.new('RGB', (w * cc, (h + 16) * rr), (18, 18, 22)); d_ = ImageDraw.Draw(g)
        for k, rid in enumerate(ids):
            fr = data[rid][0]; ff_ = min(f, len(fr) - 1); x, y = (k % cc) * w, (k // cc) * (h + 16)
            g.paste(Image.open(fr[ff_]).convert('RGB').resize((w, h)), (x, y + 16)); d_.text((x + 4, y + 1), f'{rid} f{ff_}', fill=(255, 220, 0), font=small)
        g.save(f'{gd}/{f:03d}.png')
    mp4 = f'{out}/grid_lowered.mp4'
    subprocess.run([ff, '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', f'{gd}/%03d.png', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', mp4], check=True); print(mp4, flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
