// Driver combat (car and bike): the game lets V draw only guns tagged DriverCombatRangedWeapon (pistols, revolvers,
// SMGs) and only in the right hand. With Gorilla Arms, every ranged firearm is let through the same checks, one gun
// at a time. A pair keeps its right gun: the game already puts the left one away in driver combat and brings it back
// on leaving the vehicle.
module GorillaAkimbo

public abstract class GorillaAkimboVehicle {
  public static func InDriverCombat(owner: ref<GameObject>) -> Bool {
    return StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"DriverCombatFirearms")
      || StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"DriverCombatBikeWeapons");
  }

  public static func Active(owner: ref<GameObject>) -> Bool {
    return IsDefined(owner) && GorillaAkimboVehicle.InDriverCombat(owner) && HasGorillaArms(owner) && GorillaAkimboConfig.Get(owner.GetGame()).vehicleGuns;
  }

  // Firearm types let through: the driver pose does not depend on the weapon (anim weaponType -1). Heavy-slot guns
  // (most HMGs), vehicle weapons, throwables and melee stay out.
  public static func Type(type: gamedataItemType) -> Bool {
    return Equals(type, gamedataItemType.Wea_Handgun) || Equals(type, gamedataItemType.Wea_Revolver) || Equals(type, gamedataItemType.Wea_SubmachineGun)
      || Equals(type, gamedataItemType.Wea_AssaultRifle) || Equals(type, gamedataItemType.Wea_Rifle) || Equals(type, gamedataItemType.Wea_PrecisionRifle)
      || Equals(type, gamedataItemType.Wea_SniperRifle) || Equals(type, gamedataItemType.Wea_Shotgun) || Equals(type, gamedataItemType.Wea_ShotgunDual)
      || Equals(type, gamedataItemType.Wea_LightMachineGun) || Equals(type, gamedataItemType.Wea_HeavyMachineGun) || Equals(type, gamedataItemType.Wea_GrenadeLauncher);
  }

  // A ranged firearm V may hold in the right hand in driver combat with Gorilla Arms.
  public static func Allows(owner: ref<GameObject>, item: ItemID) -> Bool {
    if !GorillaAkimboVehicle.Active(owner) || !ItemID.IsValid(item) {
      return false;
    }
    let record = TweakDBInterface.GetItemRecord(ItemID.GetTDBID(item));
    return record.TagsContains(n"RangedWeapon") && Equals(record.EquipArea().Type(), gamedataEquipmentArea.Weapon)
      && GorillaAkimboVehicle.Type(record.ItemType().Type())
      && !StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"NoWeapons")
      && !StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"Melee")
      && !StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"Fists");
  }
}

// The equip check: the game's tag test (DriverCombatRangedWeapon / DriverCombatBikeWeapon) is replaced for these guns.
@wrapMethod(EquipmentSystemPlayerData)
public final func CheckWeaponAgainstGameplayRestrictions(weaponItem: ItemID, opt suppressDriverWarnings: Bool, opt isLeftWeapon: Bool) -> Bool {
  if !isLeftWeapon && GorillaAkimboVehicle.Allows(this.m_owner, weaponItem) {
    return true;
  }
  return wrappedMethod(weaponItem, suppressDriverWarnings, isLeftWeapon);
}

// The gun the vehicle state draws on entering combat: the game picks by tag, so when it finds none the last used
// mod gun, then the first one in the loadout, is offered.
@wrapMethod(EquipmentSystemPlayerData)
public final func GetLastUsedOrFirstAvailableDriverCombatWeapon(driverCombatWeaponTag: CName) -> ItemID {
  let item = wrappedMethod(driverCombatWeaponTag);
  if ItemID.IsValid(item) || !GorillaAkimboVehicle.InDriverCombat(this.m_owner) {
    return item;
  }
  let last = this.FindItemInEquipArea(this.GetLastUsedItemID(ELastUsed.Weapon), gamedataEquipmentArea.WeaponWheel);
  if GorillaAkimboVehicle.Allows(this.m_owner, last) {
    return last;
  }
  let area = gamedataEquipmentArea.Weapon;
  let count = this.GetNumberOfSlots(area);
  let i = 0;
  while i < count {
    let id = this.GetItemInEquipSlot(area, i);
    if GorillaAkimboVehicle.Allows(this.m_owner, id) {
      return id;
    }
    i += 1;
  }
  return item;
}

// Switching guns: the next gun on the weapon wheel is picked by tag; mod-allowed guns count too.
@wrapMethod(EquipmentSystemPlayerData)
public final const func GetNextWeaponWheelItem() -> ItemID {
  let owner = this.m_owner;
  if !GorillaAkimboVehicle.Active(owner) {
    return wrappedMethod();
  }
  let area = gamedataEquipmentArea.WeaponWheel;
  let count = this.GetNumberOfSlots(area);
  let start = this.m_equipment.equipAreas[this.GetEquipAreaIndex(area)].activeIndex + 1;
  let tag = StatusEffectSystem.ObjectHasStatusEffectWithTag(owner, n"DriverCombatFirearms") ? n"DriverCombatRangedWeapon" : n"DriverCombatBikeWeapon";
  let i = 0;
  while i < count {
    let id = this.GetItemInEquipSlot(area, (start + i) % count);
    if ItemID.IsValid(id) && (TweakDBInterface.GetItemRecord(ItemID.GetTDBID(id)).TagsContains(tag) || GorillaAkimboVehicle.Allows(owner, id)) {
      return id;
    }
    i += 1;
  }
  return wrappedMethod();
}

// The quick-slot wheel: slots the game blanks for lacking the driver tag are filled back in for allowed guns.
@wrapMethod(QuickSlotsManager)
public final const func GetEquipAreaCommands(const equipArea: gamedataEquipmentArea, const opt allowedItemTypes: [gamedataItemType], const opt allowedTag: CName) -> [QuickSlotCommand] {
  let result = wrappedMethod(equipArea, allowedItemTypes, allowedTag);
  if NotEquals(equipArea, gamedataEquipmentArea.WeaponWheel) || !GorillaAkimboVehicle.Active(this.m_Player) {
    return result;
  }
  let none: array<gamedataItemType>;
  let all = wrappedMethod(equipArea, none, n"RangedWeapon");
  let data = EquipmentSystem.GetData(this.m_Player);
  let i = 0;
  while i < ArraySize(result) && i < ArraySize(all) {
    if !ItemID.IsValid(result[i].ItemId) && GorillaAkimboVehicle.Allows(this.m_Player, data.GetItemInEquipSlot(equipArea, i)) {
      result[i] = all[i];
    }
    i += 1;
  }
  return result;
}
