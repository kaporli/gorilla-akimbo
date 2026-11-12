"""Archive overlap check: which .archive files under the given folders contain a game file the mod builds on or
overrides (another mod replacing one of them changes or breaks the animations).

usage: hashscan.py <folder> [<folder> ...] [--paths <depot path>,<depot path>]
  default paths: the game files of weapons.json (player entities, reload source sets, lowered base sets, magazine
  entity, the magazine gun's vanilla sets) and the dual-wield graph files named below.
An archive lists its files by the FNV1a64 hash of the lower-case depot path; a match is that hash found in the file.
Prints <archive> | <depot path> per match. Exit code 1 when something matched.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common

manifest = common.manifest
EXTRA = ['base/gameplay/anim_graphs/player_base.animgraph', 'base/gameplay/anim_graphs/player_dualwield.animgraph',
         'base/animations/weapon/firearms/dual_wield/pma_w_default_weapon_dual_wield.anims',
         'base/animations/weapon/firearms/dual_wield/pwa_w_default_weapon_dual_wield.anims',
         'base/gameplay/gui/widgets/ammo_counter/ammo_counter.inkwidget']


def fnv(s):
    h = 0xcbf29ce484222325
    for b in s.lower().encode():
        h ^= b; h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return struct.pack('<Q', h)


def default_paths():
    gf = manifest.load()['game_files']
    out = [e for body in manifest.bodies() for e in gf['bodies'][body]] + [gf['magazine_entity']]
    out += [p for p, _ in manifest.needed_game_files() if p.endswith('.anims') and 'dual_wield' in p or '__mag_' in p]
    return [p.replace(chr(92), '/') for p in out] + EXTRA


def scan(folders, paths):
    hs = {fnv(manifest.depot(p)): p for p in paths}
    hits = []
    for d in folders:
        for root, _, fs in os.walk(d):
            for f in fs:
                if f.endswith('.archive'):
                    data = open(os.path.join(root, f), 'rb').read()
                    hits += [(os.path.join(root, f), p) for h, p in hs.items() if h in data]
    return hits


if __name__ == '__main__':
    argv = sys.argv[1:]
    paths = common.opt(argv, '--paths')
    hits = scan(argv, paths.split(',') if paths else default_paths())
    for a, p in hits:
        print(a, '|', p)
    print(len(hits), 'matches')
    sys.exit(1 if hits else 0)
