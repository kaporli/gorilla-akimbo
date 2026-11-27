// Input hints for independent firing: while it is on and two guns are drawn, the game's hint list shows the button
// that fires each gun and the aim key (GorillaAkimboIndependent.reds). The left gun key has its own hint, "Put away
// left gun" while a pair is drawn and "Draw left gun" while it is away (GorillaAkimboToggle.reds). They are added and
// removed with the game's own ranged weapon hints (Reload, Quick Melee Attack), so they hide and come back with them.
// The hint list shows the key bound to each action, so rebinds and the current device show as they are. Aim is left
// out while it has no key.
module GorillaAkimbo

// The aim key's binding, from its Key Bindings entries: the game names the keyboard entry after the input file's
// overridableUI, Unified Keybinds adds a controller entry with MKPad_ in front. Without an entry the input file's
// default applies.
public class GorillaAkimboAimKeys extends ScriptableSystem {
  private let m_searched: Bool;
  private let m_root: ref<ConfigGroup>;
  private let m_names: array<CName>;
  private let m_entries: array<ref<ConfigVarName>>;

  private static func Find(group: ref<ConfigGroup>, name: CName) -> ref<ConfigVarName> {
    if group.HasVar(name) {
      return group.GetVar(name) as ConfigVarName;
    }
    for child in group.GetGroups(false) {
      let found = GorillaAkimboAimKeys.Find(child, name);
      if IsDefined(found) {
        return found;
      }
    }
    return null;
  }

  // The key aim has on this device, or None when it is unbound.
  public static func Get(game: GameInstance, pad: Bool) -> CName {
    return GorillaAkimboAimKeys.GetNamed(game, pad, n"gorillaAkimboAim");
  }

  // The key of one of the mod's actions (its overridableUI name) on this device, or None when it is unbound.
  public static func GetNamed(game: GameInstance, pad: Bool, name: CName) -> CName {
    let fallback = GorillaAkimboAimKeys.Default(pad, name);
    let system = GameInstance.GetScriptableSystemsContainer(game).Get(n"GorillaAkimbo.GorillaAkimboAimKeys") as GorillaAkimboAimKeys;
    if !IsDefined(system) {
      return fallback;
    }
    if !system.m_searched {
      system.m_searched = true;
      let settings = GameInstance.GetSettingsSystem(game);
      if settings.HasGroup(n"/key_bindings") {
        system.m_root = settings.GetGroup(n"/key_bindings");
      }
    }
    if !IsDefined(system.m_root) {
      return fallback;
    }
    let entryName = pad ? StringToName("MKPad_" + NameToString(name)) : name;
    let index = ArrayFindFirst(system.m_names, entryName);
    if index < 0 {
      ArrayPush(system.m_names, entryName);
      ArrayPush(system.m_entries, GorillaAkimboAimKeys.Find(system.m_root, entryName));
      index = ArraySize(system.m_names) - 1;
    }
    let entry = system.m_entries[index];
    if !IsDefined(entry) {
      return fallback;
    }
    let key = entry.GetValue();
    if !IsNameValid(key) || Equals(key, n"IK_None") {
      return n"None";
    }
    return key;
  }

  // The input file's default.
  private static func Default(pad: Bool, name: CName) -> CName {
    if Equals(name, n"gorillaAkimboToggle") {
      return pad ? n"IK_Pad_LeftShoulderBackSelect" : n"IK_F2";
    }
    return pad ? n"IK_Pad_LeftThumb" : n"IK_Mouse4";
  }
}

public abstract class GorillaAkimboHints {
  public static func Source() -> CName {
    return n"GorillaAkimbo";
  }

  // Which hints are wanted. Independent firing in the low bits: 0 none, 1 mouse and keyboard, 2 controller, 3 and 4 the
  // same without aim. The left gun key from bit 3: 0 none, 1 put away, 2 draw.
  public static func Mode(owner: wref<GameObject>) -> Int32 {
    return GorillaAkimboHints.FireMode(owner) + 8 * GorillaAkimboToggle.HintMode(owner);
  }

  public static func FireMode(owner: wref<GameObject>) -> Int32 {
    if !GorillaAkimboIndependent.Active(owner) {
      return 0;
    }
    let pad = GorillaAkimboIndependent.OnPad(owner.GetGame());
    let mode = pad ? 2 : 1;
    if Equals(GorillaAkimboAimKeys.Get(owner.GetGame(), pad), n"None") {
      mode += 2;
    }
    return mode;
  }

  // The aim key the hints were made for, so a rebind refreshes them.
  public static func Key(owner: wref<GameObject>, mode: Int32) -> CName {
    if mode % 8 == 0 {
      return n"None";
    }
    return GorillaAkimboAimKeys.Get(owner.GetGame(), GorillaAkimboIndependent.OnPad(owner.GetGame()));
  }

  // The same for the left gun key.
  public static func ToggleKey(owner: wref<GameObject>, mode: Int32) -> CName {
    if mode < 8 {
      return n"None";
    }
    return GorillaAkimboAimKeys.GetNamed(owner.GetGame(), GorillaAkimboIndependent.OnPad(owner.GetGame()), n"gorillaAkimboToggle");
  }

  private static func Send(game: GameInstance, action: CName, source: CName, label: String, sorting: Int32, show: Bool) -> Void {
    let evt = new UpdateInputHintEvent();
    evt.data.action = action;
    evt.data.source = source;
    evt.data.localizedLabel = label;
    evt.data.holdIndicationType = inkInputHintHoldIndicationType.Press;
    evt.data.sortingPriority = sorting;
    evt.show = show;
    evt.targetHintContainer = n"GameplayInputHelper";
    GameInstance.GetUISystem(game).QueueEvent(evt);
  }

  public static func Remove(game: GameInstance) -> Void {
    let evt = new DeleteInputHintBySourceEvent();
    evt.source = GorillaAkimboHints.Source();
    evt.targetHintContainer = n"GameplayInputHelper";
    GameInstance.GetUISystem(game).QueueEvent(evt);
  }

  // Shows the hints for this mode. The game's Charge hint (fire button, tech guns) is taken down: each button now
  // charges its own gun, which the hints already say.
  public static func Add(game: GameInstance, mode: Int32) -> Void {
    GorillaAkimboHints.Remove(game);
    if mode == 0 {
      return;
    }
    let source = GorillaAkimboHints.Source();
    let fire = mode % 8;
    if fire > 0 {
      GorillaAkimboHints.Send(game, n"RangedAttack", n"Ranged", "", 0, false);
      GorillaAkimboHints.Send(game, GorillaAkimboIndependent.FireAction(true, game), source, GetLocalizedTextByKey(n"GorillaAkimbo-HintFireLeft"), -3, true);
      GorillaAkimboHints.Send(game, GorillaAkimboIndependent.FireAction(false, game), source, GetLocalizedTextByKey(n"GorillaAkimbo-HintFireRight"), -2, true);
      if fire <= 2 {
        GorillaAkimboHints.Send(game, GorillaAkimboIndependent.AimAction(), source, GetLocalizedTextByKey(n"GorillaAkimbo-HintAim"), -1, true);
      }
    }
    if mode >= 8 {
      let label = mode / 8 == 1 ? n"GorillaAkimbo-HintLeftAway" : n"GorillaAkimbo-HintLeftDraw";
      GorillaAkimboHints.Send(game, GorillaAkimboToggle.Action(), source, GetLocalizedTextByKey(label), 0, true);
    }
  }
}

@wrapMethod(InputContextTransitionEvents)
protected final const func ShowRangedInputHints(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  let mode = GorillaAkimboHints.Mode(scriptInterface.executionOwner);
  GorillaAkimboHints.Add(scriptInterface.GetGame(), mode);
  stateContext.SetPermanentIntParameter(n"gorillaAkimboHints", mode, true);
  stateContext.SetPermanentCNameParameter(n"gorillaAkimboHintsKey", GorillaAkimboHints.Key(scriptInterface.executionOwner, mode), true);
  stateContext.SetPermanentCNameParameter(n"gorillaAkimboHintsToggleKey", GorillaAkimboHints.ToggleKey(scriptInterface.executionOwner, mode), true);
}

@wrapMethod(InputContextTransitionEvents)
protected final func RemoveRangedInputHints(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  if this.m_isGameplayInputHintManagerInitialized {
    GorillaAkimboHints.Remove(scriptInterface.GetGame());
  }
  stateContext.SetPermanentIntParameter(n"gorillaAkimboHints", 0, true);
  stateContext.SetPermanentCNameParameter(n"gorillaAkimboHintsKey", n"None", true);
  stateContext.SetPermanentCNameParameter(n"gorillaAkimboHintsToggleKey", n"None", true);
}

// Changes the game doesn't refresh its hints for: the setting, a pair drawn or put away while the other hints stay,
// the device the fire buttons follow, and the aim key.
@wrapMethod(InputContextTransitionEvents)
protected final func UpdateWeaponInputHints(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> ActiveBaseContext {
  let context = wrappedMethod(stateContext, scriptInterface);
  if NotEquals(context, ActiveBaseContext.None) {
    return context;
  }
  let owner = scriptInterface.executionOwner;
  let shown = stateContext.GetIntParameter(n"gorillaAkimboHints", true);
  let wanted = stateContext.GetBoolParameter(n"isRangedInputHintDisplayed", true) ? GorillaAkimboHints.Mode(owner) : 0;
  let key = GorillaAkimboHints.Key(owner, wanted);
  let shownKey = stateContext.GetPermanentCNameParameter(n"gorillaAkimboHintsKey");
  let toggleKey = GorillaAkimboHints.ToggleKey(owner, wanted);
  let shownToggleKey = stateContext.GetPermanentCNameParameter(n"gorillaAkimboHintsToggleKey");
  if shown == wanted && (wanted % 8 == 0 || shownKey.valid && Equals(shownKey.value, key))
    && (wanted < 8 || shownToggleKey.valid && Equals(shownToggleKey.value, toggleKey)) {
    return context;
  }
  GorillaAkimboHints.Add(scriptInterface.GetGame(), wanted);
  if wanted % 8 == 0 && stateContext.GetBoolParameter(n"isChargeInputHintDisplayed", true) {
    this.ShowInputHint(scriptInterface, n"RangedAttack", n"Ranged", "LocKey#47919", inkInputHintHoldIndicationType.FromInputConfig, true, 0);
  }
  stateContext.SetPermanentIntParameter(n"gorillaAkimboHints", wanted, true);
  stateContext.SetPermanentCNameParameter(n"gorillaAkimboHintsKey", key, true);
  stateContext.SetPermanentCNameParameter(n"gorillaAkimboHintsToggleKey", toggleKey, true);
  return context;
}
