"""Lists the sound events of the reload clips in anim set JSONs. usage: sounds.py <anims.json>..."""
import json, sys

RELOAD = ('reload', 'empty_reload', 'reload_start', 'reload_loop', 'reload_end', 'reload_01', 'empty_reload_01')

for path in sys.argv[1:]:
    d = json.load(open(path, encoding='utf-8'))
    print('==', path.replace('\\', '/').split('/')[-1])
    for e in d['Data']['RootChunk']['animations']:
        a = e['Data']['animation']['Data']
        name = a['name']['$value']
        if name not in RELOAD:
            continue
        evs = (e['Data'].get('events') or {}).get('Data') or {}
        out = []
        for x in evs.get('events', []):
            x = x['Data']
            if x.get('$type') == 'animAnimEvent_Sound' or 'Sound' in x.get('$type', ''):
                out.append((x.get('startFrame'), x['eventName']['$value']))
        out.sort()
        print('  %-16s %.2fs %d frames: %s' % (name, a.get('duration', 0), a['animBuffer']['Data'].get('numFrames', 0),
                                                ', '.join(f'{f}:{n}' for f, n in out)))
