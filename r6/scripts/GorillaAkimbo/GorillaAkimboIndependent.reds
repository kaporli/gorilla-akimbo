// Independent firing (setting): while dual-wielding, each fire button fires one gun and aiming moves to its own key
// (GorillaAkimboAim, r6/input/GorillaAkimbo.xml). Mouse: left button the left gun, right button the right gun.
// Controller: left trigger the left gun, right trigger the right gun. The game reads the fire button (RangedAttack) in
// many weapon states; each of those reads the hand's own button here instead, only while independent firing is on and
// two guns are drawn. Everything else runs the game's code.
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

  // From the last values of both buttons, the one of this hand's button (the fire button when not active).
  public static func HandValue(owner: wref<GameObject>, left: Bool, ranged: Float, aim: Float) -> Float {
    if GorillaAkimboIndependent.Active(owner) && Equals(GorillaAkimboIndependent.FireAction(left, owner.GetGame()), n"CameraAim") {
      return aim;
    }
    return ranged;
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

@wrapMethod(WeaponTransition)
protected final const func IsSemiAutoAction(weaponObject: ref<WeaponObject>, const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(weaponObject, stateContext, scriptInterface);
  }
  let fire = GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame());
  if !this.ShouldShoot(scriptInterface) {
    return false;
  }
  if StatusEffectSystem.ObjectHasStatusEffect(scriptInterface.executionOwner, t"BaseStatusEffect.ValentinosFrenzySE") {
    return true;
  }
  if scriptInterface.GetActionValue(fire) > 0.0 {
    if this.IsInVisionModeActiveState(stateContext, scriptInterface) {
      return true;
    }
    if this.CanHoldToShoot(scriptInterface)
      && EngineTime.ToDouble(GameInstance.GetSimTime(scriptInterface.GetGame())) > this.GetLastShotTime(stateContext) {
      return true;
    }
  }
  return scriptInterface.IsActionJustPressed(fire);
}

@wrapMethod(WeaponTransition)
protected final const func IsFullAutoAction(weaponObject: ref<WeaponObject>, const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(weaponObject, stateContext, scriptInterface);
  }
  if !this.ShouldShoot(scriptInterface) {
    return false;
  }
  if StatusEffectSystem.ObjectHasStatusEffect(scriptInterface.executionOwner, t"BaseStatusEffect.ValentinosFrenzySE") {
    return true;
  }
  return scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) > 0.0;
}

// Semi-auto and full-auto states only check their conditions while the fire button is down, from an input listener:
// they also listen to the right mouse button (left trigger) and get the value of the hand's own button.
@addField(SemiAutoDecisions)
private let m_gorillaOwner: wref<GameObject>;

@addField(SemiAutoDecisions)
private let m_gorillaRanged: Float;

@addField(SemiAutoDecisions)
private let m_gorillaAim: Float;

@wrapMethod(SemiAutoDecisions)
protected final func OnAttach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  this.m_gorillaOwner = scriptInterface.executionOwner;
  scriptInterface.executionOwner.RegisterInputListener(this, n"CameraAim");
  this.OnRangeAttackInput(n"CameraAim", scriptInterface.GetActionValue(n"CameraAim"));
}

@wrapMethod(SemiAutoDecisions)
protected final func OnRangeAttackInput(input: CName, value: Float) -> Void {
  if Equals(input, n"CameraAim") {
    this.m_gorillaAim = value;
  } else {
    this.m_gorillaRanged = value;
  }
  if GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    wrappedMethod(n"RangedAttack", GorillaAkimboIndependent.HandValue(this.m_gorillaOwner, this.IsLeftWeaponLogic(), this.m_gorillaRanged, this.m_gorillaAim));
  } else {
    if !Equals(input, n"CameraAim") {
      wrappedMethod(input, value);
    }
  }
}

@addField(FullAutoDecisions)
private let m_gorillaOwner: wref<GameObject>;

@addField(FullAutoDecisions)
private let m_gorillaRanged: Float;

@addField(FullAutoDecisions)
private let m_gorillaAim: Float;

@wrapMethod(FullAutoDecisions)
protected final func OnAttach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  this.m_gorillaOwner = scriptInterface.executionOwner;
  scriptInterface.executionOwner.RegisterInputListener(this, n"CameraAim");
  this.OnRangeAttackInput(n"CameraAim", scriptInterface.GetActionValue(n"CameraAim"));
}

@wrapMethod(FullAutoDecisions)
protected final func OnRangeAttackInput(input: CName, value: Float) -> Void {
  if Equals(input, n"CameraAim") {
    this.m_gorillaAim = value;
  } else {
    this.m_gorillaRanged = value;
  }
  if GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    wrappedMethod(n"RangedAttack", GorillaAkimboIndependent.HandValue(this.m_gorillaOwner, this.IsLeftWeaponLogic(), this.m_gorillaRanged, this.m_gorillaAim));
  } else {
    if !Equals(input, n"CameraAim") {
      wrappedMethod(input, value);
    }
  }
}

@wrapMethod(FullAutoDecisions)
protected final const func ToReady(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  let isFireDelay = stateContext.GetBoolParameter(this.GetIsDelayFireName(), true);
  let timeRemaining = stateContext.GetFloatParameter(this.GetCycleTimeRemainingName(), true);
  return (!isFireDelay || timeRemaining <= 0.0)
    && scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) <= 0.0;
}

// A full-auto gun stops when its own button is let go.
@wrapMethod(CycleRoundEvents)
protected final func OnUpdate(timeDelta: Float, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    wrappedMethod(timeDelta, stateContext, scriptInterface);
    return;
  }
  let weapon = this.GetWeaponObject(scriptInterface);
  this.ShowAttackPreview(true, weapon, scriptInterface, stateContext);
  if this.m_blockAimDuration > 0.0 {
    if !this.m_hasBlockedAiming && this.m_blockAimStart < this.GetInStateTime() {
      this.BlockAimingForTime(stateContext, scriptInterface, this.m_blockAimDuration);
      this.m_hasBlockedAiming = true;
    }
  }
  this.ShootingSequenceUpdateCycleTime(timeDelta, stateContext, scriptInterface);
  this.UpdateReloadInputBuffer(stateContext, scriptInterface);
  if scriptInterface.IsTriggerModeActive(gamedataTriggerMode.FullAuto) {
    if scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) <= 0.0
      || weapon.IsMagazineEmpty() {
      scriptInterface.TEMP_WeaponStopFiring();
    }
  }
}

@wrapMethod(CycleTriggerModeDecisions)
protected final const func ToCharge(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  if !scriptInterface.IsTriggerModeActive(gamedataTriggerMode.Charge) {
    return false;
  }
  if this.GetInStateTime() < stateContext.GetConditionFloat(n"CycleTriggerModeStatCycleTime") {
    return false;
  }
  let weapon = this.GetWeaponObject(scriptInterface);
  return !weapon.IsMagazineEmpty()
    && scriptInterface.GetStatPoolsSystem().GetStatPoolValue(Cast<StatsObjectID>(weapon.GetEntityID()), gamedataStatPoolType.WeaponCharge) <= this.GetWeaponChargeMinValue(scriptInterface)
    && scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) > 0.0;
}

// An empty gun reloads when its own button is pressed, and dry-fires on its own button.
@wrapMethod(NoAmmoDecisions)
protected final const func ToReload(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  let shootState = scriptInterface.localBlackboard.GetInt(GetAllBlackboardDefs().PlayerStateMachine.ShootState);
  let weaponObject = this.GetWeaponObject(scriptInterface);
  if !WeaponObject.CanReload(weaponObject) {
    return false;
  }
  if shootState == 4 || shootState == 5 || shootState == 6 {
    return false;
  }
  if !scriptInterface.HasStatFlag(gamedataStatType.CanWeaponReloadWhileSprinting) && scriptInterface.localBlackboard.GetInt(GetAllBlackboardDefs().PlayerStateMachine.Locomotion) == 2 {
    return false;
  }
  if !scriptInterface.HasStatFlag(gamedataStatType.CanWeaponReloadWhileVaulting) && stateContext.IsStateActive(n"Locomotion", n"vault") {
    return false;
  }
  if !scriptInterface.HasStatFlag(gamedataStatType.CanWeaponReloadWhileSliding) && stateContext.IsStateActive(n"Locomotion", n"slide") {
    return false;
  }
  if scriptInterface.IsActionJustPressed(n"QuickMelee") {
    return false;
  }
  if scriptInterface.IsActionJustPressed(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) {
    return true;
  }
  if Equals(weaponObject.GetWeaponRecord().ItemType().Type(), gamedataItemType.Wea_SniperRifle) && stateContext.IsStateActive(n"UpperBody", n"aimingState") {
    return false;
  }
  return this.GetInStateTime() > this.GetStaticFloatParameterDefault("timeToAutoReload", 0.30);
}

@wrapMethod(NoAmmoEvents)
protected final func OnUpdate(timeDelta: Float, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    wrappedMethod(timeDelta, stateContext, scriptInterface);
    return;
  }
  if scriptInterface.IsActionJustPressed(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) {
    let dryFireEvent = new AudioEvent();
    dryFireEvent.eventName = n"dry_fire";
    this.GetWeaponObject(scriptInterface).QueueEvent(dryFireEvent);
  }
}

// A shell-by-shell reload is cut short by the gun's own button, in either hand.
@wrapMethod(ReloadDecisions)
protected final const func ExitCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  if this.IsReloadDurationComplete(stateContext, scriptInterface) {
    if stateContext.GetBoolParameter(this.GetFinishedReload(), true) {
      return true;
    }
  }
  if stateContext.IsStateMachineActive(n"Consumable") || stateContext.IsStateMachineActive(n"CombatGadget") || stateContext.GetBoolParameter(n"UnequipToGadgetOrConsumable", true) {
    return true;
  }
  if stateContext.GetBoolParameter(n"TryInterruptReload") && !this.IsReloadUninterruptible(stateContext, scriptInterface) {
    return true;
  }
  if scriptInterface.IsActionJustPressed(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame()))
    && Cast<Int32>(scriptInterface.GetStatsSystem().GetStatValue(Cast<StatsObjectID>(scriptInterface.ownerEntityID), gamedataStatType.ReloadAmount)) > 0 {
    if !this.GetWeaponObject(scriptInterface).IsMagazineEmpty() && !this.IsReloadUninterruptible(stateContext, scriptInterface) {
      return true;
    }
  }
  if scriptInterface.IsActionJustPressed(n"QuickMelee") && this.CanQuickMelee(stateContext, scriptInterface) {
    return true;
  }
  if !scriptInterface.HasStatFlag(gamedataStatType.CanWeaponReloadWhileVaulting) && stateContext.IsStateActive(n"Locomotion", n"vault") {
    return true;
  }
  return false;
}

// Charge weapons (tech guns while aiming): charge on the gun's own button and fire when it is let go.
@addField(ChargeDecisions)
private let m_gorillaOwner: wref<GameObject>;

@addField(ChargeDecisions)
private let m_gorillaRanged: Float;

@addField(ChargeDecisions)
private let m_gorillaAim: Float;

@wrapMethod(ChargeDecisions)
protected final func OnAttach(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  this.m_gorillaOwner = scriptInterface.executionOwner;
  this.m_gorillaRanged = scriptInterface.GetActionValue(n"RangedAttack");
  this.m_gorillaAim = scriptInterface.GetActionValue(n"CameraAim");
  scriptInterface.executionOwner.RegisterInputListener(this, n"CameraAim");
}

@wrapMethod(ChargeDecisions)
protected cb func OnAction(action: ListenerAction, consumer: ListenerActionConsumer) -> Bool {
  if Equals(ListenerAction.GetName(action), n"CameraAim") {
    this.m_gorillaAim = ListenerAction.GetValue(action);
  } else {
    this.m_gorillaRanged = ListenerAction.GetValue(action);
  }
  if !GorillaAkimboIndependent.Active(this.m_gorillaOwner) {
    if Equals(ListenerAction.GetName(action), n"CameraAim") {
      return true;
    }
    return wrappedMethod(action, consumer);
  }
  this.UpdateRangedAttackInput(GorillaAkimboIndependent.HandValue(this.m_gorillaOwner, this.IsLeftWeaponLogic(), this.m_gorillaRanged, this.m_gorillaAim));
  this.UpdateOnEnterConditionEnabled();
  return true;
}

@wrapMethod(ChargeDecisions)
protected final const func EnterCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  let actionPressCount = scriptInterface.GetActionPressCount(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame()));
  let lastChargePressCount = stateContext.GetPermanentIntParameter(this.GetLastChargePressCount());
  if lastChargePressCount.valid && lastChargePressCount.value == Cast<Int32>(actionPressCount) {
    if !this.CanHoldToShoot(scriptInterface) {
      this.EnableOnEnterCondition(false);
      return false;
    }
    if EngineTime.ToDouble(GameInstance.GetSimTime(scriptInterface.GetGame())) < this.GetLastShotTime(stateContext) {
      return false;
    }
  }
  let weapon = this.GetWeaponObject(scriptInterface);
  return !weapon.IsMagazineEmpty()
    && scriptInterface.GetStatPoolsSystem().GetStatPoolValue(Cast<StatsObjectID>(weapon.GetEntityID()), gamedataStatPoolType.WeaponCharge) <= this.GetWeaponChargeMinValue(scriptInterface);
}

@wrapMethod(ChargeDecisions)
protected final const func ToShoot(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  let weapon = this.GetWeaponObject(scriptInterface);
  let statsSystem = scriptInterface.GetStatsSystem();
  let weaponID = Cast<StatsObjectID>(weapon.GetEntityID());
  let fireWhenReady = statsSystem.GetStatValue(weaponID, gamedataStatType.ChargeShouldFireWhenReady) > 0.0;
  if fireWhenReady && WeaponObject.GetWeaponChargeNormalized(weapon) >= statsSystem.GetStatValue(weaponID, gamedataStatType.ChargeReadyPercentage) {
    return true;
  }
  return scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) <= 0.0;
}

@wrapMethod(ChargeDecisions)
protected final const func ToChargeReady(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  let weapon = this.GetWeaponObject(scriptInterface);
  let statsSystem = scriptInterface.GetStatsSystem();
  let weaponID = Cast<StatsObjectID>(weapon.GetEntityID());
  let fireWhenReady = statsSystem.GetStatValue(weaponID, gamedataStatType.ChargeShouldFireWhenReady) > 0.0;
  return !fireWhenReady && WeaponObject.GetWeaponChargeNormalized(weapon) >= statsSystem.GetStatValue(weaponID, gamedataStatType.ChargeReadyPercentage)
    && scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) > 0.0;
}

@wrapMethod(ChargeEvents)
protected final func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  if GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    let fire = GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame());
    stateContext.SetPermanentIntParameter(this.GetLastChargePressCount(), Cast<Int32>(scriptInterface.GetActionPressCount(fire)), true);
  }
}

@wrapMethod(ChargeReadyDecisions)
protected final const func ToShoot(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  if StatusEffectSystem.ObjectHasStatusEffectWithTag(scriptInterface.executionOwner, n"PerfectChargeIndication") {
    return false;
  }
  return scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) <= 0.0;
}

@wrapMethod(ChargeReadyDecisions)
protected final const func ToChargeMax(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  if StatusEffectSystem.ObjectHasStatusEffectWithTag(scriptInterface.executionOwner, n"PerfectChargeIndication")
    && scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) <= 0.0 {
    return true;
  }
  let weaponID = this.GetWeaponObject(scriptInterface).GetEntityID();
  return scriptInterface.GetStatPoolsSystem().GetStatPoolValue(Cast<StatsObjectID>(weaponID), gamedataStatPoolType.WeaponCharge) >= this.GetMaxChargeThreshold(scriptInterface);
}

@wrapMethod(ChargeMaxDecisions)
protected final const func ToShoot(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  let released = scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) <= 0.0;
  let statsSystem = scriptInterface.GetStatsSystem();
  let weaponID = Cast<StatsObjectID>(this.GetWeaponObject(scriptInterface).GetEntityID());
  if scriptInterface.HasStatFlag(gamedataStatType.CanControlFullyChargedWeapon) && !this.CanHoldToShoot(scriptInterface) {
    if statsSystem.GetStatValue(weaponID, gamedataStatType.FullAutoOnFullCharge) == 0.0 {
      return released;
    }
  }
  return this.GetInStateTime() >= statsSystem.GetStatValue(weaponID, gamedataStatType.ChargeMaxTimeInChargedState) || released;
}

@wrapMethod(DischargeDecisions)
protected final const func EnterCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if !GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  let weaponID = Cast<StatsObjectID>(this.GetWeaponObject(scriptInterface).GetEntityID());
  let charge = scriptInterface.GetStatPoolsSystem().GetStatPoolValue(weaponID, gamedataStatPoolType.WeaponCharge);
  return charge < scriptInterface.GetStatsSystem().GetStatValue(weaponID, gamedataStatType.ChargeReadyPercentage)
    && scriptInterface.GetActionValue(GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame())) <= 0.0;
}

// Lowered guns in public places come up on either fire button.
@wrapMethod(PublicSafeDecisions)
protected final const func EnterCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if GorillaAkimboIndependent.Active(scriptInterface.executionOwner) && scriptInterface.GetActionValue(n"CameraAim") > 0.0 {
    return false;
  }
  return wrappedMethod(stateContext, scriptInterface);
}

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
