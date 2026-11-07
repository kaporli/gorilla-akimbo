"""Fallback for the Shingen magazine sets when ArchiveXL's weapon_root.ent / component: Magazine entries do not apply:
adds the six dual-wield magazine sets (magtrack.py) to the "Magazine" component of every appearance of
w_smg__arasaka_shingen.app (components and compiledData), priority 100, keyed on the gorillaakimbo_mag_* wrappers.
Shipping the edited .app overrides the vanilla file: another mod that edits it conflicts.

usage: magapp.py <app.json (WolvenKit convert s)> <out app.json>
"""
import json, sys, copy

FAMILIES = [(f, s) for f in ('long', 'smg', 'pair') for s in ('left', 'right')]


def entry(family, side):
    return {'$type': 'animAnimSetupEntry',
            'animSet': {'DepotPath': {'$type': 'ResourcePath', '$storage': 'string',
                                      '$value': f'gorillaakimbo\\animations\\w_smg__arasaka_shingen__mag_{family}_{side}.anims'},
                        'Flags': 'Default'},
            'priority': 100,
            'variableNames': [{'$type': 'CName', '$storage': 'string', '$value': f'gorillaakimbo_mag_{family}_{side}'}]}


def patch(comp):
    g = comp['animations']['gameplay']
    have = {e['animSet']['DepotPath']['$value'] for e in g}
    n = 0
    for f, s in FAMILIES:
        e = entry(f, s)
        if e['animSet']['DepotPath']['$value'] not in have:
            g.append(e); n += 1
    return n


def main(src, dst):
    j = json.load(open(src, encoding='utf-8'))
    total = 0
    for a in j['Data']['RootChunk']['appearances']:
        d = a['Data']
        lists = [d.get('components') or []]
        cd = d.get('compiledData', {}).get('Data')
        if cd: lists.append(cd.get('Chunks') or [])
        for comps in lists:
            for c in comps:
                if c.get('$type') == 'entAnimatedComponent' and c.get('name', {}).get('$value') == 'Magazine':
                    total += patch(c)
    json.dump(j, open(dst, 'w', encoding='utf-8'), indent=2)
    print('entries added', total)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
