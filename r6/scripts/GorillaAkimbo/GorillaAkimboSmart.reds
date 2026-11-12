// Smart Link on both guns. The game's smart targeting runs for the right-hand gun only: its bullets are launched at
// the targets Smart Link locks, the left gun's are launched untargeted. With the setting on, bullets of a dual-wielded
// Smart gun in the left hand are launched at the right gun's locked targets the same way.
module GorillaAkimbo

// The targets the right gun's Smart Link has locked, read from the reticle data when a left bullet is launched.
public class GorillaAkimboSmartTargets extends ScriptableSystem {
  private let m_next: Int32;

  // The next locked target, in turn, with a Smart gun in the right hand; null when none.
  public func Next(player: ref<GameObject>) -> ref<GameObject> {
    let right = GameInstance.GetTransactionSystem(player.GetGame()).GetItemInSlot(player, t"AttachmentSlots.WeaponRight") as WeaponObject;
    if !GorillaAkimboSmart.IsSmart(right) {
      return null;
    }
    let board = GameInstance.GetBlackboardSystem(this.GetGameInstance()).Get(GetAllBlackboardDefs().UI_ActiveWeaponData);
    let params = FromVariant<ref<smartGunUIParameters>>(board.GetVariant(GetAllBlackboardDefs().UI_ActiveWeaponData.SmartGunParams));
    if !IsDefined(params) || !params.hasRequiredCyberware {
      return null;
    }
    let locked: array<EntityID>;
    for target in params.targets {
      if Equals(target.state, gamesmartGunTargetState.Locked) {
        ArrayPush(locked, target.entityID);
      }
    }
    let count = ArraySize(locked);
    let i = 0;
    while i < count {
      this.m_next = (this.m_next + 1) % count;
      let target = GameInstance.FindEntityByID(this.GetGameInstance(), locked[this.m_next]) as GameObject;
      if IsDefined(target) && !target.IsDead() {
        return target;
      }
      i += 1;
    }
    return null;
  }

  public static func Get(game: GameInstance) -> ref<GorillaAkimboSmartTargets> {
    return GameInstance.GetScriptableSystemsContainer(game).Get(n"GorillaAkimbo.GorillaAkimboSmartTargets") as GorillaAkimboSmartTargets;
  }
}

public abstract class GorillaAkimboSmart {
  public static func IsSmart(weapon: ref<WeaponObject>) -> Bool {
    if !IsDefined(weapon) {
      return false;
    }
    let record = weapon.GetWeaponRecord();
    return IsDefined(record) && IsDefined(record.Evolution()) && Equals(record.Evolution().Type(), gamedataWeaponEvolution.Smart);
  }

  // A dual-wielded Smart gun in the left hand that the mod made dual-wieldable, with the setting on and its type
  // allowed in the settings.
  public static func IsLeftSmart(owner: ref<GameObject>, weapon: ref<WeaponObject>) -> Bool {
    if !IsDefined(owner) || !owner.IsPlayer() || !IsDefined(weapon) {
      return false;
    }
    let settings = GorillaAkimboConfig.Get(owner.GetGame());
    if !settings.smartLinkBoth {
      return false;
    }
    let left = GameInstance.GetTransactionSystem(owner.GetGame()).GetItemInSlot(owner, t"AttachmentSlots.WeaponLeft");
    if !IsDefined(left) || left.GetEntityID() != weapon.GetEntityID() || !GameObject.IsDualWielding(owner) {
      return false;
    }
    let data = weapon.GetItemData();
    return GorillaAkimboSmart.IsSmart(weapon) && IsDefined(data) && data.HasTag(GorillaAkimboTag()) && IsGripWeaponAllowed(data, settings);
  }

  // The same launch aimed at a target: the part of it to hit, as the game picks it for smart shots.
  public static func AtTarget(evt: ref<gameprojectileShootEvent>, target: ref<GameObject>) -> ref<gameprojectileShootTargetEvent> {
    let forward = Matrix.GetDirectionVector(evt.localToWorld);
    let component = GameInstance.GetTargetingSystem(target.GetGame()).GetBestComponentOnTargetObject(evt.startPoint, forward, target, TargetComponentFilterType.Shooting);
    if !IsDefined(component) {
      return null;
    }
    let shot = new gameprojectileShootTargetEvent();
    shot.weapon = evt.weapon;
    shot.owner = evt.owner;
    shot.trajectoryParams = evt.trajectoryParams;
    shot.lerpMultiplier = evt.lerpMultiplier;
    shot.localToWorld = evt.localToWorld;
    shot.startPoint = evt.startPoint;
    shot.startVelocity = evt.startVelocity;
    shot.weaponVelocity = evt.weaponVelocity;
    let params = evt.params;
    params.trackedTargetComponent = component;
    params.targetPosition = Matrix.GetTranslation(component.GetLocalToWorld());
    params.smartGunIsProjectileGuided = true;
    shot.params = params;
    return shot;
  }
}

// A left Smart gun's bullet with no target of its own goes to the next locked target.
@wrapMethod(sampleSmartBullet)
protected cb func OnShoot(eventData: ref<gameprojectileShootEvent>) -> Bool {
  if IsDefined(eventData) && GorillaAkimboSmart.IsLeftSmart(eventData.owner, eventData.weapon as WeaponObject) {
    let target = GorillaAkimboSmartTargets.Get(eventData.owner.GetGame()).Next(eventData.owner);
    if IsDefined(target) {
      let shot = GorillaAkimboSmart.AtTarget(eventData, target);
      if IsDefined(shot) {
        return this.OnShootTarget(shot);
      }
    }
  }
  return wrappedMethod(eventData);
}
