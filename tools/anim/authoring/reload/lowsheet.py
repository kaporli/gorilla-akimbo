"""Game-camera sheet of a gun's lowered-stance reload variants: one PNG. Rows: per pick the shipped clip played in the lowered stance (blended in from the
lowered idle, as the game does) and the variant; columns: 8 frames (start, rise, release, discard, insert, end). First-person camera of the game (checks.draft.r9),
right gun reloading, left gun lowered, empty_reload. Needs Blender (background, paths.blender) and Pillow; no game, no WolvenKit.

usage: lowsheet.py <gun> <variant clips dir> <out png> [--body pma] [--stance lowered|raised] [--shipped <clips dir>] [--work <dir>]
(raised: the shipped clip and the variant played as they are, no blend from the lowered idle)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import rrender3 as RR
from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
gid, var, out = a[0], a[1].rstrip('/'), a[2]; body = common.opt(a, '--body') or 'pma'; stance = common.opt(a, '--stance') or 'lowered'
g = common.gun(gid); r = g['reload']; take = 'A' if r['weight'] == 'light' else 'B'
ship = (common.opt(a, '--shipped') or common.path(r.get('clips', 'rreload_clips'))).rstrip('/')
work = common.opt(a, '--work') or os.path.splitext(out)[0] + '_frames'
low = f"{common.path('low_clips')}/{body}/lowered_{g['lowered']['pose']}.glb"
W, H = 320, 180; fs = ImageFont.truetype('arialbd.ttf', 14); COLS = 8
picks = [p + take for p in r['slots']]; rows = []
for pk in picks:
    import rreload; nm = os.path.basename(rreload.clip_file(var, body, gid, 'right', pk[:-1], take, 'empty_reload'))[:-4]; sp_s = f'{ship}/{body}/{nm}.json'; sp_v = f'{var}/{body}/{nm}.json'
    if not os.path.exists(sp_v): continue      # a pick the discard layer could not make (blocked)
    rel = json.load(open(sp_v[:-5] + '_track.json'))['release']; N = json.load(open(sp_v))['frames']
    fr = sorted(set([0, max(0, rel - 11), rel - 7, rel - 2, rel + 2, rel + 8, N - 34, N - 1]))
    for kind, sp in (('shipped', sp_s), ('variant', sp_v)):
        ims = RR.stance_frames(sp, stance, low, fr, f'{work}/{pk}_{kind}', res=(W, H)); rows.append((pk, kind, fr, ims))
sheet = Image.new('RGB', (W * COLS, (H + 20) * len(rows) + 30), (18, 18, 22)); dr = ImageDraw.Draw(sheet)
dr.text((8, 6), f'{g["name"]} empty_reload, right gun, {stance} stance, game camera ({body}). Rows: shipped clip, variant, per pick.', fill=(255, 220, 0), font=fs)
for i, (pk, kind, fr, ims) in enumerate(rows):
    y = 30 + i * (H + 20)
    for c, k in enumerate(fr):
        sheet.paste(Image.open(ims[k]).convert('RGB').resize((W, H)), (c * W, y + 20)); dr.text((c * W + 4, y + 2), f'{pk} {kind} f{k}', fill=(255, 255, 255), font=fs)
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True); sheet.save(out); print(out, sheet.size)
