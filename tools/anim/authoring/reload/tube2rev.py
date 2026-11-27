"""Review hooks for shellreview.py: TUBE round 2. Per pick three clips (right hand, male V): O = the round 1 pick as in
production (Carnage), C = the short version on the Carnage, T = the short version on the Tactician.
usage: python -B shellreview.py tube2rev frames|dense <id><take>|sheet|grid|page"""
import os, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import tube1, tube2

PROD_OLD = common.mp('C:/Modding/anim-work/smg-shotgun/production/clips')
PROD = os.environ.get('TUBE_R1_CLIPS') or PROD_OLD      # the round 1 pick clips: production/clips when this was made; now production/superseded/tube_r1/clips (ga drafts sets it)
CL = renv.OUT + '/clips/pma'
PICKS = {k: tube2.FUN[k] for k in tube2.FUN}
DOC = {k: ' '.join((fn.__doc__ or '').split()) for k, (n, fn) in PICKS.items()}
TAKES = ['O', 'C', 'T']
TAKE_NAME = {'O': 'round 1 pick as in production, Carnage', 'C': 'short, Carnage', 'T': 'short, Tactician'}
FILE = 'tube_round2'
TITLE = 'Tube Reloads, Short Openings'
SHEET_TITLE = 'TUBE round 2: the three picks with a visible opening short enough for the game\'s reload time (O round 1, C short Carnage, T short Tactician; right hand, male V).'


def stem(pick, take, side='right'):
    if take == 'O': return f'carnage_{side}_{tube2.SRC[pick]}A_empty_reload'
    return f"{'carnage' if take == 'C' else 'tactician'}_{side}_{pick}A_empty_reload"


def copy_originals():
    """The round 1 picks' specs and gates beside the round 2 clips (the glb, shells and track stay in production)."""
    for p in PICKS:
        st = stem(p, 'O')
        for ext in ('.json', '_gate.json'):
            b = open(f'{PROD}/pma/{st}{ext}', 'rb').read().replace(PROD_OLD.encode(), PROD.encode())      # the copies point at the files they were made from
            open(f'{CL}/{st}{ext}', 'wb').write(b)


def layout_of(spec):
    """Shared hidden window of the clip's pick and gun (all four hands and bodies), from the layout file."""
    lay = json.load(open((PROD if spec['_pick'] in tube2.SRC.values() else renv.OUT + '/clips') + '/layout_tube.json'))
    return lay[spec['_gun']][spec['_pick'] + 'A']['empty_reload']


def fit(spec):
    L = layout_of(spec); one, emp = tube2.LIMITS[spec['_gun']]; hs = L['hide_start']
    return hs, L['hide_end'], L['length'], {b: (tube2.rate(hs, one, m), tube2.rate(hs, emp, m)) for b, m in tube2.BODY.items()}


def fit_text(spec):
    hs, he, n, F = fit(spec); ok = lambda r: f"{r:.2f}" + ('' if r <= 1.15 else ' FB')
    return [f"shared hide start f{hs} (all hands, bodies), rise {n - 1 - he} f"] + [f"{b}: one shell {ok(a)}, empty {ok(e)}" for b, (a, e) in F.items()]


def objects(spec):
    J = json.load(open(spec['_objects'])); col = {'spent': (0.85, 0.75, 0.2, 1)}
    mesh = common.find('weapon_meshes', common.gun(spec['_gun'])['mesh'] + '__mag_std_01.glb')
    return [{'mesh': mesh, 'joints': {'mag_std': J['joints'][n]}, 'color': col.get(n, (1, 0.35, 0.1, 1))} for n in J['names']]


def key(s, g):
    first = next((f for f in range(s['frames']) if s['_pump_cm'][f] > 4), 8); L = g['layout']; mk = s['_marks']
    sp = g['shells'].get('spent_release') or first
    return [('pump opens', first), ('spent shell out', sp + 2), ('last frame before hidden', max((L['hide_start'] or 12) - 1, 0)), ('loading in view', mk.get('catch', mk.get('rack_start', 30)) - 1 if s['_pick'] != 'TU23' else (L['hide_end'] or 30) + 4),
            ('pump shut', g['pump']['home_frame'] or mk.get('hit', 40))]


def phase(s, g, f):
    L = g['layout']; mk = s['_marks']; pc = s['_pump_cm'][min(f, len(s['_pump_cm']) - 1)]
    if L['hide_start'] is not None and L['hide_start'] <= f <= L['hide_end']: return 'HIDDEN (fast-forward)'
    if abs(f - mk.get('hit', 999)) <= 2: return f'pump shut ({pc:.1f} cm)'
    if L['hide_start'] is not None and f < L['hide_start']: return f'opening ({pc:.1f} cm)'
    return 'rise'


def numbers(s, g):
    I = g['inertia']; m = g['motion']; L = g['layout']; sh = g['shells']; pm = g['pump']
    return ([f"peak {m['peak_speed']} cm/f, overshoot {I['max_overshoot_cm']} cm / {I['max_overshoot_deg']} deg",
             f"pump open f{pm['open_frame']}, home f{pm['home_frame']}; spent out f{sh.get('spent_release')}",
             (lambda q: f"pump gate: max {q['max_jump_cm_f']} cm/f, unexplained {q['unexplained_accel_cm']} cm, map {'monotone' if q['frame_map_monotone'] else 'NOT monotone'}" if q else 'pump gate: not run (round 1 clip)')(g.get('pump_motion')),
             (lambda q: (lambda t: f"stroke open f{t['open'][0]}-{t['open'][1]} (yank moving f{t['yank_moving'][0]}-{t['yank_moving'][1]}), close f{t['close'][0]}-{t['close'][1]} (rise f{t['rise'][0]}-{t['rise'][1]}, gun at rest f{t['gun_at_rest_from']}), at rest {t['travel_at_rest_cm']} cm")(q['stroke']) if q and 'stroke' in q else 'stroke: not measured')(g.get('pump_motion')),
             f"this clip hidden f{L['hide_start']}-{L['hide_end']}, eye {g['eye_cm'][0]} cm"] + fit_text(s) +
            ['gate: ' + ('pass' if not g['fails'] else '; '.join(g['fails']))])


def shell_cell(s, g):
    sh = g['shells']; t = f"spent f{sh.get('spent_release')}->f{sh.get('spent_land')}"
    if 'saddle' in sh: t += f", saddle shell {sh['saddle']['exit_cm_f']}/{sh['saddle']['gun_cm_f']} cm/f, caught {sh['saddle']['catch_error_cm']} cm off"
    if 'toss_speed_cm_f' in sh: t += ', tossed ' + '/'.join(str(x) for x in sh['toss_speed_cm_f']) + ' cm/f'
    return t + '; fit ' + ', '.join(fit_text(s)[1:])


INTRO = ''


def intro():
    rows = ''.join(f"<tr><td>{g}</td><td>{l}</td><td>{T} s</td>" + ''.join(f"<td>{int(1.15 * 0.75 * T * 30 / m + 1e-9)}</td>" for m in tube2.BODY.values()) + '</tr>'
                   for g, (a, b) in (('Carnage', tube2.LIMITS['carnage']), ('Tactician', tube2.LIMITS['tactician'])) for l, T in (('one shell', a), ('empty', b)))
    return ('<p>The owner\'s three TUBE picks rarely played in game: their visible opening (first frame to the shared hide start) was longer '
            'than the game\'s reload time allows, so the script played the quick-drop fallback. Rule (<code>GorillaAkimbo.reds</code>, OnEnter): '
            'the pick falls back when hide start / 30 / (0.75 x reload time) is above <b>1.15</b>; Body speeds the reload up by 3 % per point. '
            'The rise after the hidden window plays at speed 1.</p>'
            '<table><tr><th>gun</th><th>reload</th><th>time</th><th>max hide start, base</th><th>Body 10</th><th>Body 20</th></tr>' + rows + '</table>'
            '<p>Each pick is shown as in round 1 (O), then shortened on the Carnage (C) and the Tactician (T). The ratio per clip is listed under it; '
            '<b>FB</b> = the fallback would play. Shortened: the gun is yanked back along the barrel and stopped dead (the loose fore-end runs on '
            'back to its stop, the spent shell is kicked out in view), then dives out of view; the tube is filled out of view; the pick\'s own way '
            'of loading moves onto the rise, in view. Right hand, male V shown; all four hands and bodies built and gated, the hide start is the '
            'latest of the four.</p>')
INTRO = intro()
