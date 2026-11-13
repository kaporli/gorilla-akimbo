// Carrying a body: the game keeps one pistol or revolver in the right hand (with the perk that allows shooting while
// carrying) and puts a left gun away. With Gorilla Arms, the guns the mod lets V dual-wield are held the same way, in
// the right hand with their one-handed clips.
module GorillaAkimbo

public abstract class GorillaAkimboCarry {
  // V is picking up, carrying or putting down a body.
  public static func Carrying(owner: ref<GameObject>) -> Bool {
    let player = owner as PlayerPuppet;
    return IsDefined(player) && player.GetPlayerStateMachineBlackboard().GetInt(GetAllBlackboardDefs().PlayerStateMachine.BodyCarrying) > 0;
  }

  // A gun the game holds two-handed that V can dual-wield right now (Gorilla Arms, the settings, Double Trouble).
  public static func Allows(owner: ref<GameObject>, item: ItemID) -> Bool {
    if !IsDefined(owner) || !ItemID.IsValid(item) || !GorillaAkimboGuns.NeedsArms(RPGManager.GetItemType(item)) {
      return false;
    }
    let data = GameInstance.GetTransactionSystem(owner.GetGame()).GetItemData(owner, item);
    return IsDefined(data) && data.HasTag(GorillaAkimboTag()) && data.CanDualWield(owner);
  }

  // Weapon switching blocked by something other than the carry itself.
  public static func SwitchBlocked(player: ref<PlayerPuppet>) -> Bool {
    for effect in StatusEffectHelper.GetAppliedEffects(player) {
      let record = effect.GetRecord();
      let tags = record.GameplayTags();
      if NotEquals(record.GetID(), t"GameplayRestriction.BodyCarryingGeneric") && ArrayContains(tags, n"FirearmsNoSwitch") {
        return true;
      }
    }
    return false;
  }

  // A grip weapon held alone in the right hand while a body is carried.
  public static func OneHanded(owner: ref<GameObject>, item: ItemID) -> Bool {
    if !IsDefined(owner) || !IsGripWeaponType(RPGManager.GetItemType(item)) || !GorillaAkimboCarry.Carrying(owner) {
      return false;
    }
    let ts = GameInstance.GetTransactionSystem(owner.GetGame());
    let right = ts.GetItemInSlot(owner, t"AttachmentSlots.WeaponRight");
    return IsDefined(right) && Equals(right.GetItemID(), item) && !IsDefined(ts.GetItemInSlot(owner, t"AttachmentSlots.WeaponLeft"))
      && GorillaAkimboCarry.Allows(owner, item);
  }

  // A grip weapon held in one hand: dual-wielded, or alone while a body is carried.
  public static func OneHand(owner: ref<GameObject>, item: ItemID) -> Bool {
    return GameObject.IsDualWielding(owner) || GorillaAkimboCarry.OneHanded(owner, item);
  }
}

// The gun the game draws while a body is carried: the last used one when V can hold it, otherwise the game's pick,
// otherwise the first such gun in the loadout.
@wrapMethod(EquipmentSystemPlayerData)
public final func GetLastUsedOrFirstAvailableOneHandedRangedWeapon() -> ItemID {
  let owner = this.m_owner;
  if !GorillaAkimboCarry.Carrying(owner) {
    return wrappedMethod();
  }
  let last = this.FindItemInEquipArea(this.GetLastUsedItemID(ELastUsed.Ranged), gamedataEquipmentArea.WeaponWheel);
  if GorillaAkimboCarry.Allows(owner, last) {
    return last;
  }
  let item = wrappedMethod();
  if ItemID.IsValid(item) {
    return item;
  }
  let area = gamedataEquipmentArea.Weapon;
  let count = this.GetNumberOfSlots(area);
  let i = 0;
  while i < count {
    let id = this.GetItemInEquipSlot(area, i);
    if GorillaAkimboCarry.Allows(owner, id) {
      return id;
    }
    i += 1;
  }
  return item;
}

// The game's carry checks accept only pistols and revolvers.
@wrapMethod(CarriedObjectTransition)
protected final func CanEquipFirearm(owner: ref<GameObject>, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if wrappedMethod(owner, stateContext, scriptInterface) {
    return true;
  }
  if this.IsInEmptyHandsState(stateContext) {
    return false;
  }
  let system = GameInstance.GetScriptableSystemsContainer(owner.GetGame()).Get(n"EquipmentSystem") as EquipmentSystem;
  let data = IsDefined(system) ? system.GetPlayerData(owner) : null;
  return IsDefined(data) && GorillaAkimboCarry.Allows(owner, data.GetLastUsedOrFirstAvailableOneHandedRangedWeapon());
}

// Drawing such a gun in the right hand while a body is carried (the game allows only guns tagged one-handed).
@wrapMethod(EquipmentSystemPlayerData)
public final func CheckWeaponAgainstGameplayRestrictions(weaponItem: ItemID, opt suppressDriverWarnings: Bool, opt isLeftWeapon: Bool) -> Bool {
  let owner = this.m_owner;
  if !isLeftWeapon && GorillaAkimboCarry.Carrying(owner) && GorillaAkimboCarry.Allows(owner, weaponItem)
    && !StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"NoWeapons")
    && !StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"Melee")
    && !StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"Fists")
    && !StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"DriverCombatFirearms")
    && !StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"DriverCombatBikeWeapons") {
    return true;
  }
  // Switching to the next weapon includes fists and melee; with Gorilla Arms only guns come up during the carry.
  if !isLeftWeapon && GorillaAkimboCarry.Carrying(owner) && HasGorillaArms(owner) && ItemID.IsValid(weaponItem)
    && !TweakDBInterface.GetItemRecord(ItemID.GetTDBID(weaponItem)).TagsContains(n"RangedWeapon") {
    return false;
  }
  return wrappedMethod(weaponItem, suppressDriverWarnings, isLeftWeapon);
}

// The body is put down: a grip weapon still in the right hand goes back to its own two-handed animations.
@wrapMethod(CarriedObjectEvents)
protected final func CleanUpCarryStateMachine(state: ECarryState, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(state, stateContext, scriptInterface);
  GorillaAkimboHands.Send(scriptInterface, false, 2, 0.3);
  GorillaAkimboBody.Refresh(scriptInterface.executionOwner);
}

// The mouse wheel while a body is carried: the game blocks weapon switching then (BodyCarryingGeneric). With Gorilla
// Arms it sends the game's next or previous weapon request; the equipment checks above decide which gun comes up.
@addField(PlayerPuppet)
private let gaCarryCycleTime: Float;

@wrapMethod(CarryEvents)
protected final func OnUpdate(timeDelta: Float, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(timeDelta, stateContext, scriptInterface);
  let next = scriptInterface.IsActionJustPressed(n"NextWeapon");
  if !next && !scriptInterface.IsActionJustPressed(n"PreviousWeapon") {
    return;
  }
  let player = scriptInterface.executionOwner as PlayerPuppet;
  if !IsDefined(player) || !HasGorillaArms(player) || !DefaultTransition.HasRightWeaponEquipped(scriptInterface)
    || GorillaAkimboCarry.SwitchBlocked(player) || StatusEffectSystem.ObjectHasStatusEffectWithTag(player, n"NoCombat") {
    return;
  }
  let now = EngineTime.ToFloat(GameInstance.GetEngineTime(player.GetGame()));
  if now - player.gaCarryCycleTime < 0.5 {
    return;
  }
  player.gaCarryCycleTime = now;
  this.SendEquipmentSystemWeaponManipulationRequest(scriptInterface, next ? EquipmentManipulationAction.CycleNextWeaponWheelItem : EquipmentManipulationAction.CyclePreviousWeaponWheelItem);
}
