// Independent firing (setting): while dual-wielding, each fire button fires one gun and aiming moves to its own key
// (GorillaAkimboAim, r6/input/GorillaAkimbo.xml). Mouse: left button the left gun, right button the right gun.
// Controller: left trigger the left gun, right trigger the right gun. The game reads the fire button (RangedAttack) in
// many weapon states; each of those reads the hand's own button instead, only while independent firing is on and
// two guns are drawn. Those methods are the game's own code with the button replaced, generated into
// GorillaAkimboVanilla.reds (tools/vanilla/derive.py). Everything else runs the game's code.
module GorillaAkimbo

public abstract class GorillaAkimboIndependent {
  public static func AimAction() -> CName {
    return n"GorillaAkimboAim";
  }

  public static func Active(owner: wref<GameObject>) -> Bool {
    return IsDefined(owner) && GorillaAkimboConfig.Get(owner.GetGame()).independentFiring && GameObject.IsDualWielding(owner);
  }

  public static func OnPad(game: GameInstance) -> Bool {
    let defs = GetAllBlackboardDefs().InputSchemes;
    return Cast<Int32>(GameInstance.GetBlackboardSystem(game).Get(defs).GetUint(defs.Device)) % 256 == EnumInt(InputDevice.PAD);
  }

  // The action that fires the gun in this hand: the button on that side of the mouse or controller.
  public static func FireAction(left: Bool, game: GameInstance) -> CName {
    return Equals(left, GorillaAkimboIndependent.OnPad(game)) ? n"CameraAim" : n"RangedAttack";
  }

  // The button a gun's weapon states read: this hand's own while active, the fire button otherwise.
  public static func Button(left: Bool, owner: wref<GameObject>) -> CName {
    return GorillaAkimboIndependent.Active(owner) ? GorillaAkimboIndependent.FireAction(left, owner.GetGame()) : n"RangedAttack";
  }

  // From the last values of both buttons, the one of this hand's button (the fire button when not active).
  public static func HandValue(owner: wref<GameObject>, left: Bool, ranged: Float, aim: Float) -> Float {
    if GorillaAkimboIndependent.Active(owner) && Equals(GorillaAkimboIndependent.FireAction(left, owner.GetGame()), n"CameraAim") {
      return aim;
    }
    return ranged;
  }
}

// Gorilla Akimbo's own listener for both fire buttons of one weapon state (semi-auto, full-auto, charge). The state's
// own listener keeps only what the game or another mod registered on it, so the right mouse button (left trigger) never
// reaches the game's code through Gorilla Akimbo, and Gorilla Akimbo still gets it when another mod filters it out.
public class GorillaAkimboFireListener extends IScriptable {
  private let m_state: wref<WeaponTransition>;

  public static func Register(state: ref<WeaponTransition>, owner: ref<GameObject>) -> ref<GorillaAkimboFireListener> {
    let listener = new GorillaAkimboFireListener();
    listener.m_state = state;
    owner.RegisterInputListener(listener, n"RangedAttack");
    owner.RegisterInputListener(listener, n"CameraAim");
    return listener;
  }

  protected cb func OnAction(action: ListenerAction, consumer: ListenerActionConsumer) -> Bool {
    let input = ListenerAction.GetName(action);
    let value = ListenerAction.GetValue(action);
    let semi = this.m_state as SemiAutoDecisions;
    if IsDefined(semi) {
      semi.GorillaAkimboInput(input, value);
    }
    let full = this.m_state as FullAutoDecisions;
    if IsDefined(full) {
      full.GorillaAkimboInput(input, value);
    }
    let charge = this.m_state as ChargeDecisions;
    if IsDefined(charge) {
      charge.GorillaAkimboInput(input, value);
    }
    return false;
  }
}

// Both guns may fire at any time; each one checks its own button.
@wrapMethod(WeaponTransition)
protected final const func ShouldShoot(scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  // Neither gun fires during a two-handed top-magazine reload (GorillaAkimboTopMag.reds).
  if GorillaAkimboTopMagSystem.Busy(scriptInterface.GetGame()) {
    return false;
  }
  if GorillaAkimboIndependent.Active(scriptInterface.executionOwner)
    && scriptInterface.localBlackboard.GetInt(GetAllBlackboardDefs().PlayerStateMachine.ShootState) < EnumInt(gamePSMShootStates.ValentinosFrenzyInit) {
    return true;
  }
  return wrappedMethod(scriptInterface);
}

// Semi-auto and full-auto states only check their conditions while the fire button is down, from an input listener:
// they also get both buttons from Gorilla Akimbo's listener and, while active, take the value of the hand's own button,
// whatever their own listener got. While not active, their own listener runs the game's (or another mod's) code.
@addField(SemiAutoDecisions)
private let m_gorillaOwner: wref<GameObject>;

@addField(SemiAutoDecisions)
private let m_gorillaRanged: Float;

@addField(SemiAutoDecisions)
private let m_gorillaAim: Float;

@addField(SemiAutoDecisions)
private let m_gorillaListener: ref<GorillaAkimboFireListener>;

@wrapMethod(SemiAutoDecisions)
protected final func OnAttach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  this.m_gorillaOwner = scriptInterface.executionOwner;
  this.m_gorillaRanged = scriptInterface.GetActionValue(n"RangedAttack");
  this.m_gorillaAim = scriptInterface.GetActionValue(n"CameraAim");
  this.m_gorillaListener = GorillaAkimboFireListener.Register(this, scriptInterface.executionOwner);
  this.GorillaAkimboInput(n"RangedAttack", this.m_gorillaRanged);
}

@wrapMethod(SemiAutoDecisions)
protected final func OnDetach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if IsDefined(this.m_gorillaListener) {
    scriptInterface.executionOwner.UnregisterInputListener(this.m_gorillaListener);
    this.m_gorillaListener = null;
  }
  wrappedMethod(stateContext, scriptInterface);
}

@addMethod(SemiAutoDecisions)
public final func GorillaAkimboInput(input: CName, value: Float) -> Void {
  if Equals(input, n"CameraAim") {
    this.m_gorillaAim = value;
  } else {
    this.m_gorillaRanged = value;
  }
  if GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    this.OnRangeAttackInput(input, value);
  }
}

@wrapMethod(SemiAutoDecisions)
protected final func OnRangeAttackInput(input: CName, value: Float) -> Void {
  if GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    wrappedMethod(n"RangedAttack", GorillaAkimboIndependent.HandValue(this.m_gorillaOwner, this.IsLeftWeaponLogic(), this.m_gorillaRanged, this.m_gorillaAim));
  } else {
    wrappedMethod(input, value);
  }
}

@addField(FullAutoDecisions)
private let m_gorillaOwner: wref<GameObject>;

@addField(FullAutoDecisions)
private let m_gorillaRanged: Float;

@addField(FullAutoDecisions)
private let m_gorillaAim: Float;

@addField(FullAutoDecisions)
private let m_gorillaListener: ref<GorillaAkimboFireListener>;

@wrapMethod(FullAutoDecisions)
protected final func OnAttach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  this.m_gorillaOwner = scriptInterface.executionOwner;
  this.m_gorillaRanged = scriptInterface.GetActionValue(n"RangedAttack");
  this.m_gorillaAim = scriptInterface.GetActionValue(n"CameraAim");
  this.m_gorillaListener = GorillaAkimboFireListener.Register(this, scriptInterface.executionOwner);
  this.GorillaAkimboInput(n"RangedAttack", this.m_gorillaRanged);
}

@wrapMethod(FullAutoDecisions)
protected final func OnDetach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if IsDefined(this.m_gorillaListener) {
    scriptInterface.executionOwner.UnregisterInputListener(this.m_gorillaListener);
    this.m_gorillaListener = null;
  }
  wrappedMethod(stateContext, scriptInterface);
}

@addMethod(FullAutoDecisions)
public final func GorillaAkimboInput(input: CName, value: Float) -> Void {
  if Equals(input, n"CameraAim") {
    this.m_gorillaAim = value;
  } else {
    this.m_gorillaRanged = value;
  }
  if GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    this.OnRangeAttackInput(input, value);
  }
}

@wrapMethod(FullAutoDecisions)
protected final func OnRangeAttackInput(input: CName, value: Float) -> Void {
  if GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    wrappedMethod(n"RangedAttack", GorillaAkimboIndependent.HandValue(this.m_gorillaOwner, this.IsLeftWeaponLogic(), this.m_gorillaRanged, this.m_gorillaAim));
  } else {
    wrappedMethod(input, value);
  }
}

// Charge weapons (tech guns while aiming): charge on the gun's own button and fire when it is let go.
@addField(ChargeDecisions)
private let m_gorillaOwner: wref<GameObject>;

@addField(ChargeDecisions)
private let m_gorillaRanged: Float;

@addField(ChargeDecisions)
private let m_gorillaAim: Float;

@addField(ChargeDecisions)
private let m_gorillaListener: ref<GorillaAkimboFireListener>;

@wrapMethod(ChargeDecisions)
protected final func OnAttach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  this.m_gorillaOwner = scriptInterface.executionOwner;
  this.m_gorillaRanged = scriptInterface.GetActionValue(n"RangedAttack");
  this.m_gorillaAim = scriptInterface.GetActionValue(n"CameraAim");
  this.m_gorillaListener = GorillaAkimboFireListener.Register(this, scriptInterface.executionOwner);
}

@wrapMethod(ChargeDecisions)
protected final func OnDetach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if IsDefined(this.m_gorillaListener) {
    scriptInterface.executionOwner.UnregisterInputListener(this.m_gorillaListener);
    this.m_gorillaListener = null;
  }
  wrappedMethod(stateContext, scriptInterface);
}

// Both buttons come from Gorilla Akimbo's listener; the state's own listener only runs the game's code while not active.
@addMethod(ChargeDecisions)
public final func GorillaAkimboInput(input: CName, value: Float) -> Void {
  if Equals(input, n"CameraAim") {
    this.m_gorillaAim = value;
  } else {
    this.m_gorillaRanged = value;
  }
  if GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    this.UpdateRangedAttackInput(GorillaAkimboIndependent.HandValue(this.m_gorillaOwner, this.IsLeftWeaponLogic(), this.m_gorillaRanged, this.m_gorillaAim));
    this.UpdateOnEnterConditionEnabled();
  }
}

@wrapMethod(ChargeDecisions)
protected cb func OnAction(action: ListenerAction, consumer: ListenerActionConsumer) -> Bool {
  if !GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    return wrappedMethod(action, consumer);
  }
  return true;
}

@wrapMethod(ChargeEvents)
protected final func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  if GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    let fire = GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame());
    stateContext.SetPermanentIntParameter(this.GetLastChargePressCount(), Cast<Int32>(scriptInterface.GetActionPressCount(fire)), true);
  }
}

// Lowered guns in public places come up on either fire button (they also stay up while it is held: the
// PublicSafeDecisions.EnterCondition wrap in GorillaAkimboGadget.reds).
@wrapMethod(PublicSafeDecisions)
private final const func ShouldLeaveSafe(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if GorillaAkimboIndependent.Active(scriptInterface.executionOwner) && scriptInterface.GetActionValue(n"CameraAim") > 0.0 {
    return true;
  }
  return wrappedMethod(stateContext, scriptInterface);
}

// Aiming: while active, the aim key aims and the right mouse button (left trigger) does not. A release only counts
// from the button that started aiming, so firing the right gun while aiming doesn't stop it.
@addField(AimingStateDecisions)
private let m_gorillaAimSource: CName;

@wrapMethod(AimingStateDecisions)
protected final func OnAttach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  scriptInterface.executionOwner.RegisterInputListener(this, GorillaAkimboIndependent.AimAction());
}

@wrapMethod(AimingStateDecisions)
protected cb func OnAction(action: ListenerAction, consumer: ListenerActionConsumer) -> Bool {
  let name = ListenerAction.GetName(action);
  if ListenerAction.GetValue(action) > 0.0 {
    let wanted = GorillaAkimboIndependent.Active(this.m_executionOwner) ? GorillaAkimboIndependent.AimAction() : n"CameraAim";
    if NotEquals(name, wanted) {
      return false;
    }
    this.m_gorillaAimSource = name;
  } else {
    let source = IsNameValid(this.m_gorillaAimSource) ? this.m_gorillaAimSource : n"CameraAim";
    if NotEquals(name, source) {
      return false;
    }
  }
  return wrappedMethod(action, consumer);
}
