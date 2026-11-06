// Gorilla Akimbo: with Gorilla Arms equipped, SMGs and shotguns can be dual-wielded (Double Trouble still required).
// Without Gorilla Arms, dual-wielding stays vanilla (pistols and revolvers only).
module GorillaAkimbo

import Codeware.Localization.*

// Weapon types the reinforced grip adds to dual-wielding.
public func IsGripWeaponType(type: gamedataItemType) -> Bool {
  return Equals(type, gamedataItemType.Wea_SubmachineGun)
    || Equals(type, gamedataItemType.Wea_Shotgun)
    || Equals(type, gamedataItemType.Wea_ShotgunDual);
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

// At load: give SMGs and shotguns the game's dual-wield tag, and add the tooltip line to Gorilla Arms.
class GorillaAkimboTweak extends ScriptableTweak {
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
      if IsGripWeaponType(type) {
        let tags = TweakDBInterface.GetCNameArray(id + t".tags");
        if !ArrayContains(tags, n"DualWield") {
          ArrayPush(tags, n"DualWield");
          TweakDBManager.SetFlat(id + t".tags", tags);
          TweakDBManager.UpdateRecord(id);
          tagged += 1;
        }
      } else {
        if Equals(type, gamedataItemType.Cyb_StrongArms) {
          let onEquip = TweakDBInterface.GetForeignKeyArray(id + t".OnEquip");
          if !ArrayContains(onEquip, t"GorillaAkimbo.GripPackage") {
            ArrayPush(onEquip, t"GorillaAkimbo.GripPackage");
            TweakDBManager.SetFlat(id + t".OnEquip", onEquip);
            TweakDBManager.UpdateRecord(id);
            armsLines += 1;
          }
        }
      }
    }
    ModLog(n"GorillaAkimbo", s"Tagged \(tagged) SMG/shotgun records, added the tooltip line to \(armsLines) Gorilla Arms records.");
  }
}

// SMGs and shotguns only count as dual-wieldable while Gorilla Arms are equipped.
@wrapMethod(gameItemData)
public func CanDualWield(owner: wref<GameObject>) -> Bool {
  let result = wrappedMethod(owner);
  if result && IsGripWeaponType(RPGManager.GetItemType(this.GetID())) && !HasGorillaArms(owner) {
    return false;
  }
  return result;
}

// Dual-wielded SMGs and shotguns use the arm clips in GorillaAkimbo.archive (see GorillaAkimbo.archive.xl): the gun
// tips up while the magazine drops, goes down out of view, holds, and rises back once its ammo is in. Shell-by-shell
// shotguns load their shells one at a time during one reload.
// Stat changes made for a dual-wielded reload, per item. Weapon objects are made again on each draw, so they
// are kept here and taken off before the next reload of that item.
public class GorillaAkimboReloadSystem extends ScriptableSystem {
  private let m_items: array<ItemID>;
  private let m_mods: array<ref<gameStatModifierData>>;
  private let m_owners: array<StatsObjectID>;

  public static func Get(game: GameInstance) -> ref<GorillaAkimboReloadSystem> {
    return GameInstance.GetScriptableSystemsContainer(game).Get(n"GorillaAkimbo.GorillaAkimboReloadSystem") as GorillaAkimboReloadSystem;
  }

  public func Clear(item: ItemID) {
    let stats = GameInstance.GetStatsSystem(this.GetGameInstance());
    let i = ArraySize(this.m_items) - 1;
    while i >= 0 {
      if Equals(this.m_items[i], item) {
        stats.RemoveModifier(this.m_owners[i], this.m_mods[i]);
        ArrayErase(this.m_items, i);
        ArrayErase(this.m_mods, i);
        ArrayErase(this.m_owners, i);
      }
      i -= 1;
    }
  }

  public func Add(weapon: ref<WeaponObject>, stat: gamedataStatType, value: Float) {
    let owner = Cast<StatsObjectID>(weapon.GetEntityID());
    let mod = RPGManager.CreateStatModifier(stat, gameStatModifierType.Additive, value);
    GameInstance.GetStatsSystem(this.GetGameInstance()).AddModifier(owner, mod);
    ArrayPush(this.m_items, weapon.GetItemID());
    ArrayPush(this.m_mods, mod);
    ArrayPush(this.m_owners, owner);
  }
}

public abstract class GorillaAkimboReload {
  // Arm clip layout, in clip seconds. Magazine guns: a slow tip-up until OpenEnd, down out of view by DropEnd, held
  // there until HoldEnd, then the rise. Shell-by-shell guns (_02 clips): down by PlainDrop.
  public static func OpenEnd() -> Float {
    return 1.2;
  }

  public static func DropEnd() -> Float {
    return 1.5;
  }

  public static func HoldEnd() -> Float {
    return 3.5;
  }

  // Highest clip speed asked of the animation graph: very high speeds have crashed its speed node.
  public static func MaxSpeed() -> Float {
    return 8.0;
  }

  public static func PlainDrop() -> Float {
    return 0.4;
  }

  public static func RiseLength() -> Float {
    return 1.1;
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

  // The weapon's audio name, or a gun of its type when the game files have no reload sounds for it.
  public static func Audio(record: ref<WeaponItem_Record>, kind: Int32) -> CName {
    let audio = record.AudioName();
    if !GorillaAkimboSounds.Has(audio) {
      audio = GorillaAkimboSounds.Fallback(audio, record.ItemType().Type(), kind == GorillaAkimboReload.Shells());
    }
    return audio;
  }

  // Takes off the changes of an earlier reload, then sets them up again when the weapon is a dual-wielded
  // grip weapon. Returns how it reloads (Magazine or Shells), 0 when the arm clips aren't used.
  // shellTimes: for shell-by-shell guns, the times into the reload at which the game's own passes would
  // load their shells, except the last pass, which the reload's end loads as usual. passStarts, passLengths:
  // when each of the game's passes would start and how long its reload takes (one pass for magazine guns).
  public static func Prepare(weapon: ref<WeaponObject>, owner: ref<GameObject>, shellTimes: script_ref<array<Float>>,
                             passStarts: script_ref<array<Float>>, passLengths: script_ref<array<Float>>) -> Int32 {
    ArrayClear(Deref(shellTimes));
    ArrayClear(Deref(passStarts));
    ArrayClear(Deref(passLengths));
    if !IsDefined(weapon) {
      return 0;
    }
    let system = GorillaAkimboReloadSystem.Get(weapon.GetGame());
    system.Clear(weapon.GetItemID());
    let type = RPGManager.GetItemType(weapon.GetItemID());
    if !IsGripWeaponType(type) || !GameObject.IsDualWielding(owner) {
      return 0;
    }
    let stats = GameInstance.GetStatsSystem(weapon.GetGame());
    let id = Cast<StatsObjectID>(weapon.GetEntityID());
    let perReload = stats.GetStatValue(id, gamedataStatType.ReloadAmount);
    let kind = GorillaAkimboReload.Magazine();
    ArrayPush(Deref(passStarts), 0.0);
    ArrayPush(Deref(passLengths), stats.GetStatValue(id, weapon.IsMagazineEmpty() ? gamedataStatType.EmptyReloadTime : gamedataStatType.ReloadTime));
    if perReload > 0.0 {
      // Shell by shell: one reload state as long as the game's own passes would take, so the arm stays down
      // throughout. Each pass after the first takes its reload time plus the previous pass's end time (the
      // reload state lasts that long before the next pass starts); an empty gun's first pass ends after the
      // empty end time instead.
      let empty = weapon.IsMagazineEmpty();
      let missing = MaxF(Cast<Float>(WeaponObject.GetMagazineCapacity(weapon)) - Cast<Float>(WeaponObject.GetMagazineAmmoCount(weapon)), 1.0);
      let passes = CeilF(missing / perReload);
      let reloadTime = stats.GetStatValue(id, gamedataStatType.ReloadTime);
      let endTime = stats.GetStatValue(id, gamedataStatType.ReloadEndTime);
      let first = empty ? stats.GetStatValue(id, gamedataStatType.EmptyReloadTime) : reloadTime;
      let time = first;
      let i = 1;
      while i < passes {
        ArrayPush(Deref(shellTimes), time);
        time += i == 1 && empty ? stats.GetStatValue(id, gamedataStatType.EmptyReloadEndTime) : endTime;
        ArrayPush(Deref(passStarts), time);
        ArrayPush(Deref(passLengths), reloadTime);
        time += reloadTime;
        i += 1;
      }
      system.Add(weapon, gamedataStatType.ReloadTime, time - first);
      system.Add(weapon, gamedataStatType.EmptyReloadTime, time - first);
      kind = GorillaAkimboReload.Shells();
    }
    // The reload state lasts until the rise is done, so its end doesn't cut the clip. The gun can fire as
    // soon as the ammo is in: firing ends the reload state.
    system.Add(weapon, gamedataStatType.ReloadEndTime, GorillaAkimboReload.RiseLength());
    system.Add(weapon, gamedataStatType.EmptyReloadEndTime, GorillaAkimboReload.RiseLength());
    return kind;
  }

  // Loads one pass of shells: up to ReloadAmount, as many as fit and as the player has.
  public static func LoadPass(weapon: ref<WeaponObject>, owner: ref<GameObject>) {
    let ts = GameInstance.GetTransactionSystem(weapon.GetGame());
    let ammo = WeaponObject.GetAmmoType(weapon);
    let perReload = Cast<Int32>(GameInstance.GetStatsSystem(weapon.GetGame()).GetStatValue(Cast<StatsObjectID>(weapon.GetEntityID()), gamedataStatType.ReloadAmount));
    let mag = Cast<Int32>(WeaponObject.GetMagazineAmmoCount(weapon));
    let room = Cast<Int32>(WeaponObject.GetMagazineCapacity(weapon)) - mag;
    let count = Min(Min(perReload, room), ts.GetItemQuantity(owner, ammo));
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
private let m_gorillaShells: Bool;

@addField(ReloadEvents)
private let m_gorillaSoundTimes: array<Float>;

@addField(ReloadEvents)
private let m_gorillaSoundNames: array<CName>;

@addField(ReloadEvents)
private let m_gorillaMagOut: Float;

@wrapMethod(ReloadEvents)
protected final func OnEnter(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  let weapon = this.GetWeaponObject(scriptInterface);
  let passStarts: array<Float>;
  let passLengths: array<Float>;
  let kind = GorillaAkimboReload.Prepare(weapon, scriptInterface.executionOwner, this.m_gorillaShellTimes, passStarts, passLengths);
  this.m_gorillaTimed = kind > 0;
  if this.m_gorillaTimed {
    GorillaAkimboReload.Sounds(weapon, this.m_weaponRecord, kind, passStarts, passLengths, this.m_gorillaSoundTimes, this.m_gorillaSoundNames);
  } else {
    ArrayClear(this.m_gorillaSoundTimes);
    ArrayClear(this.m_gorillaSoundNames);
  }
  this.m_gorillaShells = kind == GorillaAkimboReload.Shells();
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
  if this.m_gorillaTimed && IsDefined(this.m_randomSync) {
    this.m_randomSync.value = GorillaAkimboReload.Variant(kind, this.m_randomSync.value);
    scriptInterface.SetAnimationParameterFeature(this.IsRightWeaponLogic() ? n"RandomSync" : n"LeftRandomSync", this.m_randomSync);
  }
}

// Re-times the arm clip as the reload goes, against the duration the game itself checks for the ammo.
@wrapMethod(ReloadEvents)
protected final func OnUpdate(timeDelta: Float, stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(timeDelta, stateContext, scriptInterface);
  if !this.m_gorillaTimed {
    return;
  }
  let duration = stateContext.GetPermanentFloatParameter(this.GetReloadLogicalDuration());
  if !duration.valid {
    return;
  }
  let speed = GorillaAkimboReload.Speed(this.GetInStateTime(), duration.value, this.m_gorillaMagOut, this.m_gorillaShells);
  if AbsF(speed - this.m_gorillaSpeed) > 0.001 {
    this.m_gorillaSpeed = speed;
    this.m_animReloadSpeed.reloadSpeed = speed;
    this.m_animReloadSpeed.emptyReloadSpeed = speed;
    scriptInterface.SetAnimationParameterFeature(this.IsRightWeaponLogic() ? n"RightReloadSpeed" : n"LeftReloadSpeed", this.m_animReloadSpeed);
  }
  // Shell by shell: the passes before the last load as the game's own would, so the counter fills shell by
  // shell and firing mid-reload keeps what is in.
  while ArraySize(this.m_gorillaShellTimes) > 0 && this.GetInStateTime() >= this.m_gorillaShellTimes[0] {
    ArrayErase(this.m_gorillaShellTimes, 0);
    GorillaAkimboReload.LoadPass(this.GetWeaponObject(scriptInterface), scriptInterface.executionOwner);
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

  // Sends the hand's item handling again with the dual-wield index. state: the itemState just sent.
  public static func Send(owner: ref<GameObject>, left: Bool, state: Int32, duration: Float) {
    let ts = GameInstance.GetTransactionSystem(owner.GetGame());
    let item = ts.GetItemInSlot(owner, left ? t"AttachmentSlots.WeaponLeft" : t"AttachmentSlots.WeaponRight");
    if !IsDefined(item) || !IsGripWeaponType(RPGManager.GetItemType(item.GetItemID())) {
      return;
    }
    let dual = IsDefined(ts.GetItemInSlot(owner, t"AttachmentSlots.WeaponLeft"))
      && IsDefined(ts.GetItemInSlot(owner, t"AttachmentSlots.WeaponRight"));
    let feature = new AnimFeature_EquipUnequipItem();
    feature.stateTransitionDuration = duration;
    feature.itemState = state;
    feature.itemType = dual ? GorillaAkimboHands.OneHandedIndex()
      : TweakDBInterface.GetItemRecord(ItemID.GetTDBID(item.GetItemID())).ItemType().AnimFeatureIndex();
    AnimationControllerComponent.ApplyFeatureToReplicate(owner, left ? n"leftHandItemHandling" : n"rightHandItemHandling", feature);
  }
}

@wrapMethod(EquipmentBaseTransition)
protected final const func HandleWeaponEquip(scriptInterface: ref<StateGameScriptInterface>, stateContext: ref<StateContext>, stateMachineInstanceData: StateMachineInstanceData, item: ItemID, isLeftWeapon: Bool) -> Void {
  wrappedMethod(scriptInterface, stateContext, stateMachineInstanceData, item, isLeftWeapon);
  let owner = scriptInterface.executionOwner;
  let duration = scriptInterface.GetStatsSystem().GetStatValue(Cast<StatsObjectID>(owner.GetEntityID()), gamedataStatType.EquipDuration);
  GorillaAkimboHands.Send(owner, this.IsLeftHandLogic(stateMachineInstanceData), 1, duration);
}

// Equip finished: both hands are refreshed, since the right hand's index depends on the left hand being filled.
@wrapMethod(EquipCycleEvents)
protected func OnExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  GorillaAkimboHands.Send(scriptInterface.executionOwner, false, 2, 0.0);
  GorillaAkimboHands.Send(scriptInterface.executionOwner, true, 2, 0.0);
}

// Unequip finished: a grip weapon left alone in the right hand goes back to its own index.
@wrapMethod(UnequipCycleEvents)
protected func OnExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  if !this.IsRightHandLogic(this.stateMachineInstanceData) {
    GorillaAkimboHands.Send(scriptInterface.executionOwner, false, 2, 0.0);
  }
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
    this.Text("GorillaAkimbo-ArmsLine", "Reinforced grip actuators steady SMGs and shotguns one-handed: with Double Trouble, they can be dual-wielded.");
    this.Text("GorillaAkimbo-PerkNote", "equipping Gorilla Arms extends this to SMGs and Shotguns");
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
