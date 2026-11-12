// Grenades while dual-wielding SMGs or shotguns: the left gun is put away while the left hand throws, as the game does
// for pistol pairs, and the right gun stays up and can fire the whole time. The game's charged throw moves the
// grenade to the right hand and puts the right gun away; during a pair's throw the grenade stays in the left hand
// instead: it stays in the left hand while charging and is thrown with the left-hand throw, along the charged
// throw's path.
// The left gun comes back on its own once the grenade is gone (the game's own unequip), with its magazine as it was.
module GorillaAkimbo

public class GorillaAkimboGadgetSystem extends ScriptableSystem {
  // A pair's throw is under way: from the grenade request until the left gun is back.
  public let active: Bool;
  public let startedAt: Float;
  // When the grenade's state machine ended (-1 while it runs).
  public let endedAt: Float;
  // A grenade asked for during a two-handed top-magazine reload, started once the reload is done.
  public let pending: Bool;
  public let pendingAt: Float;

  public static func Get(game: GameInstance) -> ref<GorillaAkimboGadgetSystem> {
    return GameInstance.GetScriptableSystemsContainer(game).Get(n"GorillaAkimbo.GorillaAkimboGadgetSystem") as GorillaAkimboGadgetSystem;
  }

  public static func Now(game: GameInstance) -> Float {
    return EngineTime.ToFloat(GameInstance.GetSimTime(game));
  }

  // Whether a pair's throw is under way. Lapses a moment after the grenade is done, or after a long time, so a
  // throw cut off without its end (a save loaded mid-throw) can't keep the right gun's checks changed.
  public static func Active(owner: wref<GameObject>) -> Bool {
    if !IsDefined(owner) {
      return false;
    }
    let system = GorillaAkimboGadgetSystem.Get(owner.GetGame());
    if !IsDefined(system) || !system.active {
      return false;
    }
    let now = GorillaAkimboGadgetSystem.Now(owner.GetGame());
    if (system.endedAt >= 0.0 && now - system.endedAt > 2.0) || now - system.startedAt > 30.0 {
      system.active = false;
      return false;
    }
    return true;
  }

  public func Start() {
    this.active = true;
    this.startedAt = GorillaAkimboGadgetSystem.Now(this.GetGameInstance());
    this.endedAt = -1.0;
    this.pending = false;
  }

  public func End() {
    if this.active && this.endedAt < 0.0 {
      this.endedAt = GorillaAkimboGadgetSystem.Now(this.GetGameInstance());
    }
  }

  public func Stop() {
    this.active = false;
  }
}

public abstract class GorillaAkimboGadget {
  // Both hands hold guns and one of them is an SMG or shotgun.
  public static func IsPair(owner: wref<GameObject>) -> Bool {
    if !IsDefined(owner) || !GameObject.IsDualWielding(owner) {
      return false;
    }
    let right = GameObject.GetRightActiveWeapon(owner);
    let left = GameObject.GetLeftActiveWeapon(owner);
    if !IsDefined(right) || !IsDefined(left) {
      return false;
    }
    return IsGripWeaponType(RPGManager.GetItemType(right.GetItemID())) || IsGripWeaponType(RPGManager.GetItemType(left.GetItemID()));
  }

  // The right gun's reload goes on during a pair's throw.
  public static func KeepsReload(left: Bool, owner: wref<GameObject>) -> Bool {
    return !left && GorillaAkimboGadgetSystem.Active(owner);
  }
}

// The grenade request: a pair's throw starts here. During a two-handed top-magazine reload both hands are busy, so
// the request waits until the reload is done (see DualWieldEvents.OnUpdate).
@wrapMethod(EquipmentSystemPlayerData)
public final func OnEquipmentSystemWeaponManipulationRequest(request: ref<EquipmentSystemWeaponManipulationRequest>) -> Void {
  if Equals(request.requestType, EquipmentManipulationAction.RequestGadget) && IsDefined(this.m_owner)
    && Equals(RPGManager.GetItemCategory(this.GetActiveGadget()), gamedataItemCategory.Gadget) && GorillaAkimboGadget.IsPair(this.m_owner) {
    let game = this.m_owner.GetGame();
    let system = GorillaAkimboGadgetSystem.Get(game);
    if GorillaAkimboTopMagSystem.Busy(game) {
      system.pending = true;
      system.pendingAt = GorillaAkimboGadgetSystem.Now(game);
      return;
    }
    system.Start();
  }
  wrappedMethod(request);
}

@wrapMethod(DualWieldEvents)
protected final func OnUpdate(timeDelta: Float, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(timeDelta, stateContext, scriptInterface);
  let game = scriptInterface.GetGame();
  let system = GorillaAkimboGadgetSystem.Get(game);
  if !system.pending || GorillaAkimboTopMagSystem.Busy(game) {
    return;
  }
  system.pending = false;
  if GorillaAkimboGadgetSystem.Now(game) - system.pendingAt < 5.0 && !stateContext.IsStateMachineActive(n"CombatGadget")
    && this.PlayerHasGrenadeCharges(scriptInterface) && GorillaAkimboGadget.IsPair(scriptInterface.executionOwner) {
    this.SendEquipmentSystemWeaponManipulationRequest(scriptInterface, EquipmentManipulationAction.RequestGadget);
  }
}

@wrapMethod(CombatGadgetUnequipEvents)
protected func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  GorillaAkimboGadgetSystem.Get(scriptInterface.GetGame()).End();
}

@wrapMethod(CombatGadgetWaitForUnequipEvents)
protected final func OnForcedExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  GorillaAkimboGadgetSystem.Get(scriptInterface.GetGame()).End();
}

// The right gun stays ready to fire during a pair's throw: the game holds every gun while a grenade is in use and
// while the left gun is put away for it.
@wrapMethod(WeaponReadyListenerTransition)
protected cb func OnCombatGadgetChanged(value: Int32) -> Bool {
  let result = wrappedMethod(value);
  if this.m_isUsingCombatGadget && this.IsRightWeaponLogic() && GorillaAkimboGadgetSystem.Active(this.m_executionOwner) {
    this.m_isUsingCombatGadget = false;
    this.UpdateWeaponReadyListenerReturnValue();
  }
  return result;
}

// Charging: the grenade stays in the left hand, where the trajectory preview starts (the game moves it to the right
// hand once the right gun is away). Written by hand; tools/vanilla/derive.py reports when the game's method changes.
// The other throw methods are the game's own with small edits, in GorillaAkimboVanilla.reds.
@wrapMethod(CombatGadgetChargeEvents)
protected final func OnUpdate(timeDelta: Float, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    wrappedMethod(timeDelta, stateContext, scriptInterface);
    return;
  }
  if !this.initiated {
    let grenade = scriptInterface.GetTransactionSystem().GetItemInSlot(scriptInterface.executionOwner, t"AttachmentSlots.WeaponLeft");
    if IsDefined(grenade) {
      this.SetBlackboardIntVariable(scriptInterface, GetAllBlackboardDefs().PlayerStateMachine.CombatGadget, 3);
      let setup = new gameprojectileSetUpEvent();
      setup.owner = scriptInterface.executionOwner;
      setup.trajectoryParams = this.CreateTrajectoryParams(grenade, false);
      grenade.QueueEvent(setup);
      this.SetThrowableAnimFeatureOnGrenade(scriptInterface, 1, grenade);
      this.initiated = true;
      this.itemSwitched = true;
    }
  }
  if this.CheckEquipDurationCondition(scriptInterface, stateContext) {
    this.TogglePreview(true, scriptInterface, stateContext);
  }
}

// After a pair's throw in a public safe zone the left gun comes back with a fresh safe timer and lowers about a second
// later while the right gun, fired during the throw, is still up. With one hand lowered and the other raised the arm
// graph plays the game's pistol lowered pose on the right hand for a moment (a large swing across the view). The left
// gun of a grip pair therefore lowers only once the right gun has lowered.
// Independent firing: guns don't lower while the right mouse button (left trigger) is held, as with the fire button.
@wrapMethod(PublicSafeDecisions)
protected final const func EnterCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if this.IsLeftWeaponLogic() && GorillaAkimboGadget.IsPair(scriptInterface.executionOwner)
    && scriptInterface.localBlackboard.GetInt(GetAllBlackboardDefs().PlayerStateMachine.RightWeapon) != EnumInt(gamePSMRangedWeaponStates.Safe) {
    return false;
  }
  if GorillaAkimboIndependent.Active(scriptInterface.executionOwner) && scriptInterface.GetActionValue(n"CameraAim") > 0.0 {
    return false;
  }
  return wrappedMethod(stateContext, scriptInterface);
}
