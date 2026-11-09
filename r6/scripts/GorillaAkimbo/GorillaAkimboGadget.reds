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

// The throw is over once the left gun is equipped again.
@wrapMethod(EquipCycleEvents)
protected func OnExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  if this.IsLeftHandLogic(this.stateMachineInstanceData) && IsDefined(GameObject.GetLeftActiveWeapon(scriptInterface.executionOwner)) {
    GorillaAkimboGadgetSystem.Get(scriptInterface.GetGame()).Stop();
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

@wrapMethod(WeaponReadyListenerTransition)
protected final const func IsWeaponReadyToShoot(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !this.IsRightWeaponLogic() || !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner)
    || !stateContext.GetBoolParameter(n"UnequipToGadgetOrConsumable", true) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  // The game's checks, without the one for the left gun being put away for the grenade.
  if !this.m_weaponReadyListenerReturnValue || stateContext.IsStateMachineActive(n"Consumable") {
    return false;
  }
  if this.m_isInWorkspot && !stateContext.GetBoolParameter(n"isInVehCombat", true) && !stateContext.GetBoolParameter(n"isInDriverCombat", true) {
    return false;
  }
  if !this.IsRightHandInEquippedState(stateContext) {
    return false;
  }
  if (scriptInterface.executionOwner as PlayerPuppet).IsAimingAtFriendly() {
    return this.ShouldIgnoreWeaponSafe(scriptInterface);
  }
  return true;
}

// A reload of the right gun goes on during a pair's throw (the game ends it when a grenade is used).
@wrapMethod(ReloadDecisions)
protected final const func ExitCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboGadget.KeepsReload(this.IsLeftWeaponLogic(), scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  if this.IsReloadDurationComplete(stateContext, scriptInterface) && stateContext.GetBoolParameter(this.GetFinishedReload(), true) {
    return true;
  }
  if stateContext.IsStateMachineActive(n"Consumable") {
    return true;
  }
  if stateContext.GetBoolParameter(n"TryInterruptReload") && !this.IsReloadUninterruptible(stateContext, scriptInterface) {
    return true;
  }
  let fire = GorillaAkimboIndependent.Active(scriptInterface.executionOwner) ? GorillaAkimboIndependent.FireAction(false, scriptInterface.GetGame()) : n"RangedAttack";
  if this.ShouldShoot(scriptInterface) && scriptInterface.IsActionJustPressed(fire)
    && Cast<Int32>(scriptInterface.GetStatsSystem().GetStatValue(Cast<StatsObjectID>(scriptInterface.ownerEntityID), gamedataStatType.ReloadAmount)) > 0 {
    if !this.GetWeaponObject(scriptInterface).IsMagazineEmpty() && !this.IsReloadUninterruptible(stateContext, scriptInterface) {
      return true;
    }
  }
  if !scriptInterface.HasStatFlag(gamedataStatType.CanWeaponReloadWhileVaulting) && stateContext.IsStateActive(n"Locomotion", n"vault") {
    return true;
  }
  return false;
}

// A quick throw doesn't wait for the right gun's reload.
@wrapMethod(CombatGadgetInactiveDecisions)
protected final const func ToCombatGadgetQuickThrow(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    return scriptInterface.GetActionValue(n"UseCombatGadget") == 0.0 && NotEquals(stateContext.GetStateMachineCurrentState(n"UpperBody"), n"useConsumable");
  }
  return wrappedMethod(stateContext, scriptInterface);
}

// The game stops the gun's firing when the grenade comes up and when a charge starts or ends; the right gun keeps
// firing during a pair's throw.
@wrapMethod(CombatGadgetEquipEvents)
protected func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    wrappedMethod(stateContext, scriptInterface);
    return;
  }
  this.SetBlackbordThrowUnequip(scriptInterface, false);
  scriptInterface.PushAnimationEvent(n"CombatGadgetEquip");
  stateContext.RemovePermanentBoolParameter(n"cgCached");
  this.SetBlackboardIntVariable(scriptInterface, GetAllBlackboardDefs().PlayerStateMachine.CombatGadget, 2);
}

// Charging: the grenade stays in the left hand and the right gun stays up (the game puts it away and moves the
// grenade to the right hand). The trajectory preview starts from the left hand.
@wrapMethod(CombatGadgetChargeEvents)
protected func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    wrappedMethod(stateContext, scriptInterface);
    return;
  }
  let broadcaster = scriptInterface.executionOwner.GetStimBroadcasterComponent();
  if IsDefined(broadcaster) {
    broadcaster.AddActiveStimuli(scriptInterface.executionOwner, gamedataStimType.IllegalInteraction, -1.0);
  }
  this.DisableCameraBobbing(stateContext, scriptInterface, true);
  this.ShowInputHint(scriptInterface, n"CancelChargingCG", n"Locomotion", "LocKey#49906");
  this.initiated = false;
  this.itemSwitched = false;
  stateContext.RemovePermanentBoolParameter(n"rightHandThrow");
  this.SetCombatGadgetAnimFeature(scriptInterface, false, true);
  this.SetItemInLeftHand(scriptInterface, true);
}

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

@addMethod(CombatGadgetChargeEvents)
private final func GorillaChargeEnd(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) {
  this.TogglePreview(false, scriptInterface, stateContext);
  let broadcaster = scriptInterface.executionOwner.GetStimBroadcasterComponent();
  if IsDefined(broadcaster) {
    broadcaster.RemoveActiveStimuliByName(scriptInterface.executionOwner, gamedataStimType.IllegalInteraction);
  }
  this.DisableCameraBobbing(stateContext, scriptInterface, false);
  this.RemoveInputHint(scriptInterface, n"CancelChargingCG", n"Locomotion");
}

@wrapMethod(CombatGadgetChargeEvents)
protected final func OnExitToCombatGadgetChargedThrow(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    wrappedMethod(stateContext, scriptInterface);
    return;
  }
  this.GorillaChargeEnd(stateContext, scriptInterface);
}

@wrapMethod(CombatGadgetChargeEvents)
protected final func OnExitToCombatGadgetWaitForUnequip(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    wrappedMethod(stateContext, scriptInterface);
    return;
  }
  this.GorillaChargeEnd(stateContext, scriptInterface);
}

@wrapMethod(CombatGadgetChargeEvents)
protected final func OnExitToCombatGadgetUnequip(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    wrappedMethod(stateContext, scriptInterface);
    return;
  }
  this.GorillaChargeEnd(stateContext, scriptInterface);
}

@wrapMethod(CombatGadgetChargeEvents)
protected final func OnExitToCombatGadgetEquip(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    wrappedMethod(stateContext, scriptInterface);
    return;
  }
  scriptInterface.PushAnimationEvent(n"CombatGadgetStopCharge");
  stateContext.SetPermanentBoolParameter(n"CancelAction", true, true);
  this.GorillaChargeEnd(stateContext, scriptInterface);
}

// The charged throw: the left hand's throw, along the charged throw's path and aim.
@wrapMethod(CombatGadgetChargedThrowEvents)
protected func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboGadgetSystem.Active(scriptInterface.executionOwner) {
    wrappedMethod(stateContext, scriptInterface);
    return;
  }
  this.SetBlackboardIntVariable(scriptInterface, GetAllBlackboardDefs().PlayerStateMachine.CombatGadget, 4);
  this.SetBlackbordThrowUnequip(scriptInterface, true);
  this.SetItemInLeftHand(scriptInterface, false);
  this.SetCombatGadgetAnimFeature(scriptInterface, true, false);
  scriptInterface.PushAnimationEvent(n"CombatGadgetQuickThrow");
  this.SetThrowableAnimFeatureOnGrenade(scriptInterface, 2, true);
  this.m_grenadeThrown = false;
  DefaultTransition.PlayRumble(scriptInterface, "heavy_pulse");
  let aimForward: Vector4;
  let aimPosition: Vector4;
  scriptInterface.GetTargetingSystem().GetDefaultCrosshairData(scriptInterface.executionOwner, aimPosition, aimForward);
  let transform = scriptInterface.executionOwner.GetWorldTransform();
  this.m_localAimForward = WorldTransform.TransformInvPoint(transform, scriptInterface.executionOwner.GetWorldPosition() + aimForward);
  this.m_localAimPosition = WorldTransform.TransformInvPoint(transform, aimPosition);
}

// After a pair's throw in a public safe zone the left gun comes back with a fresh safe timer and lowers about a second
// later while the right gun, fired during the throw, is still up. With one hand lowered and the other raised the arm
// graph plays the game's pistol lowered pose on the right hand for a moment (a large swing across the view). The left
// gun of a grip pair therefore lowers only once the right gun has lowered.
@wrapMethod(PublicSafeDecisions)
protected final const func EnterCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if this.IsLeftWeaponLogic() && GorillaAkimboGadget.IsPair(scriptInterface.executionOwner)
    && scriptInterface.localBlackboard.GetInt(GetAllBlackboardDefs().PlayerStateMachine.RightWeapon) != 6 {
    return false;
  }
  return wrappedMethod(stateContext, scriptInterface);
}
