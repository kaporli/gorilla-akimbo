"""Calibrates the mass-derived arm spring (gunmass.arm_spring) against the take labels (r3lib.SPRING) on the guns whose shipped clips use the r3lib spring.
One stiffness per axis (k_pos, k_rot) is the geometric mean over the guns of w^2 * M (M = m_gun + m_arm, I_arm + I_gun); prints the fit table.
usage: springfit.py [--tol 0.05]"""
import os, sys, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renv, common, gunmass
import r3lib

GUNS = {'pulsar': 'A', 'warden': 'B'}     # smgprod.FAMILIES with engine r3lib (bull3, top3)
FPS = 30.0


def table(tol=0.05):
    rows = []
    for g, take in GUNS.items():
        t = gunmass.spring_terms(g); L = r3lib.SPRING[take]; M = t['m_gun'] + t['m_arm']; J = t['I_arm'] + t['I_gun']
        rows.append(dict(gun=g, take=take, t=t, M=M, J=J, wp=L['wp'], wr=L['wr'], z=L['z']))
    kp = math.exp(sum(math.log((r['wp'] * FPS) ** 2 * r['M']) for r in rows) / len(rows)); kr = math.exp(sum(math.log((r['wr'] * FPS) ** 2 * r['J']) for r in rows) / len(rows))
    cfg = {'source': 'label', 'k_pos_n_m': round(kp, 1), 'k_rot_nm_rad': round(kr, 2), 'zeta': sorted(set(r['z'] for r in rows))[0] if len({r['z'] for r in rows}) == 1 else None}
    out = []
    for r in rows:
        wp = math.sqrt(kp / r['M']) / FPS; wr = math.sqrt(kr / r['J']) / FPS
        out.append(dict(r, fit_wp=wp, fit_wr=wr, err_wp=wp / r['wp'] - 1, err_wr=wr / r['wr'] - 1))
    return cfg, out


if __name__ == '__main__':
    tol = float(sys.argv[sys.argv.index('--tol') + 1]) if '--tol' in sys.argv else 0.05
    cfg, rows = table(tol)
    print('arm mass %.3f kg (whole arm), arm inertia %.4f kg m2 (forearm and hand about the elbow)' % (rows[0]['t']['m_arm'], rows[0]['t']['I_arm']))
    print('k_pos %.1f N/m, k_rot %.2f N m/rad, zeta %s' % (cfg['k_pos_n_m'], cfg['k_rot_nm_rad'], cfg['zeta']))
    print('%-8s %-4s %7s %8s %6s %6s | %6s %6s %7s | %6s %6s %7s' % ('gun', 'take', 'm kg', 'I kg m2', 'M', 'J', 'wp lbl', 'wp fit', 'err', 'wr lbl', 'wr fit', 'err'))
    ok = True
    for r in rows:
        print('%-8s %-4s %7.3f %8.4f %6.3f %6.4f | %6.3f %6.3f %+6.1f%% | %6.3f %6.3f %+6.1f%%' % (r['gun'], r['take'], r['t']['m_gun'], r['t']['I_gun'], r['M'], r['J'], r['wp'], r['fit_wp'], 100 * r['err_wp'], r['wr'], r['fit_wr'], 100 * r['err_wr']))
        ok &= abs(r['err_wp']) <= tol and abs(r['err_wr']) <= tol
    print('within %.0f%%: %s' % (100 * tol, ok))
