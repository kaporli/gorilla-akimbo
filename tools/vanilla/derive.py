"""Writes r6/scripts/GorillaAkimbo/GorillaAkimboVanilla.reds: the game's own methods with small edits.

Some of the game's weapon and grenade methods read the fire button or stop the guns inline, with no hook to change
that. Each entry below takes the method's source from the decompiled game scripts, applies its edits (every edit must
match exactly as often as stated) and wraps the result so it only runs under the entry's condition; otherwise the
game's (or another mod's) method runs. After a game update: decompile again, run this, and look at what it reports.

  python tools/vanilla/derive.py            regenerate; lists methods whose game source changed
  python tools/vanilla/derive.py --check    exit 1 if the game source or the generated file differ
  python tools/vanilla/derive.py --accept   also record the current game source as the baseline

Game scripts: GA_GAMESCRIPTS, default C:/Modding/_tools/gamescripts, made with
  redscript-cli decompile -i "<game>/r6/cache/final.redscripts" -o <dir> -f
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.environ.get('GA_GAMESCRIPTS', 'C:/Modding/_tools/gamescripts')
OUT = os.path.join(ROOT, 'r6', 'scripts', 'GorillaAkimbo', 'GorillaAkimboVanilla.reds')
BASELINE = os.path.join(HERE, 'baseline.json')

OWNER = 'scriptInterface.executionOwner'
# Independent firing: the button of this hand's gun instead of the fire button.
INDEPENDENT = 'GorillaAkimboIndependent.Active(%s)' % OWNER
BUTTON = 'GorillaAkimboIndependent.Button(this.IsLeftWeaponLogic(), %s)' % OWNER
FIRE = (r'n"RangedAttack"', BUTTON)
# A pair's grenade throw: the right gun stays up and firing.
THROW = 'GorillaAkimboGadgetSystem.Active(%s)' % OWNER
NO_STOP = (r'[ \t]*scriptInterface\.TEMP_WeaponStopFiring\(\);\n', '')


def fire(n):
    return [FIRE + (n,)]


# (class, method, [(condition, [(regex, replacement, count)])]). Conditions are tried in order.
DERIVED = [
    ('WeaponTransition', 'IsSemiAutoAction', [(INDEPENDENT, fire(2))]),
    ('WeaponTransition', 'IsFullAutoAction', [(INDEPENDENT, fire(1))]),
    ('FullAutoDecisions', 'ToReady', [(INDEPENDENT, fire(1))]),
    ('CycleRoundEvents', 'OnUpdate', [(INDEPENDENT, fire(1))]),
    ('CycleTriggerModeDecisions', 'ToCharge', [(INDEPENDENT, fire(1))]),
    ('NoAmmoDecisions', 'ToReload', [(INDEPENDENT, fire(1))]),
    ('NoAmmoEvents', 'OnUpdate', [(INDEPENDENT, fire(1))]),
    ('ChargeDecisions', 'EnterCondition', [(INDEPENDENT, fire(1))]),
    ('ChargeDecisions', 'ToShoot', [(INDEPENDENT, fire(1))]),
    ('ChargeDecisions', 'ToChargeReady', [(INDEPENDENT, fire(1))]),
    ('ChargeReadyDecisions', 'ToShoot', [(INDEPENDENT, fire(1))]),
    ('ChargeReadyDecisions', 'ToChargeMax', [(INDEPENDENT, fire(1))]),
    ('ChargeMaxDecisions', 'ToShoot', [(INDEPENDENT, fire(2))]),
    ('DischargeDecisions', 'EnterCondition', [(INDEPENDENT, fire(1))]),
    # The right gun's reload goes on during a pair's throw (the game ends it when a grenade is used); otherwise a
    # shell-by-shell reload is cut short by the gun's own button.
    ('ReloadDecisions', 'ExitCondition', [
        ('GorillaAkimboGadget.KeepsReload(this.IsLeftWeaponLogic(), %s)' % OWNER, [
            (r' \|\| stateContext\.IsStateMachineActive\(n"CombatGadget"\) \|\| stateContext\.GetBoolParameter\(n"UnequipToGadgetOrConsumable", true\)', '', 1),
            FIRE + (1,)]),
        (INDEPENDENT, fire(1))]),
    # The right gun stays ready during a pair's throw: without the checks for the left gun being put away.
    ('WeaponReadyListenerTransition', 'IsWeaponReadyToShoot', [
        ('this.IsRightWeaponLogic() && %s && stateContext.GetBoolParameter(n"UnequipToGadgetOrConsumable", true)' % THROW, [
            (r'[ \t]*if stateContext\.GetBoolParameter\(n"UnequipToGadgetOrConsumable", true\) \{\s*return false;\s*\};?\n', '', 1),
            (r'[ \t]*if DefaultTransition\.IsRightHandInUnequippingState\(stateContext\) && DefaultTransition\.IsLeftHandInUnequippingState\(stateContext\) \{\s*return false;\s*\};?\n', '', 1),
            (r' && !DefaultTransition\.IsLeftHandInEquippedState\(stateContext\)', '', 1)])]),
    # A quick throw doesn't wait for the right gun's reload.
    ('CombatGadgetInactiveDecisions', 'ToCombatGadgetQuickThrow', [
        (THROW, [(r' && !this\.IsInWeaponReloadState\(scriptInterface\)', '', 1)])]),
    # The game stops the guns when the grenade comes up and when a charge starts or ends.
    ('CombatGadgetEquipEvents', 'OnEnter', [(THROW, [NO_STOP + (1,)])]),
    ('CombatGadgetChargeEvents', 'OnExitToCombatGadgetChargedThrow', [(THROW, [NO_STOP + (1,)])]),
    ('CombatGadgetChargeEvents', 'OnExitToCombatGadgetWaitForUnequip', [(THROW, [NO_STOP + (1,)])]),
    ('CombatGadgetChargeEvents', 'OnExitToCombatGadgetUnequip', [(THROW, [NO_STOP + (1,)])]),
    ('CombatGadgetChargeEvents', 'OnExitToCombatGadgetEquip', [(THROW, [NO_STOP + (1,)])]),
    # Charging: the grenade stays in the left hand and the right gun stays up.
    ('CombatGadgetChargeEvents', 'OnEnter', [(THROW, [
        (r'stateContext\.SetPermanentBoolParameter\(n"rightHandThrow", true, true\);', 'stateContext.RemovePermanentBoolParameter(n"rightHandThrow");', 1),
        (r'if this\.IsRightHandInEquippedState\(stateContext\) \{\s*stateContext\.SetPermanentBoolParameter\(n"forceTempUnequipWeapon", true, true\);\s*\};?', 'this.SetItemInLeftHand(scriptInterface, true);', 1)])]),
    # The charged throw: the left hand's throw, along the charged throw's path and aim.
    ('CombatGadgetChargedThrowEvents', 'OnEnter', [(THROW, [
        (r'this\.SetCombatGadgetAnimFeature\(scriptInterface, false, true\);', 'this.SetCombatGadgetAnimFeature(scriptInterface, true, false);', 1),
        (r'n"CombatGadgetChargedThrow"', 'n"CombatGadgetQuickThrow"', 1),
        (r'this\.SetThrowableAnimFeatureOnGrenade\(scriptInterface, 2, false\);', 'this.SetThrowableAnimFeatureOnGrenade(scriptInterface, 2, true);', 1)])]),
    # Heywood Hurricane goes on through the stun of V's own shot: without the weapons' ready check.
    ('DefaultTransition', 'CanBeInValentinosFrenzy', [
        ('GorillaAkimboFiringMode.OwnShotStun(scriptInterface)', [
            (r'[ \t]*if DefaultTransition\.AreWeaponsNotReady\(scriptInterface\) \{\s*return false;\s*\};?\n', '', 1)])]),
]

# Hand-written copies that can't be made by edits: only watched for changes of the game's source.
PINNED = [
    ('CombatGadgetChargeEvents', 'OnUpdate', 'GorillaAkimboGadget.reds'),
]

_files = {}


def sources():
    if not _files:
        for folder, _, names in os.walk(SCRIPTS):
            for name in names:
                if name.endswith('.script'):
                    path = os.path.join(folder, name)
                    _files[path] = open(path, encoding='utf-8', errors='replace').read()
        if not _files:
            sys.exit('no game scripts in %s (set GA_GAMESCRIPTS)' % SCRIPTS)
    return _files


def block(text, start):
    a = text.index('{', start)
    depth = 0
    for i in range(a, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return a, i + 1
    raise ValueError('unbalanced braces')


def method(cls, name):
    """(signature, body) of the game's method; body is the text between its braces."""
    for text in sources().values():
        found = re.search(r'\bclass\s+' + re.escape(cls) + r'\b[^{]*', text)
        if not found:
            continue
        a, b = block(text, found.start())
        body = text[a:b]
        head = re.search(r'^[ \t]*((?:\w+\s+)*func\s+' + re.escape(name) + r'\s*\([^{]*)\{', body, re.M)
        if not head:
            break
        x, y = block(body, head.start())
        return head.group(1).strip(), body[x + 1:y - 1].strip('\n')
    sys.exit('%s.%s not found in the game scripts' % (cls, name))


def digest(signature, body):
    return hashlib.sha1(re.sub(r'\s+', ' ', signature + body).encode()).hexdigest()[:12]


def derive(cls, name, variants):
    signature, body = method(cls, name)
    args = ', '.join(p.strip().split(':')[0].split()[-1] for p in
                     re.search(r'\((.*)\)\s*->', signature).group(1).split(',') if p.strip())
    void = signature.rstrip().endswith('Void')
    call = 'wrappedMethod(%s);' % args
    lines = ['@wrapMethod(%s)' % cls, signature + ' {']
    for condition, edits in variants:
        text = body
        for pattern, replacement, count in edits:
            text, n = re.subn(pattern, lambda m: replacement, text)
            if n != count:
                sys.exit('%s.%s: %r matched %d times, expected %d' % (cls, name, pattern, n, count))
        text = re.sub(r'\};', '}', text).rstrip()
        lines.append('  if %s {' % condition)
        lines.append(text)
        if void:
            lines.append('    return;')
        lines.append('  }')
    lines.append('  ' + (call if void else 'return ' + call))
    lines.append('}')
    return digest(signature, body), '\n'.join(lines)


def main():
    check = '--check' in sys.argv
    accept = '--accept' in sys.argv
    baseline = json.load(open(BASELINE)) if os.path.exists(BASELINE) else {}
    current = {}
    parts = ['// Generated by tools/vanilla/derive.py from the game\'s scripts. Do not edit: change the entries there.',
             '// Each method is the game\'s own code with the edits named in derive.py, run only under its condition.',
             'module GorillaAkimbo', '']
    for cls, name, variants in DERIVED:
        current['%s.%s' % (cls, name)], text = derive(cls, name, variants)
        parts += [text, '']
    for cls, name, where in PINNED:
        current['%s.%s' % (cls, name)] = digest(*method(cls, name))
    changed = [key for key in current if key in baseline and baseline[key] != current[key]]
    for key in changed:
        where = next((w for c, n, w in PINNED if '%s.%s' % (c, n) == key), None)
        print('game source changed: %s%s' % (key, ' (hand-written copy in %s)' % where if where else ''))
    output = '\n'.join(parts).rstrip('\n') + '\n'
    same = os.path.exists(OUT) and open(OUT, encoding='utf-8', newline='').read().replace('\r\n', '\n') == output
    if check:
        if changed or not same or set(current) != set(baseline):
            sys.exit('derive.py --check: %s' % ('game source changed' if changed else 'generated file or baseline out of date'))
        print('ok: %d methods' % len(current))
        return
    open(OUT, 'w', encoding='utf-8', newline='\n').write(output)
    if accept or not baseline:
        json.dump(current, open(BASELINE, 'w', newline='\n'), indent=1, sort_keys=True)
        open(BASELINE, 'a', newline='\n').write('\n')
    elif set(current) != set(baseline):
        print('baseline.json lists other methods: run with --accept after checking the report above')
    print('wrote %s (%d derived, %d watched)' % (os.path.relpath(OUT, ROOT), len(DERIVED), len(PINNED)))


if __name__ == '__main__':
    main()
