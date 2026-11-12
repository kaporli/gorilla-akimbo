// Gorilla Akimbo: guns the game doesn't let V dual-wield can be dual-wielded (Double Trouble still required).
// SMGs, shotguns and assault rifles need Gorilla Arms; pistols and revolvers of every kind don't. Which item types are
// handled, and how, is in GorillaAkimboGuns.reds, generated from tools/anim/weapons.json.
module GorillaAkimbo

import Codeware.Localization.*

// Types that dual-wield with the mod's own arm clips and lowered stance, each hand on its own (not pistols and
// revolvers, which use the game's dual-wield animations).
public func IsGripWeaponType(type: gamedataItemType) -> Bool {
  return GorillaAkimboGuns.UsesArmClips(type);
}

// The tag on every weapon record the mod added the game's DualWield tag to. Guns the game already lets V dual-wield
// don't have it and are left alone.
public func GorillaAkimboTag() -> CName {
  return n"GorillaAkimboAdded";
}

public func HasGorillaArms(owner: wref<GameObject>) -> Bool {
  let player = owner as PlayerPuppet;
  if !IsDefined(player) {
    return false;
  }
  let data = EquipmentSystem.GetData(player);
  if !IsDefined(data) {
    return false;
  }
  let area = gamedataEquipmentArea.ArmsCW;
  let count = data.GetNumberOfSlots(area);
  let i = 0;
  while i < count {
    let id = data.GetItemInEquipSlot(area, i);
    if ItemID.IsValid(id) && Equals(RPGManager.GetItemType(id), gamedataItemType.Cyb_StrongArms) {
      return true;
    }
    i += 1;
  }
  return false;
}

// At load: give the handled guns the game's dual-wield tag, and add the tooltip line to Gorilla Arms.
class GorillaAkimboTweak extends ScriptableTweak {
  // The package shown as the cyberware's attuned block (the tooltip draws an attribute header for it), or -1.
  public static func AttunedIndex(packages: array<TweakDBID>) -> Int32 {
    let helper = TweakDBInterface.GetStatRecord(t"BaseStats.AttunementHelper");
    let i = 0;
    while i < ArraySize(packages) {
      let ui = TweakDBInterface.GetGameplayLogicPackageRecord(packages[i]).UIData();
      if IsDefined(ui) && ui.StatsContains(helper) {
        return i;
      }
      i += 1;
    }
    return -1;
  }

  protected func OnApply() {
    // Weapons are WeaponItem records, cyberware is Item records: GetRecords returns one exact type, so check both.
    let tagged = 0;
    let armsLines = 0;
    let records = TweakDBInterface.GetRecords(n"WeaponItem_Record");
    for extra in TweakDBInterface.GetRecords(n"Item_Record") {
      ArrayPush(records, extra);
    }
    for record in records {
      let item = record as Item_Record;
      let type = gamedataItemType.Invalid;
      if IsDefined(item) && IsDefined(item.ItemType()) {
        type = item.ItemType().Type();
      }
      let id = record.GetID();
      if GorillaAkimboGuns.IsHandled(type) {
        let tags = TweakDBInterface.GetCNameArray(id + t".tags");
        if !ArrayContains(tags, n"DualWield") {
          ArrayPush(tags, n"DualWield");
          ArrayPush(tags, GorillaAkimboTag());
          TweakDBManager.SetFlat(id + t".tags", tags);
          TweakDBManager.UpdateRecord(id);
          tagged += 1;
        }
      } else {
        if Equals(type, gamedataItemType.Cyb_StrongArms) {
          let onEquip = TweakDBInterface.GetForeignKeyArray(id + t".OnEquip");
          if !ArrayContains(onEquip, t"GorillaAkimbo.GripPackage") {
            // The grip line goes above the Body Attuned block, the Body scaling lines right under it so they read
            // as part of that block. Without an attuned block, they all go at the end.
            let attuned = GorillaAkimboTweak.AttunedIndex(onEquip);
            if attuned >= 0 {
              ArrayInsert(onEquip, attuned + 1, t"GorillaAkimbo.ReloadPackage");
              ArrayInsert(onEquip, attuned + 1, t"GorillaAkimbo.FireRatePackage");
              ArrayInsert(onEquip, attuned + 1, t"GorillaAkimbo.RecoilPackage");
              ArrayInsert(onEquip, attuned, t"GorillaAkimbo.GripPackage");
            } else {
              ArrayPush(onEquip, t"GorillaAkimbo.GripPackage");
              ArrayPush(onEquip, t"GorillaAkimbo.RecoilPackage");
              ArrayPush(onEquip, t"GorillaAkimbo.FireRatePackage");
              ArrayPush(onEquip, t"GorillaAkimbo.ReloadPackage");
            }
            TweakDBManager.SetFlat(id + t".OnEquip", onEquip);
            TweakDBManager.UpdateRecord(id);
            armsLines += 1;
          }
        }
      }
    }
    TweakDBManager.SetFlat(t"GorillaAkimbo.DoubleTroubleDamage.value", TweakDBInterface.GetFloat(GorillaAkimboDamage.Effector() + t".value", 0.625));
    ModLog(n"GorillaAkimbo", s"Tagged \(tagged) weapon records, added the tooltip line to \(armsLines) Gorilla Arms records.");
  }
}

// Whether a weapon type (Power, Smart, Tech) is switched on. Guns of no such type are allowed.
public func IsEvolutionAllowed(item: ref<gameItemData>, power: Bool, smart: Bool, tech: Bool) -> Bool {
  let record = TweakDBInterface.GetWeaponItemRecord(ItemID.GetTDBID(item.GetID()));
  if !IsDefined(record) || !IsDefined(record.Evolution()) {
    return true;
  }
  let evolution = record.Evolution().Type();
  if Equals(evolution, gamedataWeaponEvolution.Power) {
    return power;
  }
  if Equals(evolution, gamedataWeaponEvolution.Smart) {
    return smart;
  }
  if Equals(evolution, gamedataWeaponEvolution.Tech) {
    return tech;
  }
  return true;
}

// Whether the settings allow dual-wielding this gun: its type's switch, its kind (Power, Smart, Tech), and for
// shotguns how it reloads.
public func IsGripWeaponAllowed(item: ref<gameItemData>, settings: ref<GorillaAkimboSettings>) -> Bool {
  let type = RPGManager.GetItemType(item.GetID());
  if !settings.Allows(GorillaAkimboGuns.Group(type), item) {
    return false;
  }
  if Equals(type, gamedataItemType.Wea_ShotgunDual) {
    return settings.doubleBarrels;
  }
  if Equals(type, gamedataItemType.Wea_Shotgun) {
    return item.GetStatValueByType(gamedataStatType.ReloadAmount) > 0.0 ? settings.shellShotguns : settings.magazineShotguns;
  }
  return true;
}

// Guns the mod made dual-wieldable only count as such when the settings allow them, and with Gorilla Arms equipped
// where their type needs them.
@wrapMethod(gameItemData)
public func CanDualWield(owner: wref<GameObject>) -> Bool {
  let result = wrappedMethod(owner);
  if !result || !this.HasTag(GorillaAkimboTag()) {
    return result;
  }
  if GorillaAkimboGuns.NeedsArms(RPGManager.GetItemType(this.GetID())) && !HasGorillaArms(owner) {
    return false;
  }
  return IsGripWeaponAllowed(this, GorillaAkimboConfig.Get(owner.GetGame()));
}

// Double Trouble's damage cut while dual-wielding (a multiplier on each hit), set from the settings.
public abstract class GorillaAkimboDamage {
  public static func Effector() -> TweakDBID {
    return t"BaseStatusEffect.DoubleTroubleLogic_inline2";
  }

  public static func Apply(settings: ref<GorillaAkimboSettings>) {
    let value = settings.noDamagePenalty ? 1.0 : TweakDBInterface.GetFloat(t"GorillaAkimbo.DoubleTroubleDamage.value", 0.625);
    if AbsF(TweakDBInterface.GetFloat(GorillaAkimboDamage.Effector() + t".value", value) - value) > 0.0001 {
      TweakDBManager.SetFlat(GorillaAkimboDamage.Effector() + t".value", value);
      TweakDBManager.UpdateRecord(GorillaAkimboDamage.Effector());
    }
  }
}

// Dual-wielded SMGs and shotguns use the arm clips in GorillaAkimbo.archive (see GorillaAkimbo.archive.xl): the gun
// tips up while the magazine drops, goes down out of view, holds, and rises back once its ammo is in. Shell-by-shell
// shotguns load their shells one at a time during one reload.
// Stat changes made to dual-wielded grip weapons, per item and group (n"reload" for one reload, n"body" for the
// Body scaling). Weapon objects are made again on each draw, so they are kept here and taken off before they are
// set again.
public class GorillaAkimboReloadSystem extends ScriptableSystem {
  private let m_items: array<ItemID>;
  private let m_groups: array<CName>;
  private let m_mods: array<ref<gameStatModifierData>>;
  private let m_owners: array<StatsObjectID>;
  // Sim time of each hand's last shot, for the Alternate firing setting.
  public let m_lastShotRight: Float;
  public let m_lastShotLeft: Float;

  public static func Get(game: GameInstance) -> ref<GorillaAkimboReloadSystem> {
    return GameInstance.GetScriptableSystemsContainer(game).Get(n"GorillaAkimbo.GorillaAkimboReloadSystem") as GorillaAkimboReloadSystem;
  }

  public func Clear(item: ItemID, group: CName) {
    let stats = GameInstance.GetStatsSystem(this.GetGameInstance());
    let i = ArraySize(this.m_items) - 1;
    while i >= 0 {
      if Equals(this.m_items[i], item) && Equals(this.m_groups[i], group) {
        stats.RemoveModifier(this.m_owners[i], this.m_mods[i]);
        ArrayErase(this.m_items, i);
        ArrayErase(this.m_groups, i);
        ArrayErase(this.m_mods, i);
        ArrayErase(this.m_owners, i);
      }
      i -= 1;
    }
  }

  public func Add(weapon: ref<WeaponObject>, group: CName, stat: gamedataStatType, type: gameStatModifierType, value: Float) {
    let owner = Cast<StatsObjectID>(weapon.GetEntityID());
    let mod = RPGManager.CreateStatModifier(stat, type, value);
    GameInstance.GetStatsSystem(this.GetGameInstance()).AddModifier(owner, mod);
    ArrayPush(this.m_items, weapon.GetItemID());
    ArrayPush(this.m_groups, group);
    ArrayPush(this.m_mods, mod);
    ArrayPush(this.m_owners, owner);
  }
}

// Body scaling of dual-wielded SMGs and shotguns, like the game's attribute bonuses: a fixed change per Body point,
// counted from 0 (so Body 20 gives 20 times the per-point value).
public abstract class GorillaAkimboBody {
  public static func Body(owner: ref<GameObject>) -> Float {
    return GameInstance.GetStatsSystem(owner.GetGame()).GetStatValue(Cast<StatsObjectID>(owner.GetEntityID()), gamedataStatType.Strength);
  }

  // Multipliers at the player's Body (1 when the scaling is off).
  public static func Recoil(settings: ref<GorillaAkimboSettings>, body: Float) -> Float {
    return settings.recoilScaling ? MaxF(1.0 - settings.recoilPerPoint * body / 100.0, 0.1) : 1.0;
  }

  public static func FireRate(settings: ref<GorillaAkimboSettings>, body: Float) -> Float {
    return settings.fireRateScaling ? 1.0 + settings.fireRatePerPoint * body / 100.0 : 1.0;
  }

  public static func ReloadSpeed(settings: ref<GorillaAkimboSettings>, body: Float) -> Float {
    return settings.reloadScaling ? 1.0 + settings.reloadPerPoint * body / 100.0 : 1.0;
  }

  // Reload time multiplier of the reload speed scaling (1 when off).
  public static func ReloadTimeFactor(owner: ref<GameObject>, settings: ref<GorillaAkimboSettings>) -> Float {
    return 1.0 / GorillaAkimboBody.ReloadSpeed(settings, GorillaAkimboBody.Body(owner));
  }

  // Sets the scaling on a weapon again: on a dual-wielded grip weapon from the settings, otherwise none.
  public static func Apply(weapon: ref<WeaponObject>, owner: ref<GameObject>) {
    if !IsDefined(weapon) {
      return;
    }
    let system = GorillaAkimboReloadSystem.Get(weapon.GetGame());
    system.Clear(weapon.GetItemID(), n"body");
    if !IsGripWeaponType(RPGManager.GetItemType(weapon.GetItemID())) || !GameObject.IsDualWielding(owner) {
      return;
    }
    let settings = GorillaAkimboConfig.Get(weapon.GetGame());
    let body = GorillaAkimboBody.Body(owner);
    let recoil = GorillaAkimboBody.Recoil(settings, body);
    if recoil != 1.0 {
      system.Add(weapon, n"body", gamedataStatType.RecoilKickMin, gameStatModifierType.Multiplier, recoil);
      system.Add(weapon, n"body", gamedataStatType.RecoilKickMax, gameStatModifierType.Multiplier, recoil);
    }
    let rate = GorillaAkimboBody.FireRate(settings, body);
    if rate != 1.0 {
      system.Add(weapon, n"body", gamedataStatType.CycleTime, gameStatModifierType.Multiplier, 1.0 / rate);
      system.Add(weapon, n"body", gamedataStatType.CycleTime_Burst, gameStatModifierType.Multiplier, 1.0 / rate);
    }
    let reload = GorillaAkimboBody.ReloadTimeFactor(owner, settings);
    if reload != 1.0 {
      system.Add(weapon, n"body", gamedataStatType.ReloadTime, gameStatModifierType.Multiplier, reload);
      system.Add(weapon, n"body", gamedataStatType.EmptyReloadTime, gameStatModifierType.Multiplier, reload);
    }
  }

  // The Gorilla Arms tooltip lines, like the game's attuned line: the change per Body point, then the total at the
  // player's Body, in percent.
  public static func UpdateTooltip(owner: ref<GameObject>) {
    let settings = GorillaAkimboConfig.Get(owner.GetGame());
    let body = GorillaAkimboBody.Body(owner);
    GorillaAkimboBody.SetLine(t"GorillaAkimbo.RecoilUIData", settings.recoilScaling ? settings.recoilPerPoint : 0.0, 1.0 - GorillaAkimboBody.Recoil(settings, body));
    GorillaAkimboBody.SetLine(t"GorillaAkimbo.FireRateUIData", settings.fireRateScaling ? settings.fireRatePerPoint : 0.0, GorillaAkimboBody.FireRate(settings, body) - 1.0);
    GorillaAkimboBody.SetLine(t"GorillaAkimbo.ReloadUIData", settings.reloadScaling ? settings.reloadPerPoint : 0.0, GorillaAkimboBody.ReloadSpeed(settings, body) - 1.0);
  }

  private static func SetLine(record: TweakDBID, perPoint: Float, total: Float) {
    let values: array<Float>;
    ArrayPush(values, Cast<Float>(Cast<Int32>(perPoint * 10.0 + 0.5)) / 10.0);
    ArrayPush(values, Cast<Float>(Cast<Int32>(total * 1000.0 + 0.5)) / 10.0);
    TweakDBManager.SetFlat(record + t".floatValues", values);
    TweakDBManager.UpdateRecord(record);
  }

  // Both hands.
  public static func Refresh(owner: ref<GameObject>) {
    let ts = GameInstance.GetTransactionSystem(owner.GetGame());
    GorillaAkimboBody.Apply(ts.GetItemInSlot(owner, t"AttachmentSlots.WeaponRight") as WeaponObject, owner);
    GorillaAkimboBody.Apply(ts.GetItemInSlot(owner, t"AttachmentSlots.WeaponLeft") as WeaponObject, owner);
  }
}

public abstract class GorillaAkimboReload {
  // Arm clip layout, in clip seconds (the numbers flick.py builds the clips with). Magazine guns: a slow tip-up until OpenEnd, down out of view by DropEnd, held
  // there until HoldEnd, then the rise. Shell-by-shell guns (_02 clips): down by PlainDrop.
  public static func OpenEnd() -> Float {
    return GorillaAkimboGuns.OpenEnd();
  }

  public static func DropEnd() -> Float {
    return GorillaAkimboGuns.DropEnd();
  }

  public static func HoldEnd() -> Float {
    return GorillaAkimboGuns.HoldEnd();
  }

  // Highest clip speed asked of the animation graph: very high speeds have crashed its speed node.
  public static func MaxSpeed() -> Float {
    return 8.0;
  }

  public static func PlainDrop() -> Float {
    return GorillaAkimboGuns.PlainDrop();
  }

  public static func RiseLength() -> Float {
    return GorillaAkimboGuns.RiseLength();
  }

  // Seconds the magazine takes to fall clear after it leaves the gun.
  public static func MagFall() -> Float {
    return 0.45;
  }

  // Clip speed at a time into the reload. The gun's own reload animation runs at the same speed as the arm clip, so
  // its magazine leaves at clip time magOut whatever the speed. The opening (tip-up and drop) plays at one speed per
  // gun, picked so the drop starts once that magazine has fallen clear; the speed changes only while the gun is out
  // of view. The out-of-view hold is fast-forwarded so the rise starts when the ammo lands.
  public static func Speed(time: Float, duration: Float, magOut: Float, shells: Bool) -> Float {
    let opening = shells ? GorillaAkimboReload.PlainDrop() : GorillaAkimboReload.DropEnd();
    let rate = 1.0;
    if !shells {
      rate = ClampF((GorillaAkimboReload.OpenEnd() - magOut) / GorillaAkimboReload.MagFall(), 0.6, 1.4);
    }
    // Short reloads play the opening faster, so the gun is down well before the ammo lands.
    rate = MinF(MaxF(rate, opening / MaxF(0.75 * duration, 0.05)), GorillaAkimboReload.MaxSpeed());
    let openingReal = opening / rate;
    if time < openingReal {
      return rate;
    }
    if time < duration {
      return MinF((GorillaAkimboReload.HoldEnd() - opening) / MaxF(duration - openingReal, 0.05), GorillaAkimboReload.MaxSpeed());
    }
    return 1.0;
  }

  // Guns with reload clips of their own (rifles; GorillaAkimboGuns.ReloadOwner): the clip plays at its own speed
  // until the gun, hand and magazines are out of view (opening), the hidden part is fast-forwarded or slowed so it
  // ends (holdEnd) when the ammo lands, and the rest plays at its own speed again.
  public static func OwnSpeed(time: Float, duration: Float, opening: Float, holdEnd: Float) -> Float {
    // Short reloads play the opening faster, so the gun is down well before the ammo lands.
    let rate = MinF(MaxF(1.0, opening / MaxF(0.75 * duration, 0.05)), GorillaAkimboReload.MaxSpeed());
    let openingReal = opening / rate;
    if time < openingReal {
      return rate;
    }
    if time < duration {
      return MinF((holdEnd - opening) / MaxF(duration - openingReal, 0.05), GorillaAkimboReload.MaxSpeed());
    }
    return 1.0;
  }

  // Seconds into the reload at which such a clip reaches clip second t (for the gun's sounds).
  public static func OwnTime(t: Float, duration: Float, opening: Float, holdEnd: Float) -> Float {
    let rate = GorillaAkimboReload.OwnSpeed(0.0, duration, opening, holdEnd);
    let openingReal = opening / rate;
    if t <= opening {
      return t / rate;
    }
    if t <= holdEnd {
      return openingReal + (t - opening) / MaxF(GorillaAkimboReload.OwnSpeed(openingReal, duration, opening, holdEnd), 0.05);
    }
    return MaxF(duration, openingReal) + t - holdEnd;
  }

  // The longest part of such a gun's clips after the hidden part, over its variants: the reload state lasts that
  // much longer than the ammo takes.
  public static func OwnRise(owner: CName, empty: Bool) -> Float {
    let rise = 0.0;
    let i = 0;
    while i < 3 {
      rise = MaxF(rise, GorillaAkimboGuns.ReloadLength(owner, i, empty) - GorillaAkimboGuns.ReloadHideEnd(owner, i, empty));
      i += 1;
    }
    return rise;
  }

  // The gun whose own reload clips this weapon plays while dual-wielded, n"None" on the generic clips.
  public static func Owner(record: ref<WeaponItem_Record>) -> CName {
    return IsDefined(record) ? GorillaAkimboGuns.ReloadOwner(record.AudioName()) : n"None";
  }

  // The magazine track set of such a gun, as the anim wrapper on the gun that selects it in the archive.xl
  // (GorillaAkimboRifles.archive.xl): per gun, body and hand.
  public static func MagazineWrapper(owner: CName, player: ref<GameObject>, left: Bool) -> CName {
    let puppet = player as PlayerPuppet;
    let body = IsDefined(puppet) && Equals(puppet.GetResolvedGenderName(), n"Female") ? "pwa" : "pma";
    return StringToName("gorillaakimbo_rmag_" + NameToString(owner) + "_" + body + "_" + (left ? "left" : "right"));
  }

  // The weapon's audio name, or a gun of its type when the game files have no reload sounds for it.
  public static func Audio(record: ref<WeaponItem_Record>, kind: Int32) -> CName {
    let audio = record.AudioName();
    if !GorillaAkimboSounds.Has(audio) {
      audio = GorillaAkimboGuns.FallbackAudio(record.ItemType().Type(), kind == GorillaAkimboReload.Shells());
    }
    return audio;
  }

  // Takes off the changes of an earlier reload, then sets them up again when the weapon is a dual-wielded
  // grip weapon. Returns how it reloads (Magazine or Shells), 0 when the arm clips aren't used.
  // shellTimes, shellCounts: for shell-by-shell guns, the times into the reload at which shells are loaded and
  // how many (0 for one of the game's passes), except the last pass, which the reload's end loads as usual.
  // passStarts, passLengths: when each of the game's passes would start and how long its reload takes (one pass
  // for magazine guns and for shells loaded all at once).
  public static func Prepare(weapon: ref<WeaponObject>, owner: ref<GameObject>, shellTimes: script_ref<array<Float>>,
                             shellCounts: script_ref<array<Int32>>, passStarts: script_ref<array<Float>>,
                             passLengths: script_ref<array<Float>>) -> Int32 {
    ArrayClear(Deref(shellTimes));
    ArrayClear(Deref(shellCounts));
    ArrayClear(Deref(passStarts));
    ArrayClear(Deref(passLengths));
    if !IsDefined(weapon) {
      return 0;
    }
    let system = GorillaAkimboReloadSystem.Get(weapon.GetGame());
    system.Clear(weapon.GetItemID(), n"reload");
    // The Body scaling may have changed since the draw (a level up, the settings).
    GorillaAkimboBody.Apply(weapon, owner);
    let type = RPGManager.GetItemType(weapon.GetItemID());
    if !IsGripWeaponType(type) || !GameObject.IsDualWielding(owner) {
      return 0;
    }
    let settings = GorillaAkimboConfig.Get(weapon.GetGame());
    let stats = GameInstance.GetStatsSystem(weapon.GetGame());
    let id = Cast<StatsObjectID>(weapon.GetEntityID());
    let perReload = stats.GetStatValue(id, gamedataStatType.ReloadAmount);
    let kind = GorillaAkimboReload.Magazine();
    ArrayPush(Deref(passStarts), 0.0);
    ArrayPush(Deref(passLengths), stats.GetStatValue(id, weapon.IsMagazineEmpty() ? gamedataStatType.EmptyReloadTime : gamedataStatType.ReloadTime));
    if perReload > 0.0 {
      let empty = weapon.IsMagazineEmpty();
      let missing = MaxF(Cast<Float>(WeaponObject.GetMagazineCapacity(weapon)) - Cast<Float>(WeaponObject.GetMagazineAmmoCount(weapon)), 1.0);
      let reloadTime = stats.GetStatValue(id, gamedataStatType.ReloadTime);
      let first = empty ? stats.GetStatValue(id, gamedataStatType.EmptyReloadTime) : reloadTime;
      if Equals(settings.shellReload, GorillaAkimboShellReload.AllAtOnce) {
        // All at once: one pass long; the shells beyond the last pass go in just before its end.
        if missing > perReload {
          ArrayPush(Deref(shellTimes), first * 0.9);
          ArrayPush(Deref(shellCounts), Cast<Int32>(missing - perReload));
        }
      } else {
        // Shell by shell: one reload state as long as the game's own passes would take, so the arm stays down
        // throughout. Each pass after the first takes its reload time plus the previous pass's end time (the
        // reload state lasts that long before the next pass starts); an empty gun's first pass ends after the
        // empty end time instead.
        let passes = CeilF(missing / perReload);
        let endTime = stats.GetStatValue(id, gamedataStatType.ReloadEndTime);
        let time = first;
        let i = 1;
        while i < passes {
          ArrayPush(Deref(shellTimes), time);
          ArrayPush(Deref(shellCounts), 0);
          time += i == 1 && empty ? stats.GetStatValue(id, gamedataStatType.EmptyReloadEndTime) : endTime;
          ArrayPush(Deref(passStarts), time);
          ArrayPush(Deref(passLengths), reloadTime);
          time += reloadTime;
          i += 1;
        }
        // The reload times are multiplied by the reload speed scaling after this is added.
        let extra = (time - first) / GorillaAkimboBody.ReloadTimeFactor(owner, settings);
        system.Add(weapon, n"reload", gamedataStatType.ReloadTime, gameStatModifierType.Additive, extra);
        system.Add(weapon, n"reload", gamedataStatType.EmptyReloadTime, gameStatModifierType.Additive, extra);
      }
      kind = GorillaAkimboReload.Shells();
    }
    // The reload state lasts until the rise is done, so its end doesn't cut the clip. The gun can fire as
    // soon as the ammo is in: firing ends the reload state.
    let rise = GorillaAkimboReload.RiseLength();
    let own = GorillaAkimboReload.Owner(weapon.GetWeaponRecord());
    if kind == GorillaAkimboReload.Magazine() && IsNameValid(own) {
      rise = GorillaAkimboReload.OwnRise(own, weapon.IsMagazineEmpty());
    }
    system.Add(weapon, n"reload", gamedataStatType.ReloadEndTime, gameStatModifierType.Additive, rise);
    system.Add(weapon, n"reload", gamedataStatType.EmptyReloadEndTime, gameStatModifierType.Additive, rise);
    return kind;
  }

  // Loads shells: count of them, or one pass (up to ReloadAmount) when count is 0; as many as fit and as the
  // player has.
  public static func LoadPass(weapon: ref<WeaponObject>, owner: ref<GameObject>, count: Int32) {
    let ts = GameInstance.GetTransactionSystem(weapon.GetGame());
    let ammo = WeaponObject.GetAmmoType(weapon);
    if count <= 0 {
      count = Cast<Int32>(GameInstance.GetStatsSystem(weapon.GetGame()).GetStatValue(Cast<StatsObjectID>(weapon.GetEntityID()), gamedataStatType.ReloadAmount));
    }
    let mag = Cast<Int32>(WeaponObject.GetMagazineAmmoCount(weapon));
    let room = Cast<Int32>(WeaponObject.GetMagazineCapacity(weapon)) - mag;
    count = Min(Min(count, room), ts.GetItemQuantity(owner, ammo));
    if count <= 0 {
      return;
    }
    // The event takes the rounds from the player's ammo itself.
    let evt = new SetAmmoCountEvent();
    evt.ammoTypeID = ammo;
    evt.count = Cast<Uint32>(mag + count);
    weapon.QueueEvent(evt);
    WeaponObject.SendAmmoUpdateEvent(owner, weapon);
  }

  // The weapon's own reload sounds for each pass, timed as its own reload clip would play them: clip seconds
  // scaled by the pass's reload time over the base reload time. A pass's sounds after the next pass starts are
  // cut, as the game's own clip would be.
  public static func Sounds(weapon: ref<WeaponObject>, record: ref<WeaponItem_Record>, kind: Int32, passStarts: array<Float>,
                            passLengths: array<Float>, times: script_ref<array<Float>>, names: script_ref<array<CName>>) {
    ArrayClear(Deref(times));
    ArrayClear(Deref(names));
    let audio = GorillaAkimboReload.Audio(record, kind);
    let empty = weapon.IsMagazineEmpty();
    let n = ArraySize(passStarts);
    let i = 0;
    while i < n {
      let first = i == 0 && empty;
      let base = first ? record.BaseEmptyReloadTime() : record.BaseReloadTime();
      let scale = base > 0.0 ? passLengths[i] / base : 1.0;
      let clipTimes: array<Float>;
      let clipNames: array<CName>;
      GorillaAkimboSounds.Get(audio, first, clipTimes, clipNames);
      let j = 0;
      while j < ArraySize(clipTimes) {
        let t = passStarts[i] + clipTimes[j] * scale;
        if i == n - 1 || t < passStarts[i + 1] {
          ArrayPush(Deref(times), t);
          ArrayPush(Deref(names), clipNames[j]);
        }
        j += 1;
      }
      i += 1;
    }
  }

  public static func Magazine() -> Int32 {
    return 1;
  }

  public static func Shells() -> Int32 {
    return 2;
  }

  // Which arm clip variant plays, through the game's random reload pick (0, 1, 2 = reload, _01, _02).
  // _02 is the plain drop for shell-by-shell guns; magazine guns get one of the tip-up clips.
  public static func Variant(kind: Int32, current: Int32) -> Int32 {
    if kind == GorillaAkimboReload.Shells() {
      return 2;
    }
    return current == 2 ? RandRange(0, 2) : current;
  }
}

@addField(ReloadEvents)
private let m_gorillaTimed: Bool;

@addField(ReloadEvents)
private let m_gorillaSpeed: Float;

@addField(ReloadEvents)
private let m_gorillaShellTimes: array<Float>;

@addField(ReloadEvents)
private let m_gorillaShellCounts: array<Int32>;

@addField(ReloadEvents)
private let m_gorillaShells: Bool;

@addField(ReloadEvents)
private let m_gorillaSoundTimes: array<Float>;

@addField(ReloadEvents)
private let m_gorillaSoundNames: array<CName>;

@addField(ReloadEvents)
private let m_gorillaMagOut: Float;

// A gun with reload clips of its own: that gun, the variant playing, whether it is the empty reload, and the
// magazine wrapper turned on on the weapon for this reload.
@addField(ReloadEvents)
private let m_gorillaOwn: CName;

@addField(ReloadEvents)
private let m_gorillaOwnVariant: Int32;

@addField(ReloadEvents)
private let m_gorillaOwnEmpty: Bool;

@addField(ReloadEvents)
private let m_gorillaOwnWrapper: CName;

@addField(ReloadEvents)
private let m_gorillaOwnWeapon: wref<WeaponObject>;

// The speed of a gun's own reload clip at a time into the reload.
@addMethod(ReloadEvents)
private final func GorillaOwnSpeed(time: Float, duration: Float) -> Float {
  return GorillaAkimboReload.OwnSpeed(time, duration, GorillaAkimboGuns.ReloadHideStart(this.m_gorillaOwn, this.m_gorillaOwnVariant, this.m_gorillaOwnEmpty),
    GorillaAkimboGuns.ReloadHideEnd(this.m_gorillaOwn, this.m_gorillaOwnVariant, this.m_gorillaOwnEmpty));
}

// Turns the magazine track set of the last own reload off again.
@addMethod(ReloadEvents)
public final func GorillaOwnEnd() -> Void {
  if IsNameValid(this.m_gorillaOwnWrapper) && IsDefined(this.m_gorillaOwnWeapon) {
    AnimationControllerComponent.SetAnimWrapperWeight(this.m_gorillaOwnWeapon, this.m_gorillaOwnWrapper, 0.0);
  }
  this.m_gorillaOwnWrapper = n"None";
  this.m_gorillaOwn = n"None";
}

@wrapMethod(ReloadEvents)
protected final func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  let weapon = this.GetWeaponObject(scriptInterface);
  GorillaAkimboTopMagSystem.Get(scriptInterface.GetGame()).SetReloading(this.IsLeftWeaponLogic(), true);
  // Top-magazine guns: a two-handed clip (GorillaAkimboTopMag.reds).
  this.m_gorillaTopMag = this.GorillaTopMagPrepare(weapon, scriptInterface);
  if this.m_gorillaTopMag {
    this.m_gorillaTimed = false;
    this.m_gorillaShells = false;
    ArrayClear(this.m_gorillaShellTimes);
    ArrayClear(this.m_gorillaShellCounts);
    wrappedMethod(stateContext, scriptInterface);
    this.GorillaTopMagStart(scriptInterface);
    return;
  }
  let passStarts: array<Float>;
  let passLengths: array<Float>;
  let kind = GorillaAkimboReload.Prepare(weapon, scriptInterface.executionOwner, this.m_gorillaShellTimes, this.m_gorillaShellCounts, passStarts, passLengths);
  this.m_gorillaTimed = kind > 0;
  if this.m_gorillaTimed {
    GorillaAkimboReload.Sounds(weapon, this.m_weaponRecord, kind, passStarts, passLengths, this.m_gorillaSoundTimes, this.m_gorillaSoundNames);
  } else {
    ArrayClear(this.m_gorillaSoundTimes);
    ArrayClear(this.m_gorillaSoundNames);
  }
  this.m_gorillaShells = kind == GorillaAkimboReload.Shells();
  this.GorillaOwnEnd();
  if kind == GorillaAkimboReload.Magazine() {
    this.m_gorillaOwn = GorillaAkimboReload.Owner(this.m_weaponRecord);
    this.m_gorillaOwnVariant = 0;
    this.m_gorillaOwnEmpty = weapon.IsMagazineEmpty();
  }
  if this.m_gorillaTimed {
    this.m_gorillaMagOut = GorillaAkimboSounds.MagOut(GorillaAkimboReload.Audio(this.m_weaponRecord, kind), weapon.IsMagazineEmpty());
    let stats = scriptInterface.GetStatsSystem();
    let id = Cast<StatsObjectID>(weapon.GetEntityID());
    // The arm clips are one whole reload; a shell count would send the anim graph into its shell loop, which
    // has no dual-wield clips. The shells themselves are loaded by OnUpdate and the reload's end.
    this.m_animReloadData.amountToReload = 0;
    this.m_animReloadData.loopDuration = stats.GetStatValue(id, gamedataStatType.ReloadTime);
    this.m_animReloadData.emptyDuration = stats.GetStatValue(id, gamedataStatType.EmptyReloadTime);
    let duration = weapon.IsMagazineEmpty() ? this.m_animReloadData.emptyDuration : this.m_animReloadData.loopDuration;
    this.m_gorillaSpeed = GorillaAkimboReload.Speed(0.0, duration, this.m_gorillaMagOut, this.m_gorillaShells);
    if IsNameValid(this.m_gorillaOwn) {
      this.m_gorillaSpeed = this.GorillaOwnSpeed(0.0, duration);
    }
    this.m_animReloadSpeed.reloadSpeed = this.m_gorillaSpeed;
    this.m_animReloadSpeed.emptyReloadSpeed = this.m_gorillaSpeed;
    this.m_animReloadDataDirty = true;
    this.m_animReloadSpeedDirty = true;
  } else {
    // Single-wielded again: back to the speeds made for the weapon's own animations.
    if IsDefined(weapon) && IsGripWeaponType(RPGManager.GetItemType(weapon.GetItemID())) {
      this.m_animReloadSpeed.reloadSpeed = this.GetReloadAnimSpeed(gamedataStatType.ReloadTime, this.m_weaponRecord);
      this.m_animReloadSpeed.emptyReloadSpeed = this.GetReloadAnimSpeed(gamedataStatType.EmptyReloadTime, this.m_weaponRecord);
      this.m_animReloadSpeedDirty = true;
    }
  }
  wrappedMethod(stateContext, scriptInterface);
  if this.m_gorillaTimed && IsNameValid(this.m_gorillaOwn) {
    // The game's pick is known now: its own layout, the gun's sounds along it, and its magazine track set.
    this.m_gorillaOwnVariant = IsDefined(this.m_randomSync) ? Clamp(this.m_randomSync.value, 0, 2) : 0;
    let own = this.m_gorillaOwn;
    let opening = GorillaAkimboGuns.ReloadHideStart(own, this.m_gorillaOwnVariant, this.m_gorillaOwnEmpty);
    let holdEnd = GorillaAkimboGuns.ReloadHideEnd(own, this.m_gorillaOwnVariant, this.m_gorillaOwnEmpty);
    let ownDuration = this.m_gorillaOwnEmpty ? this.m_animReloadData.emptyDuration : this.m_animReloadData.loopDuration;
    let clipTimes: array<Float>;
    GorillaAkimboSounds.Get(GorillaAkimboReload.Audio(this.m_weaponRecord, kind), this.m_gorillaOwnEmpty, clipTimes, this.m_gorillaSoundNames);
    ArrayClear(this.m_gorillaSoundTimes);
    for clipTime in clipTimes {
      ArrayPush(this.m_gorillaSoundTimes, GorillaAkimboReload.OwnTime(clipTime, ownDuration, opening, holdEnd));
    }
    this.m_gorillaOwnWeapon = weapon;
    this.m_gorillaOwnWrapper = GorillaAkimboReload.MagazineWrapper(own, scriptInterface.executionOwner, this.IsLeftWeaponLogic());
    AnimationControllerComponent.SetAnimWrapperWeight(weapon, this.m_gorillaOwnWrapper, 1.0);
    return;
  }
  if this.m_gorillaTimed && IsDefined(this.m_randomSync) {
    this.m_randomSync.value = GorillaAkimboReload.Variant(kind, this.m_randomSync.value);
    scriptInterface.SetAnimationParameterFeature(this.IsRightWeaponLogic() ? n"RandomSync" : n"LeftRandomSync", this.m_randomSync);
  }
}

// Re-times the arm clip as the reload goes, against the duration the game itself checks for the ammo.
@wrapMethod(ReloadEvents)
protected final func OnUpdate(timeDelta: Float, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(timeDelta, stateContext, scriptInterface);
  if this.m_gorillaTopMag {
    this.GorillaTopMagUpdate(timeDelta, scriptInterface);
    // Top-magazine clips play at one speed; only the guns' own reload sounds are played here.
    while ArraySize(this.m_gorillaSoundTimes) > 0 && this.GetInStateTime() >= this.m_gorillaSoundTimes[0] {
      GameObject.PlaySoundEvent(scriptInterface.executionOwner, this.m_gorillaSoundNames[0]);
      ArrayErase(this.m_gorillaSoundTimes, 0);
      ArrayErase(this.m_gorillaSoundNames, 0);
    }
    return;
  }
  if !this.m_gorillaTimed {
    return;
  }
  let duration = stateContext.GetPermanentFloatParameter(this.GetReloadLogicalDuration());
  if !duration.valid {
    return;
  }
  let speed = GorillaAkimboReload.Speed(this.GetInStateTime(), duration.value, this.m_gorillaMagOut, this.m_gorillaShells);
  if IsNameValid(this.m_gorillaOwn) {
    speed = this.GorillaOwnSpeed(this.GetInStateTime(), duration.value);
  }
  if AbsF(speed - this.m_gorillaSpeed) > 0.001 {
    this.m_gorillaSpeed = speed;
    this.m_animReloadSpeed.reloadSpeed = speed;
    this.m_animReloadSpeed.emptyReloadSpeed = speed;
    scriptInterface.SetAnimationParameterFeature(this.IsRightWeaponLogic() ? n"RightReloadSpeed" : n"LeftReloadSpeed", this.m_animReloadSpeed);
  }
  // Shell by shell: the passes before the last load as the game's own would, so the counter fills shell by
  // shell and firing mid-reload keeps what is in. All at once: the shells beyond the last pass load together.
  while ArraySize(this.m_gorillaShellTimes) > 0 && this.GetInStateTime() >= this.m_gorillaShellTimes[0] {
    ArrayErase(this.m_gorillaShellTimes, 0);
    GorillaAkimboReload.LoadPass(this.GetWeaponObject(scriptInterface), scriptInterface.executionOwner, this.m_gorillaShellCounts[0]);
    ArrayErase(this.m_gorillaShellCounts, 0);
  }
  // The weapon's own reload sounds (the arm clips carry none).
  while ArraySize(this.m_gorillaSoundTimes) > 0 && this.GetInStateTime() >= this.m_gorillaSoundTimes[0] {
    GameObject.PlaySoundEvent(scriptInterface.executionOwner, this.m_gorillaSoundNames[0]);
    ArrayErase(this.m_gorillaSoundTimes, 0);
    ArrayErase(this.m_gorillaSoundNames, 0);
  }
  // A shell-by-shell reload can be cut short by firing the whole way through (the game itself allows it early
  // in each of its own passes), keeping the shells already in. As in the base game, only the right hand's
  // reload can be cut short while dual-wielding.
  if this.m_gorillaShells {
    stateContext.SetPermanentFloatParameter(this.GetUninteruptibleReloadTimeStamp(), this.GetInStateTime() + 1.0, true);
  }
}

// The ammo counter is drawn into a HUD slot as wide as its root's HUD entry size (1100). Two long SMG or
// shotgun icons push the left gun's ammo count past that, where it's cut off. The root and its entry are made
// wider to the left; the counter is anchored to the right, so nothing moves.
@wrapMethod(WeaponRosterGameController)
protected cb func OnInitialize() -> Bool {
  let result = wrappedMethod();
  let extra = 600.0;
  let root = this.GetRootWidget();
  let info = root.GetUserData(n"inkHudEntryInfo") as inkHudEntryInfo;
  if IsDefined(info) {
    let size = info.size;
    info.size = new Vector2(size.X + extra, size.Y);
    let rootSize = root.GetSize();
    root.SetSize(new Vector2(rootSize.X + extra, rootSize.Y));
  }
  return result;
}

// The ranged anim graph animates each hand on its own only when the right hand holds a one-handed weapon
// (item type anim index 1, pistols and revolvers). Dual-wielded grip weapons report 1 so each gun reloads
// with its own arm; held alone they report their own index again.
public abstract class GorillaAkimboHands {
  public static func OneHandedIndex() -> Int32 {
    return 1;
  }

  // Sets a hand's item handling with the dual-wield index, the way the game sets it (not replicated: a replicated
  // feature keeps overriding the game's later updates, so the hands stayed "equipped" after the guns were put away).
  public static func Set(scriptInterface: ref<StateGameScriptInterface>, left: Bool, state: Int32, duration: Float) {
    let feature = new AnimFeature_EquipUnequipItem();
    feature.stateTransitionDuration = duration;
    feature.itemState = state;
    feature.itemType = GorillaAkimboHands.OneHandedIndex();
    scriptInterface.SetAnimationParameterFeature(left ? n"leftHandItemHandling" : n"rightHandItemHandling", feature, scriptInterface.executionOwner);
  }

  // A grip weapon in a dual-wielded pair: both slots filled, this hand's item an SMG or shotgun.
  public static func IsDualGrip(owner: ref<GameObject>, item: ItemID) -> Bool {
    let ts = GameInstance.GetTransactionSystem(owner.GetGame());
    return IsGripWeaponType(RPGManager.GetItemType(item)) && IsDefined(ts.GetItemInSlot(owner, t"AttachmentSlots.WeaponLeft"))
      && IsDefined(ts.GetItemInSlot(owner, t"AttachmentSlots.WeaponRight"));
  }

  // Sends the hand's item handling again for the gun in its slot (state: the itemState just sent): the dual-wield
  // index while dual-wielding, the weapon's own one otherwise.
  public static func Send(scriptInterface: ref<StateGameScriptInterface>, left: Bool, state: Int32, duration: Float) {
    let owner = scriptInterface.executionOwner;
    let item = GameInstance.GetTransactionSystem(owner.GetGame()).GetItemInSlot(owner, left ? t"AttachmentSlots.WeaponLeft" : t"AttachmentSlots.WeaponRight");
    if !IsDefined(item) || !IsGripWeaponType(RPGManager.GetItemType(item.GetItemID())) {
      return;
    }
    // Gadget: during a pair's throw the right gun keeps the dual-wield index while the left slot is empty, so a reload
    // of the right gun isn't cut when the left gun comes back (GorillaAkimboGadget.reds).
    if GorillaAkimboHands.IsDualGrip(owner, item.GetItemID()) || (!left && GorillaAkimboGadgetSystem.Active(owner)) {
      GorillaAkimboHands.Set(scriptInterface, left, state, duration);
    } else {
      let feature = new AnimFeature_EquipUnequipItem();
      feature.stateTransitionDuration = duration;
      feature.itemState = state;
      feature.itemType = TweakDBInterface.GetItemRecord(ItemID.GetTDBID(item.GetItemID())).ItemType().AnimFeatureIndex();
      scriptInterface.SetAnimationParameterFeature(left ? n"leftHandItemHandling" : n"rightHandItemHandling", feature, owner);
    }
  }
}

@wrapMethod(EquipmentBaseTransition)
protected final const func HandleWeaponEquip(scriptInterface: ref<StateGameScriptInterface>, stateContext: ref<StateContext>, stateMachineInstanceData: StateMachineInstanceData, item: ItemID, isLeftWeapon: Bool) -> Void {
  wrappedMethod(scriptInterface, stateContext, stateMachineInstanceData, item, isLeftWeapon);
  let duration = scriptInterface.GetStatsSystem().GetStatValue(Cast<StatsObjectID>(scriptInterface.executionOwnerEntityID), gamedataStatType.EquipDuration);
  GorillaAkimboHands.Send(scriptInterface, this.IsLeftHandLogic(stateMachineInstanceData), 1, duration);
}

// Putting a dual-wielded pair away (holstering, or the game hiding the guns for a very hard landing): the game sends
// each hand with the weapon's own index; vanilla pistol pairs use the dual-wield index throughout, so this does too.
@wrapMethod(EquipmentBaseTransition)
protected final const func HandleWeaponUnequip(scriptInterface: ref<StateGameScriptInterface>, stateContext: ref<StateContext>, stateMachineInstanceData: StateMachineInstanceData, item: ItemID, isLeftWeapon: Bool) -> Void {
  wrappedMethod(scriptInterface, stateContext, stateMachineInstanceData, item, isLeftWeapon);
  if GorillaAkimboHands.IsDualGrip(scriptInterface.executionOwner, item) {
    let edit = stateContext.GetPermanentBoolParameter(this.GetDualWieldLoadoutEdit(stateMachineInstanceData));
    GorillaAkimboHands.Set(scriptInterface, this.IsLeftHandLogic(stateMachineInstanceData), edit.valid && edit.value ? 1 : 3,
      this.GetWeaponUnEquipDuration(scriptInterface, stateContext, stateMachineInstanceData));
  }
}

// Equip finished: both hands are refreshed, since the right hand's index depends on the left hand being filled.
@wrapMethod(EquipCycleEvents)
protected func OnExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  GorillaAkimboHands.Send(scriptInterface, false, 2, 0.0);
  GorillaAkimboHands.Send(scriptInterface, true, 2, 0.0);
  GorillaAkimboBody.Refresh(scriptInterface.executionOwner);
  GorillaAkimboDamage.Apply(GorillaAkimboConfig.Get(scriptInterface.GetGame()));
  // A pair's grenade throw is over once the left gun is equipped again (GorillaAkimboGadget.reds).
  if this.IsLeftHandLogic(this.stateMachineInstanceData) && IsDefined(GameObject.GetLeftActiveWeapon(scriptInterface.executionOwner)) {
    GorillaAkimboGadgetSystem.Get(scriptInterface.GetGame()).Stop();
  }
}

// Unequip finished: a grip weapon left alone in the right hand goes back to its own index and loses the Body scaling.
@wrapMethod(UnequipCycleEvents)
protected func OnExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  if !this.IsRightHandLogic(this.stateMachineInstanceData) && this.IsRightHandInEquippedState(stateContext)
    && !DefaultTransition.IsRightHandInUnequippingState(stateContext) {
    GorillaAkimboHands.Send(scriptInterface, false, 2, 0.0);
  }
  GorillaAkimboBody.Refresh(scriptInterface.executionOwner);
}

// Firing setting. Vanilla: semi-automatic pairs alternate on taps; holding fire, aiming or two full-auto guns fire both. Both: both guns
// fire whenever both are ready. Alternate: never both; the turn passes to the other gun half a cycle after a shot.
public abstract class GorillaAkimboFiringMode {
  // Independent firing leaves the game's shoot states alone (each gun checks its own button).
  public static func Get(scriptInterface: ref<StateGameScriptInterface>) -> GorillaAkimboFiring {
    if GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
      return GorillaAkimboFiring.Vanilla;
    }
    return GorillaAkimboConfig.Get(scriptInterface.GetGame()).firing;
  }

  public static func BothReady(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
    return DefaultTransition.HasRightWeaponEquipped(scriptInterface) && DefaultTransition.HasLeftWeaponEquipped(scriptInterface)
      && ShootTransition.IsRightWeaponReady(stateContext, scriptInterface) && ShootTransition.IsLeftWeaponReady(stateContext, scriptInterface);
  }

  // Heywood Hurricane (Double Trouble 2) ends as soon as a gun is not ready. A Carnage shot stuns V for a moment (the
  // game's own recoil, also single-wielded), which stopped Hurricane after the first shot of a Carnage pair. True
  // during that stun right after V's own shot: Hurricane's check then skips the weapons' ready test
  // (CanBeInValentinosFrenzy in GorillaAkimboVanilla.reds).
  public static func OwnShotStun(const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
    let shootState = scriptInterface.localBlackboard.GetInt(GetAllBlackboardDefs().PlayerStateMachine.ShootState);
    if shootState != EnumInt(gamePSMShootStates.ValentinosFrenzyRightOnly) && shootState != EnumInt(gamePSMShootStates.ValentinosFrenzy) {
      return false;
    }
    if !StatusEffectSystem.ObjectHasStatusEffect(scriptInterface.executionOwner, t"BaseStatusEffect.HeavyStun") {
      return false;
    }
    let system = GorillaAkimboReloadSystem.Get(scriptInterface.GetGame());
    return EngineTime.ToFloat(GameInstance.GetSimTime(scriptInterface.GetGame())) - MaxF(system.m_lastShotRight, system.m_lastShotLeft) <= 0.5;
  }

  // Alternate: whether the gun that has the turn (right when fromRight) passes it to the other one.
  public static func PassTurn(fromRight: Bool, const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
    let system = GorillaAkimboReloadSystem.Get(scriptInterface.GetGame());
    let own = fromRight ? system.m_lastShotRight : system.m_lastShotLeft;
    let other = fromRight ? system.m_lastShotLeft : system.m_lastShotRight;
    if own <= other {
      return false;
    }
    let cycle = fromRight ? ShootTransition.GetRightWeaponCycleTime(scriptInterface) : ShootTransition.GetLeftWeaponCycleTime(scriptInterface);
    return EngineTime.ToFloat(GameInstance.GetSimTime(scriptInterface.GetGame())) - own >= cycle / 2.0;
  }
}

@wrapMethod(ShootEvents)
protected final func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  let system = GorillaAkimboReloadSystem.Get(scriptInterface.GetGame());
  let now = EngineTime.ToFloat(GameInstance.GetSimTime(scriptInterface.GetGame()));
  if this.IsLeftWeaponLogic() {
    system.m_lastShotLeft = now;
  } else {
    system.m_lastShotRight = now;
  }
  // The game notes the fire button's press count for charge weapons; with independent firing, the gun's own button.
  if GorillaAkimboIndependent.Active(scriptInterface.executionOwner) {
    let fire = GorillaAkimboIndependent.FireAction(this.IsLeftWeaponLogic(), scriptInterface.GetGame());
    stateContext.SetPermanentIntParameter(this.GetLastChargePressCount(), Cast<Int32>(scriptInterface.GetActionPressCount(fire)), true);
  }
}

// A full-auto gun keeps firing each cycle while the trigger is held, whichever gun has the turn; in Alternate it only
// fires on its turn, so the turn can pass while the trigger stays down.
@wrapMethod(FullAutoDecisions)
protected final const func ToShoot(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if Equals(GorillaAkimboFiringMode.Get(scriptInterface), GorillaAkimboFiring.Alternate)
    && GameObject.IsDualWielding(scriptInterface.executionOwner) && !this.ShouldShoot(scriptInterface) {
    return false;
  }
  return wrappedMethod(stateContext, scriptInterface);
}

@wrapMethod(BothWeaponsDecisions)
protected final const func EnterCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  switch GorillaAkimboFiringMode.Get(scriptInterface) {
    case GorillaAkimboFiring.Both:
      return GorillaAkimboFiringMode.BothReady(stateContext, scriptInterface);
    case GorillaAkimboFiring.Alternate:
      return false;
    default:
      return wrappedMethod(stateContext, scriptInterface);
  }
}

@wrapMethod(BothWeaponsDecisions)
protected const func SmartExitCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  switch GorillaAkimboFiringMode.Get(scriptInterface) {
    case GorillaAkimboFiring.Both:
      return !GorillaAkimboFiringMode.BothReady(stateContext, scriptInterface);
    case GorillaAkimboFiring.Alternate:
      return true;
    default:
      return wrappedMethod(stateContext, scriptInterface);
  }
}

@wrapMethod(RightWeaponDecisions)
protected final const func ToLeftWeapon(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if NotEquals(GorillaAkimboFiringMode.Get(scriptInterface), GorillaAkimboFiring.Alternate)
    || !DefaultTransition.HasLeftWeaponEquipped(scriptInterface) || !DefaultTransition.HasRightWeaponEquipped(scriptInterface)
    || DefaultTransition.LeftWeaponHasNoAmmoOrIsReloading(scriptInterface) || DefaultTransition.RightWeaponHasNoAmmoOrIsReloading(scriptInterface) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  return ShootTransition.IsLeftWeaponReady(stateContext, scriptInterface) && GorillaAkimboFiringMode.PassTurn(true, stateContext, scriptInterface);
}

@wrapMethod(LeftWeaponDecisions)
protected final const func ToRightWeapon(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  if NotEquals(GorillaAkimboFiringMode.Get(scriptInterface), GorillaAkimboFiring.Alternate)
    || !DefaultTransition.HasLeftWeaponEquipped(scriptInterface) || !DefaultTransition.HasRightWeaponEquipped(scriptInterface)
    || DefaultTransition.LeftWeaponHasNoAmmoOrIsReloading(scriptInterface) || DefaultTransition.RightWeaponHasNoAmmoOrIsReloading(scriptInterface) {
    return wrappedMethod(stateContext, scriptInterface);
  }
  return ShootTransition.IsRightWeaponReady(stateContext, scriptInterface) && GorillaAkimboFiringMode.PassTurn(false, stateContext, scriptInterface);
}

// Double Trouble's weapon box (the red "Only affects ..." line at the top of the tooltip) gets the Gorilla Arms clause.
@wrapMethod(PerkDisplayTooltipController)
private func PerkWeaponGroupTypeToText(type: gamedataPerkWeaponGroupType) -> String {
  let text = wrappedMethod(type);
  if Equals(type, gamedataPerkWeaponGroupType.CoolDualWieldingPerkWeaponGroup) {
    text = GetLocalizedText(text) + "; " + GetLocalizedTextByKey(n"GorillaAkimbo-PerkNote");
  }
  return text;
}

public class EnglishPackage extends ModLocalizationPackage {
  protected func DefineTexts() {
    let guns = GorillaAkimboGuns.ArmsTypeNames();
    this.Text("GorillaAkimbo-ArmsLine", "Reinforced grip actuators steady " + guns + " one-handed: with Double Trouble, they can be dual-wielded.");
    this.Text("GorillaAkimbo-HintFireLeft", "Fire left gun");
    this.Text("GorillaAkimbo-HintFireRight", "Fire right gun");
    this.Text("GorillaAkimbo-HintAim", "Aim");
    this.Text("GorillaAkimbo-PerkNote", "equipping Gorilla Arms extends this effect to " + guns);
    this.Text("GorillaAkimbo-RecoilLine", "<Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">-{float_0}% recoil</> with dual-wielded " + guns + " per Attribute Point.\nCurrent total: <Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">-{float_1}%</>");
    this.Text("GorillaAkimbo-FireRateLine", "<Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">+{float_0}% fire rate</> with dual-wielded " + guns + " per Attribute Point.\nCurrent total: <Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">+{float_1}%</>");
    this.Text("GorillaAkimbo-ReloadLine", "<Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">+{float_0}% reload speed</> with dual-wielded " + guns + " per Attribute Point.\nCurrent total: <Rich color=\"TooltipText.cyberwareDescriptionHighlightColor\" style=\"Semi-Bold\">+{float_1}%</>");
  }
}

public class LocalizationProvider extends ModLocalizationProvider {
  public func GetPackage(language: CName) -> ref<ModLocalizationPackage> {
    switch language {
      case n"en-us": return new EnglishPackage();
      default: return null;
    }
  }

  public func GetFallback() -> CName {
    return n"en-us";
  }
}
