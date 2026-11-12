"""End-pose fix of every top-magazine arm clip the build ships, male and female, into a new clips folder, with the
verify line of each and a summary.

usage: batch.py [--src <dir>] [--dst <dir>] [--bodies pma,pwa] [--only <text in the clip name>] [--force]
  --src   clips before the fix, <body>/<clip>.glb (default: paths.clips_pre_endpose)
  --dst   default: <authoring work>/endpose/clips. Existing files are kept unless --force.
The clip list is the build's (topmagsets.plan): clips of enabled top-magazine guns. Clips of other guns in --src are
copied as they are with --copy-rest. The log goes to <dst>/batch_log.txt.
"""
import concurrent.futures, os, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import common
import fix_endpose, verify


def shipped(clips):
    """{body: [clip file names]} the build takes from a clips folder."""
    from topmagsets import plan
    out = {}
    for body, _, files, _ in plan(clips):
        for p, _ in files:
            if os.path.basename(p) not in out.setdefault(body, []):
                out[body].append(os.path.basename(p))
    return out


def one(a):
    src, dst, body, name, force = a
    idle = common.need(common.idle_glb(body))
    f0, f1 = fix_endpose.window(name)
    if force or not os.path.exists(f'{dst}/{body}/{name}'):
        fix_endpose.fix(f'{src}/{body}/{name}', idle, f'{dst}/{body}/{name}', f0, f1)
    return f'{body}/{name} ' + '|'.join(verify.report(f'{dst}/{body}/{name}', f'{src}/{body}/{name}', idle, f0))


if __name__ == '__main__':
    argv = sys.argv[1:]
    src = common.opt(argv, '--src') or common.path('clips_pre_endpose')
    dst = common.opt(argv, '--dst') or common.work('endpose', 'clips')
    only = common.opt(argv, '--only')
    bodies = common.body_list(common.opt(argv, '--bodies'))
    jobs = []
    for body, names in shipped(src).items():
        if body not in bodies: continue
        os.makedirs(f'{dst}/{body}', exist_ok=True)
        jobs += [(src, dst, body, n, '--force' in argv) for n in sorted(names) if not only or only in n]
        if '--copy-rest' in argv:
            for n in os.listdir(f'{src}/{body}'):
                if n.endswith('.glb') and n not in names and not os.path.exists(f'{dst}/{body}/{n}'):
                    shutil.copyfile(f'{src}/{body}/{n}', f'{dst}/{body}/{n}')
    with concurrent.futures.ProcessPoolExecutor(int(os.environ.get('JOBS', '4'))) as ex:
        lines = list(ex.map(one, jobs))
    open(dst + '/batch_log.txt', 'a', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print(len(lines), 'clips ->', dst)
