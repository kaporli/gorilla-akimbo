// Inventory screen: the game's paperdoll has a two-gun pose only for pistols and revolvers (handgun_dual_wield_idle,
// picked by the Wea_Handgun wrapper and has_left_weapon). A pair of the mod's guns gets the Wea_Handgun wrapper on the
// paperdoll puppet so it uses that pose instead of the one-gun pose of its type.
module GorillaAkimbo

@addField(NPCPuppet)
private let gaPaperdollPistolPose: Bool;

public abstract class GorillaAkimboPaperdoll {
  public static func Refresh(puppet: ref<NPCPuppet>) -> Void {
    let ts = GameInstance.GetTransactionSystem(puppet.GetGame());
    let right = ts.GetItemInSlot(puppet, t"AttachmentSlots.WeaponRight");
    let left = ts.GetItemInSlot(puppet, t"AttachmentSlots.WeaponLeft");
    let pair = IsDefined(right) && IsDefined(left) && (IsGripWeaponType(RPGManager.GetItemType(right.GetItemID()))
      || IsGripWeaponType(RPGManager.GetItemType(left.GetItemID())));
    if pair {
      AnimationControllerComponent.SetAnimWrapperWeight(puppet, n"Wea_Handgun", 1.0);
      puppet.gaPaperdollPistolPose = true;
    } else {
      if puppet.gaPaperdollPistolPose {
        let pistol = IsDefined(right) && Equals(AIActionHelper.GetAnimWrapperNameBasedOnItemID(right.GetItemID()), n"Wea_Handgun");
        AnimationControllerComponent.SetAnimWrapperWeight(puppet, n"Wea_Handgun", pistol ? 1.0 : 0.0);
        puppet.gaPaperdollPistolPose = false;
      }
    }
  }
}

@wrapMethod(NPCPuppet)
protected cb func OnItemAddedToSlot(evt: ref<ItemAddedToSlot>) -> Bool {
  let result = wrappedMethod(evt);
  if this.IsPaperdoll() {
    GorillaAkimboPaperdoll.Refresh(this);
  }
  return result;
}

@wrapMethod(NPCPuppet)
protected cb func OnItemRemovedFromSlot(evt: ref<ItemRemovedFromSlot>) -> Bool {
  let result = wrappedMethod(evt);
  if this.IsPaperdoll() {
    GorillaAkimboPaperdoll.Refresh(this);
  }
  return result;
}
