"""Prints the widget tree of an .inkwidget JSON (WolvenKit). usage: inktree.py <json> [name filter]"""
import json, sys

d = json.load(open(sys.argv[1], encoding='utf-8'))
filt = sys.argv[2] if len(sys.argv) > 2 else None
H = {}


def idx(o):
    if isinstance(o, dict):
        if 'HandleId' in o and 'Data' in o:
            H[o['HandleId']] = o['Data']
        for v in o.values():
            idx(v)
    elif isinstance(o, list):
        for v in o:
            idx(v)


idx(d)


def deref(h):
    if not isinstance(h, dict):
        return None
    return h.get('Data') or H.get(h.get('HandleRefId'))


def nm(w):
    n = w.get('name', {})
    return n.get('$value') if isinstance(n, dict) else n


def line(w, depth):
    lay = w.get('layout', {}) or {}
    m = lay.get('margin', {}) or {}
    s = w.get('size', {}) or {}
    extra = ''
    if 'childMargin' in w:
        extra += ' childMargin=' + str([w['childMargin'].get(k) for k in ('left', 'top', 'right', 'bottom')])
    for k in ('fitToContent', 'clipping', 'affectsLayoutWhenHidden', 'childOrder'):
        if k in w:
            extra += f' {k}={w[k]}'
    return ('  ' * depth + f"{nm(w)} [{w.get('$type')}] size={s.get('X')}x{s.get('Y')} anchor={lay.get('anchor')} "
            f"rule={lay.get('sizeRule')} h={lay.get('HAlign')} v={lay.get('VAlign')} "
            f"margin={[m.get(k) for k in ('left', 'top', 'right', 'bottom')]}{extra}")


def show(w, depth, path):
    if w is None or depth > 20:
        return
    p = path + [str(nm(w))]
    if not filt or any(filt in x for x in p):
        print(line(w, depth))
    ch = deref(w.get('children'))
    for c in (ch or {}).get('children', []) if ch else []:
        show(deref(c), depth + 1, p)


lib = d['Data']['RootChunk']
for item in lib.get('libraryItems', []):
    print('== item', item.get('name', {}).get('$value'))
    pkg = item.get('package', {})
    root = None
    # WolvenKit embeds the item's widget tree under package -> Data -> file -> RootChunk -> root
    def find_root(o):
        if isinstance(o, dict):
            if o.get('$type') == 'inkWidgetLibraryItemInstance' or 'rootWidget' in o:
                return deref(o.get('rootWidget'))
            for v in o.values():
                r = find_root(v)
                if r is not None:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = find_root(v)
                if r is not None:
                    return r
        return None
    root = find_root(item)
    show(root, 0, [])
