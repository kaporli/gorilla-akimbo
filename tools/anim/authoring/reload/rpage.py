"""Review page of a draft category, in the style of the earlier scored review pages.

usage: rpage.py <category> [--recheck]
Reads <OUT>/<category>/<id>/<id>.json and _checks.json and <OUT>/scores.json; copies each draft's mp4 and strip into
<OUT>/<category>/review/ and writes <category>-reloads.html there. --recheck runs the checks again first.
Also writes <OUT>/<category>/checks_table.txt (every draft's numbers, one line each).
"""
import os, sys, json, shutil, importlib, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common
import make, rchecks

STYLE_FROM = 'C:/Modding/anim-work/long-partner/review/long-topmag.html'
TITLES = {'front': ('Front Magazine Rifle Reloads', 'Copperhead (stands for Umbra and Sidewinder; Ajax and Kyubi with their own timing)'),
          'masamune': ('Masamune Reloads', 'Masamune'), 'hercules': ('Hercules Reloads', 'Hercules 3AX')}


def v(c, k):
    x = c.get(k)
    return x[0] if isinstance(x, list) else x


def main(cat, recheck=False):
    mod, gun = make.CATS[cat]; M = importlib.import_module(mod); out = f'{renv.OUT}/{cat}'; rev = out + '/review'; os.makedirs(rev, exist_ok=True)
    SC = json.load(open(renv.OUT + '/scores.json')); W = SC['weights']; rows = []; lines = []
    for did, (name, fn) in M.DRAFTS.items():
        sp = f'{out}/{did}/{did}.json'; spec = json.load(open(sp))
        if recheck:
            c = rchecks.check(spec); c['name'] = name; json.dump(c, open(f'{out}/{did}/{did}_checks.json', 'w'), indent=1)
        c = json.load(open(f'{out}/{did}/{did}_checks.json')); lines.append(make.summary(c))
        for ext in ('.mp4', '_strip.png'):
            if os.path.exists(f'{out}/{did}/{did}{ext}'): shutil.copyfile(f'{out}/{did}/{did}{ext}', f'{rev}/{did}{ext}')
        s = SC[cat][did]; hid = c['hidden']
        rows.append({'id': did, 'name': name, 's': s['s'], 'concept': spec['_doc'], 'good': s['good'], 'bad': s['bad'], 'two': c['two_arm'],
                     'm': [f"{v(c, 'eye_cm')} cm", f"{v(c, 'cover_peak')}%", f"f{hid[0]}-{hid[1]}" if hid else 'never', f"{v(c, 'wrist_swing'):.0f} deg", f"{v(c, 'reach'):.2f}",
                           f"{v(c, 'hands_gap_cm'):.0f} cm", f"{v(c, 'guns_gap_cm'):.0f} cm", f"{c['end_cm']:.3f} cm"],
                     'fails': c['fails'], 'notes': spec.get('_notes', '')})
    open(out + '/checks_table.txt', 'w').write('\n'.join(lines) + '\n')
    tot = lambda r: sum(a * b for a, b in zip(r['s'], W))
    top = sorted(rows, key=lambda r: -tot(r))[:3]
    T = json.load(open(f'{out}/{list(M.DRAFTS)[0]}/{list(M.DRAFTS)[0]}.json'))['_timing']
    css = open(STYLE_FROM, encoding='utf-8').read(); css = css[css.index('<style>'):css.index('</style>') + 8].replace('aspect-ratio: 32 / 9', 'aspect-ratio: 32 / 9')
    title, rep = TITLES[cat]; h = T.get('handle')
    timing = (f"The gun's own reload ({T['clip'].replace('_', ' ')}, {T['frames']} frames at 30 fps): magazine leaves at frame {T['out']}, clear of the well at {T['clear']}, "
              f"new one near at {T['near']}, seated at {T['seated']}" + (f", handle or bolt at {h[0]} to {h[1]}" if h else ', no handle') + '.')
    page = f'''<title>{title}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
{css}
<div class="wrap">
  <section class="intro">
    <h1>{title}</h1>
    <p>Ten one-handed reload drafts for the right hand, male V, on the {html.escape(rep)}, each starting and ending in the gun's raised idle pose (hip carry). The other hand holds its own rifle. Up to three can ship per set (the game picks one at random).</p>
    <p class="muted">{timing} Each video shows first person on the left (camera fitted to the game, 105 degrees) and an outside view on the right; grey blocks stand for torso, belt and thighs. The <span class="tag">orange block</span> is the magazine, driven by the game's own animation: when it leaves the gun it goes where the game's missing left hand would carry it, so it has to be out of view then. Blender previews only, nothing tested in game. The moving handle or bolt is not drawn.</p>
    <p><b>My top three:</b> {', '.join(f'<a href="#{r["id"]}">{r["id"]} {html.escape(r["name"])}</a> ({tot(r):.2f})' for r in top)}.</p>
  </section>
  <section class="intro">
    <h2>Scores</h2>
    <div class="legend muted">
      <span><b>Fit</b> (30%): the motion gives the gun's own animation a reason (magazine out, new magazine, handle or bolt). <b>Clarity</b> (25%): reads in first person, time in view, nothing in the face. <b>Plausible</b> (20%): wrists, reach, body, checks. <b>Style</b> (15%). <b>Cost</b> (10%): production effort and risk; two-arm clips block the other gun and need the top-magazine machinery.</span>
      <span><b>Eye</b>: closest the rifle gets to the eye (rule 20 cm). <b>Cover</b>: peak share of the screen it covers (rule 18%). <b>Hidden</b>: frames it is fully out of view. <b>Wrist</b>: largest bend against the idle (rule 113). <b>Reach</b>: shoulder to wrist over arm length (rule 0.985). <b>Hands</b>, <b>Guns</b>: smallest gap between the wrists and between the two rifles. <b>End</b>: last frame against the raised idle (rule 0.01 cm). Every draft: the detached magazine is never on screen, the new one goes in out of view.</span>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th>#</th><th>Draft</th><th class="num">Fit</th><th class="num">Clarity</th><th class="num">Plausible</th><th class="num">Style</th><th class="num">Cost</th><th class="num">Score</th><th class="num">Eye</th><th class="num">Cover</th><th class="num">Hidden</th><th class="num">Wrist</th><th class="num">Reach</th><th class="num">Hands</th><th class="num">Guns</th><th class="num">End</th><th>Check failures</th></tr></thead>
      <tbody id="tbody"></tbody></table></div>
  </section>
  <section id="list"></section>
</div>
<script>
const V = {json.dumps(rows)};
const W = {json.dumps(W)};
const total = s => s.reduce((a, x, i) => a + x * W[i], 0);
V.forEach(v => v.t = total(v.s));
V.sort((a, b) => b.t - a.t || b.s[0] - a.s[0]);
const cls = t => t >= 7 ? "s-good" : t >= 6 ? "s-mid" : "s-low";
function player(id) {{
  return `<div class="player">
    <video src="${{id}}.mp4" controls loop muted playsinline preload="metadata"></video>
    <div class="speed" role="group" aria-label="Playback speed for ${{id}}">Speed
      ${{[1, 0.5, 0.25].map(r => `<button type="button" data-r="${{r}}" aria-pressed="${{r === 1}}">${{r}}x</button>`).join("")}}
    </div>
    <details><summary>Key frames</summary><img class="strip" src="${{id}}_strip.png" alt="Labelled first-person key frames of ${{id}}" loading="lazy"></details></div>`;
}}
function wire(el) {{
  el.querySelectorAll(".player").forEach(p => {{
    const vid = p.querySelector("video");
    p.querySelectorAll(".speed button").forEach(b => b.addEventListener("click", () => {{
      vid.playbackRate = parseFloat(b.dataset.r);
      p.querySelectorAll(".speed button").forEach(o => o.setAttribute("aria-pressed", String(o === b)));
      vid.play().catch(() => {{}});
    }}));
  }});
}}
const tb = document.getElementById("tbody");
V.forEach((v, i) => {{
  const tr = document.createElement("tr");
  tr.innerHTML = `<td class="mono">${{i + 1}}</td><td><a href="#${{v.id}}">${{v.id}} ${{v.name}}</a></td>` +
    v.s.map(x => `<td class="num">${{x}}</td>`).join("") + `<td class="num total ${{cls(v.t)}}">${{v.t.toFixed(2)}}</td>` +
    v.m.map(x => `<td class="num">${{x}}</td>`).join("") + `<td>${{v.fails.length ? v.fails.join("; ") : "none"}}</td>`;
  tb.appendChild(tr);
}});
const labels = {json.dumps(SC['labels'])};
const list = document.getElementById("list");
V.forEach((v, i) => {{
  const el = document.createElement("article"); el.className = "variant"; el.id = v.id;
  el.innerHTML = `
    <div class="head"><span class="rank">#${{i + 1}} - ${{v.id}}</span><h2>${{v.name}}</h2><span class="score ${{cls(v.t)}}">${{v.t.toFixed(2)}} / 10</span>${{v.two ? '<span class="tag">two-arm clip</span>' : ''}}</div>
    <div class="row">
      ${{player(v.id)}}
      <div class="notes">
        <p>${{v.concept}}</p>
        <div class="bars">${{v.s.map((x, k) => `<span>${{labels[k]}}</span><span class="bar"><i style="width:${{x * 10}}%"></i></span><span class="mono">${{x}}</span>`).join("")}}</div>
        <ul>${{v.good.map(g => `<li>${{g}}</li>`).join("")}}</ul>
        <ul class="muted">${{v.bad.map(b => `<li>${{b}}</li>`).join("")}}</ul>
        <p class="mono muted">eye ${{v.m[0]}}, cover ${{v.m[1]}}, hidden ${{v.m[2]}}, wrist ${{v.m[3]}}, reach ${{v.m[4]}}, hands ${{v.m[5]}}, guns ${{v.m[6]}}, end ${{v.m[7]}}${{v.fails.length ? "; FAILS: " + v.fails.join("; ") : ""}}</p>
      </div>
    </div>`;
  list.appendChild(el); wire(el);
}});
</script>
'''
    p = f'{rev}/{cat}-reloads.html'; open(p, 'w', encoding='utf-8').write(page); print('wrote', p)
    print('top three:', [(r['id'], r['name'], round(tot(r), 2)) for r in top])
    for r in sorted(rows, key=lambda r: -tot(r)): print(f"  {r['id']} {r['name']}: {tot(r):.2f}  fails {r['fails']}")


if __name__ == '__main__':
    argv = sys.argv[1:]; main(argv[0], '--recheck' in argv)
