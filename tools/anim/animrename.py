"""Renames every animation in an anim set JSON (WolvenKit `convert s`) except the kept ones, so a set added at a
higher priority only overrides those clips. The other clips stay in the file (their data chunks are shared by
index) under names nothing asks for.

usage: animrename.py <anims.json> <keep name> [<keep name> ...]
"""
import sys, json

path, keep = sys.argv[1], set(sys.argv[2:])
j = json.load(open(path, encoding='utf-8'))
found, renamed = [], 0
for entry in j['Data']['RootChunk']['animations']:
    anim = entry['Data']['animation']['Data']
    name = anim['name']['$value']
    if name in keep:
        found.append(name)
    else:
        anim['name']['$value'] = 'gorillaakimbo_unused_' + name
        renamed += 1
missing = keep - set(found)
if missing:
    raise SystemExit(f'not in the set: {sorted(missing)}')
json.dump(j, open(path, 'w', encoding='utf-8'), indent=1)
print(f'kept {sorted(found)}, renamed {renamed}')
