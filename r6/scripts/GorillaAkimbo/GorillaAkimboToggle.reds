// Left gun key (setting akimboToggle): one key puts the left gun of a dual-wielded pair away and draws it again.
// The right gun stays drawn, held one-handed as while a body is carried (GorillaAkimboCarry.OneHanded). The left gun
// stays in its equipment slot, so the loadout is never changed and the magazine is the item's own, as it was.
// While the gun is away, every draw of that right gun (switching guns, holstering and drawing, a grenade, leaving a
// vehicle) leaves the left hand empty: TryGetSecondaryItemID, the game's choice of the left gun, skips it. The
// memory lasts until the key draws the gun again or the left slot holds another gun; it is not saved. The key works
// from the hands and slots alone, so it still puts the left gun away or draws it after a load.
module GorillaAkimbo

// Per right slot (0 to 2): the left gun the key put away, in the paired slot (3 to 5).
@addField(EquipmentSystemPlayerData)
public let gaToggleOff: array<ItemID>;

@addField(PlayerPuppet)
public let gaToggleListener: ref<GorillaAkimboToggleListener>;

public abstract class GorillaAkimboToggle {
  public static func Action() -> CName {
    return n"GorillaAkimboToggle";
  }

  public static func Enabled(owner: wref<GameObject>) -> Bool {
    return IsDefined(owner) && GorillaAkimboConfig.Get(owner.GetGame()).akimboToggle;
  }

  // The left gun is away (put there by the key) and this is the right gun drawn alone.
  public static func Holds(owner: wref<GameObject>, item: ItemID) -> Bool {
    let player = owner as PlayerPuppet;
    if !IsDefined(player) || !GorillaAkimboToggle.Enabled(player) {
      return false;
    }
    let data = EquipmentSystem.GetData(player);
    return IsDefined(data) && data.GaToggleOff(item);
  }

  // Which hint to show: 0 none, 1 "put away" (a pair is drawn), 2 "draw" (the left gun is away). Cheap checks only,
  // it runs with the other hints.
  public static func HintMode(owner: wref<GameObject>) -> Int32 {
    if !GorillaAkimboToggle.Enabled(owner) || GorillaAkimboCarry.Carrying(owner) {
      return 0;
    }
    let player = owner as PlayerPuppet;
    if !IsDefined(player) || VehicleComponent.IsMountedToVehicle(player.GetGame(), player) {
      return 0;
    }
    if GameObject.IsDualWielding(player) {
      return 1;
    }
    let right = GameObject.GetRightActiveWeapon(player);
    if IsDefined(right) && !IsDefined(GameObject.GetLeftActiveWeapon(player)) && GorillaAkimboToggle.Holds(player, right.GetItemID()) {
      return 2;
    }
    return 0;
  }

  // Something is going on that the key must not cut into: a reload, a draw, a grenade, a takedown, a vehicle, a carry.
  public static func Blocked(player: ref<PlayerPuppet>) -> Bool {
    let game = player.GetGame();
    if GorillaAkimboCarry.Carrying(player) || GorillaAkimboGadgetSystem.Active(player) || GorillaAkimboTopMagSystem.Busy(game)
      || VehicleComponent.IsMountedToVehicle(game, player) {
      return true;
    }
    let topMag = GorillaAkimboTopMagSystem.Get(game);
    if IsDefined(topMag) && (topMag.Pending(true) || topMag.Pending(false)) {
      return true;
    }
    let bb = player.GetPlayerStateMachineBlackboard();
    let defs = GetAllBlackboardDefs().PlayerStateMachine;
    let locomotion = bb.GetInt(defs.Locomotion);
    let upper = bb.GetInt(defs.UpperBody);
    return locomotion == EnumInt(gamePSMLocomotionStates.Sprint) || locomotion == EnumInt(gamePSMLocomotionStates.CrouchSprint)
      || bb.GetInt(defs.RightWeapon) == EnumInt(gamePSMRangedWeaponStates.Reload)
      || bb.GetInt(defs.LeftWeapon) == EnumInt(gamePSMRangedWeaponStates.Reload)
      || bb.GetInt(defs.Vision) != 0 || bb.GetInt(defs.Consumable) != 0 || bb.GetInt(defs.CombatGadget) != 0
      || bb.GetInt(defs.LeftHandCyberware) != 0 || bb.GetInt(defs.BodyCarrying) != 0 || bb.GetInt(defs.Takedown) != 0
      || bb.GetInt(defs.ShootState) >= EnumInt(gamePSMShootStates.ValentinosFrenzyInit)
      || upper == EnumInt(gamePSMUpperBodyStates.SwitchItems) || upper == EnumInt(gamePSMUpperBodyStates.SwitchCyberware)
      || upper == EnumInt(gamePSMUpperBodyStates.Reload) || upper == EnumInt(gamePSMUpperBodyStates.TemporaryUnequip)
      || upper == EnumInt(gamePSMUpperBodyStates.ForceEmptyHands);
  }

  public static func Press(player: ref<PlayerPuppet>) -> Void {
    if !GorillaAkimboToggle.Enabled(player) || GorillaAkimboToggle.Blocked(player) {
      return;
    }
    let data = EquipmentSystem.GetData(player);
    if IsDefined(data) {
      data.GaToggleLeft(player);
    }
  }
}

// The key's own listener on the player.
public class GorillaAkimboToggleListener extends IScriptable {
  public let m_owner: wref<PlayerPuppet>;

  protected cb func OnAction(action: ListenerAction, consumer: ListenerActionConsumer) -> Bool {
    if IsDefined(this.m_owner) && ListenerAction.IsButtonJustPressed(action) {
      GorillaAkimboToggle.Press(this.m_owner);
    }
    return false;
  }
}

@wrapMethod(PlayerPuppet)
protected cb func OnGameAttached() -> Bool {
  let result = wrappedMethod();
  this.gaToggleListener = new GorillaAkimboToggleListener();
  this.gaToggleListener.m_owner = this;
  this.RegisterInputListener(this.gaToggleListener, GorillaAkimboToggle.Action());
  return result;
}

@wrapMethod(PlayerPuppet)
protected cb func OnDetach() -> Bool {
  if IsDefined(this.gaToggleListener) {
    this.UnregisterInputListener(this.gaToggleListener);
    this.gaToggleListener = null;
  }
  return wrappedMethod();
}

// The right slot (0 to 2) the weapon is in, or -1.
@addMethod(EquipmentSystemPlayerData)
public final func GaToggleSlot(item: ItemID) -> Int32 {
  if !ItemID.IsValid(item) {
    return -1;
  }
  let slot = this.GetSlotIndex(item, gamedataEquipmentArea.Weapon);
  return slot >= 0 && slot <= 2 ? slot : -1;
}

// The key put this right gun's partner away, and that gun still sits in the paired slot.
@addMethod(EquipmentSystemPlayerData)
public final func GaToggleOff(right: ItemID) -> Bool {
  let slot = this.GaToggleSlot(right);
  if slot < 0 || ArraySize(this.gaToggleOff) <= slot {
    return false;
  }
  let left = this.gaToggleOff[slot];
  return ItemID.IsValid(left) && this.GetItemInEquipSlot(gamedataEquipmentArea.Weapon, EquipmentSystemPlayerData.GetOppositeWeaponSlotIndex(slot)) == left;
}

// 1: the pair is drawn, 2: the right gun is drawn alone and its partner can be drawn, 0: neither.
@addMethod(EquipmentSystemPlayerData)
public final func GaToggleState(player: ref<PlayerPuppet>) -> Int32 {
  let right = GameObject.GetRightActiveWeapon(player);
  if !IsDefined(right) || !right.IsRanged() || right.WeaponHasTag(n"Cyberware") {
    return 0;
  }
  let rightItem = right.GetItemID();
  let slot = this.GaToggleSlot(rightItem);
  if slot < 0 {
    return 0;
  }
  let leftItem = this.GetItemInEquipSlot(gamedataEquipmentArea.Weapon, EquipmentSystemPlayerData.GetOppositeWeaponSlotIndex(slot));
  if !ItemID.IsValid(leftItem) {
    return 0;
  }
  let ts = GameInstance.GetTransactionSystem(player.GetGame());
  let rightData = ts.GetItemData(player, rightItem);
  let leftData = ts.GetItemData(player, leftItem);
  if !ts.HasItem(player, leftItem) || !IsDefined(rightData) || !IsDefined(leftData) || !rightData.CanDualWield(player) || !leftData.CanDualWield(player) {
    return 0;
  }
  let left = GameObject.GetLeftActiveWeapon(player);
  if IsDefined(left) {
    return left.IsRanged() && left.GetItemID() == leftItem ? 1 : 0;
  }
  // Something else in the left hand (a grenade, a cyberware weapon): not ours to touch.
  return IsDefined(ts.GetItemInSlot(player, t"AttachmentSlots.WeaponLeft")) ? 0 : 2;
}

// Puts the left gun away, or draws it. The same two requests the game sends when a gun is added to or taken from
// the left slot with the right gun drawn.
@addMethod(EquipmentSystemPlayerData)
public final func GaToggleLeft(player: ref<PlayerPuppet>) -> Bool {
  let state = this.GaToggleState(player);
  if state == 0 {
    return false;
  }
  let rightItem = GameObject.GetRightActiveWeapon(player).GetItemID();
  let slot = this.GaToggleSlot(rightItem);
  let leftItem = this.GetItemInEquipSlot(gamedataEquipmentArea.Weapon, EquipmentSystemPlayerData.GetOppositeWeaponSlotIndex(slot));
  ArrayResize(this.gaToggleOff, 3);
  if state == 1 {
    this.gaToggleOff[slot] = leftItem;
    this.SetSlotActiveItem(EquipmentManipulationRequestSlot.Left, ItemID.None());
    this.SendPSMWeaponManipulationRequest(EquipmentManipulationRequestType.Unequip, EquipmentManipulationRequestSlot.Left, gameEquipAnimationType.Default);
    return true;
  }
  if !this.CheckWeaponAgainstGameplayRestrictions(leftItem, true, true) {
    return false;
  }
  this.gaToggleOff[slot] = ItemID.None();
  this.SetSlotActiveItem(EquipmentManipulationRequestSlot.Left, leftItem);
  this.SendPSMWeaponManipulationRequest(EquipmentManipulationRequestType.DualEquip, EquipmentManipulationRequestSlot.Left, gameEquipAnimationType.Default);
  return true;
}

// The game's choice of the left gun for a right gun: none while the key has put it away.
@wrapMethod(EquipmentSystemPlayerData)
public final func TryGetSecondaryItemID(item: ItemID, out secondaryItem: ItemID) -> Bool {
  if GorillaAkimboToggle.Enabled(this.m_owner) && this.GaToggleOff(item) {
    return false;
  }
  return wrappedMethod(item, secondaryItem);
}

// The same choice where the equipment refreshes the hands after a loadout change.
@wrapMethod(EquipmentSystemPlayerData)
public final func GetActiveSecondaryWeapon() -> ItemID {
  if GorillaAkimboToggle.Enabled(this.m_owner) && this.GaToggleOff(this.GetActiveWeapon()) {
    return ItemID.None();
  }
  return wrappedMethod();
}

// A left gun drawn any other way (the inventory, another mod) ends the memory: a pair is drawn.
@wrapMethod(EquipCycleEvents)
protected func OnExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  if !this.IsLeftHandLogic(this.stateMachineInstanceData) {
    return;
  }
  let owner = scriptInterface.executionOwner as PlayerPuppet;
  let left = GameObject.GetLeftActiveWeapon(owner);
  let data = IsDefined(owner) ? EquipmentSystem.GetData(owner) : null;
  if IsDefined(left) && IsDefined(data) {
    let i = 0;
    while i < ArraySize(data.gaToggleOff) {
      if data.gaToggleOff[i] == left.GetItemID() {
        data.gaToggleOff[i] = ItemID.None();
      }
      i += 1;
    }
  }
}
