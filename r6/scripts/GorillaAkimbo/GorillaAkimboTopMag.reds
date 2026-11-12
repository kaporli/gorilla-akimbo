// Top-magazine guns (the Shingen) reload two-handed while dual-wielded: the other hand, still holding
// its gun, knocks the magazine out, then both guns go down while the new magazine goes in and come back up.
// One arm clip drives both arms: during the reload the left hand reports a two-handed item type, which turns off
// the dual-wield graph's left-arm overlay, so the right hand's part of the graph poses both arms.
// A right gun's clip plays as the right hand's reload (reload, _01, _02); a left gun's clip plays in the right
// hand's part as an empty reload (empty_reload, _01, _02), a slot right-hand reloads never use while
// dual-wielding top-magazine guns, because their reloads always play as non-empty reloads.
// Each clip is the gun's own reload animation length; the gun's own reload animation plays alongside at the
// same speed. While dual-wielded, the gun's magazine plays its own track set (see Family): seated until the hit
// at f25, then knocked off along the hit.
module GorillaAkimbo

public abstract class GorillaAkimboTopMag {
  public static func None() -> Int32 {
    return 0;
  }

  // Which top-magazine gun this is (0 when it isn't one), by its sound set (shared by every variant, iconic and
  // modded copy). Only guns whose two-handed clips ship count: see top-mag in tools/anim/weapons.json.
  public static func Kind(weapon: ref<WeaponObject>) -> Int32 {
    if !IsDefined(weapon) {
      return GorillaAkimboTopMag.None();
    }
    let record = weapon.GetWeaponRecord();
    if !IsDefined(record) {
      return GorillaAkimboTopMag.None();
    }
    return GorillaAkimboGuns.TopMagKind(record.AudioName());
  }

  // Clip seconds at which the new magazine is seated (the reload's ammo lands then), from the gun's own reload
  // animation. A pair's clip runs to the later gun's.
  public static func Seated(kind: Int32) -> Float {
    return GorillaAkimboGuns.TopMagSeated(kind);
  }

  // Clip length in seconds.
  public static func Length(kind: Int32) -> Float {
    return GorillaAkimboGuns.TopMagLength(kind);
  }

  // Clip seconds before the end at which the arms are handed back to the dual-wield idle (6 frames).
  public static func HandBack() -> Float {
    return 6.0 / 30.0;
  }

  // Clip seconds at which both guns are out of view. The other gun's ammo starts going in at Down; the clip is held
  // between HoldStart and HoldEnd until that ammo is in.
  public static func Down(kind: Int32) -> Float {
    return GorillaAkimboGuns.TopMagDown(kind);
  }

  public static func HoldStart(kind: Int32) -> Float {
    return GorillaAkimboGuns.TopMagHoldStart(kind);
  }

  public static func HoldEnd(kind: Int32) -> Float {
    return GorillaAkimboGuns.TopMagHoldEnd(kind);
  }

  // Seconds into the reload at which the gun's own animation reaches gun seconds t (for its sounds). The gun's
  // animation runs at the arms' speed.
  public static func GunTime(kind: Int32, speed: Float, t: Float) -> Float {
    return t / speed;
  }

  // The long gun in the other hand, by its sound set: n"None" for any other gun. Beside these the clips are lupper,
  // axe and hang, so the magazine leaves along a different hit.
  public static func LongPartner(weapon: ref<WeaponObject>) -> CName {
    if !IsDefined(weapon) {
      return n"None";
    }
    let record = weapon.GetWeaponRecord();
    if !IsDefined(record) {
      return n"None";
    }
    return GorillaAkimboGuns.LongPartner(record.AudioName());
  }

  // The magazine track set of this hand's gun, as the anim wrapper on the gun that selects it in archive.xl: a
  // pair's, one beside a long shotgun, one beside any other gun (by the slot the gun is in). n"None" when the
  // reload isn't two-handed; the magazine then plays the gun's own track.
  public static func Family(owner: ref<GameObject>, weapon: ref<WeaponObject>, left: Bool) -> CName {
    if GorillaAkimboTopMag.Pair(owner, weapon, left) != GorillaAkimboTopMag.None() {
      return left ? n"gorillaakimbo_mag_pair_left" : n"gorillaakimbo_mag_pair_right";
    }
    if GorillaAkimboTopMag.Single(owner, weapon, left) == GorillaAkimboTopMag.None() {
      return n"None";
    }
    if NotEquals(GorillaAkimboTopMag.LongPartner(GorillaAkimboTopMag.Weapon(owner, !left)), n"None") {
      return left ? n"gorillaakimbo_mag_long_left" : n"gorillaakimbo_mag_long_right";
    }
    return left ? n"gorillaakimbo_mag_smg_left" : n"gorillaakimbo_mag_smg_right";
  }

  // Turns on one magazine track set on a gun (its parts get the wrapper too), the others off; n"None" turns all off.
  public static func SetFamily(weapon: ref<WeaponObject>, family: CName) {
    if !IsDefined(weapon) {
      return;
    }
    let names: array<CName> = [n"gorillaakimbo_mag_long_left", n"gorillaakimbo_mag_long_right", n"gorillaakimbo_mag_smg_left", n"gorillaakimbo_mag_smg_right", n"gorillaakimbo_mag_pair_left", n"gorillaakimbo_mag_pair_right"];
    let i = 0;
    while i < ArraySize(names) {
      AnimationControllerComponent.SetAnimWrapperWeight(weapon, names[i], Equals(names[i], family) ? 1.0 : 0.0);
      i += 1;
    }
  }

  public static func Same(a: ref<WeaponObject>, b: ref<WeaponObject>) -> Bool {
    if !IsDefined(a) || !IsDefined(b) {
      return !IsDefined(a) && !IsDefined(b);
    }
    return Equals(a.GetEntityID(), b.GetEntityID());
  }

  public static func Weapon(owner: ref<GameObject>, left: Bool) -> ref<WeaponObject> {
    return GameInstance.GetTransactionSystem(owner.GetGame()).GetItemInSlot(owner, left ? t"AttachmentSlots.WeaponLeft" : t"AttachmentSlots.WeaponRight") as WeaponObject;
  }

  // The top-magazine kind of this hand's gun when its reload plays two-handed: dual-wielding, a grip weapon,
  // the other gun not also a top-magazine gun (a pair reloads together, see Pair).
  public static func Single(owner: ref<GameObject>, weapon: ref<WeaponObject>, left: Bool) -> Int32 {
    if !IsDefined(weapon) || !GameObject.IsDualWielding(owner) || !GorillaAkimboHands.IsDualGrip(owner, weapon.GetItemID()) {
      return GorillaAkimboTopMag.None();
    }
    let kind = GorillaAkimboTopMag.Kind(weapon);
    if kind == GorillaAkimboTopMag.None() || GorillaAkimboTopMag.Kind(GorillaAkimboTopMag.Weapon(owner, !left)) != GorillaAkimboTopMag.None() {
      return GorillaAkimboTopMag.None();
    }
    return kind;
  }

  // Both guns are top-magazine guns: they reload together with a pair clip. Returns the kind of the slower one
  // (its clip timing rules), None otherwise.
  public static func Pair(owner: ref<GameObject>, weapon: ref<WeaponObject>, left: Bool) -> Int32 {
    if !IsDefined(weapon) || !GameObject.IsDualWielding(owner) || !GorillaAkimboHands.IsDualGrip(owner, weapon.GetItemID()) {
      return GorillaAkimboTopMag.None();
    }
    let mine = GorillaAkimboTopMag.Kind(weapon);
    let other = GorillaAkimboTopMag.Kind(GorillaAkimboTopMag.Weapon(owner, !left));
    if mine == GorillaAkimboTopMag.None() || other == GorillaAkimboTopMag.None() {
      return GorillaAkimboTopMag.None();
    }
    return GorillaAkimboTopMag.Seated(other) > GorillaAkimboTopMag.Seated(mine) ? other : mine;
  }

  // The reload time of a gun as its reload would start now (empty or not).
  public static func Duration(weapon: ref<WeaponObject>) -> Float {
    if !IsDefined(weapon) {
      return 0.0;
    }
    let stats = GameInstance.GetStatsSystem(weapon.GetGame());
    let id = Cast<StatsObjectID>(weapon.GetEntityID());
    return stats.GetStatValue(id, weapon.IsMagazineEmpty() ? gamedataStatType.EmptyReloadTime : gamedataStatType.ReloadTime);
  }

  // Adds a sound to a time-sorted list.
  public static func InsertSound(times: script_ref<array<Float>>, names: script_ref<array<CName>>, time: Float, name: CName) {
    let i = 0;
    while i < ArraySize(Deref(times)) && Deref(times)[i] <= time {
      i += 1;
    }
    ArrayInsert(Deref(times), i, time);
    ArrayInsert(Deref(names), i, name);
  }

  // Sets the left hand's item type: two-handed (2) while a top-magazine clip poses both arms, the dual-wield
  // index (1) otherwise. `blend` is the transition time in seconds.
  public static func LeftHand(scriptInterface: ref<StateGameScriptInterface>, twoHanded: Bool, blend: Float) {
    let feature = new AnimFeature_EquipUnequipItem();
    feature.stateTransitionDuration = blend;
    feature.itemState = 2;
    feature.itemType = twoHanded ? 2 : GorillaAkimboHands.OneHandedIndex();
    scriptInterface.SetAnimationParameterFeature(n"leftHandItemHandling", feature, scriptInterface.executionOwner);
  }
}

// Which hand is in a two-handed top-magazine reload, which hands are reloading at all, and the reloads asked for
// while a hand was busy (they start when it is done).
public class GorillaAkimboTopMagSystem extends ScriptableSystem {
  public let busy: Bool;
  public let busyLeft: Bool;
  public let busyUntil: Float;
  public let reloadingLeft: Bool;
  public let reloadingRight: Bool;
  public let pendingLeft: Bool;
  public let pendingRight: Bool;
  // A pair reload: the other gun is reloaded from the driving hand's reload (its own reload state isn't used).
  public let pair: Bool;
  public let pairOther: wref<WeaponObject>;
  public let pairOtherAt: Float;
  // Until this sim time, a queued reload waits for the top-magazine gun's reload to start (see EnterCondition).
  public let joinWaitUntil: Float;
  // The magazine track set each hand's gun has (see GorillaAkimboTopMag.Family), and that gun.
  public let familyLeft: CName;
  public let familyRight: CName;
  public let familyWeaponLeft: wref<WeaponObject>;
  public let familyWeaponRight: wref<WeaponObject>;

  public static func Get(game: GameInstance) -> ref<GorillaAkimboTopMagSystem> {
    return GameInstance.GetScriptableSystemsContainer(game).Get(n"GorillaAkimbo.GorillaAkimboTopMagSystem") as GorillaAkimboTopMagSystem;
  }

  // A hand is in a two-handed reload. Lapses on its own after the clip's length, so a reload cut off without
  // its exit (a save loaded mid-reload) can't keep the guns blocked.
  public static func Busy(game: GameInstance) -> Bool {
    let system = GorillaAkimboTopMagSystem.Get(game);
    return IsDefined(system) && system.busy && EngineTime.ToFloat(GameInstance.GetSimTime(game)) < system.busyUntil;
  }

  public func Reloading(left: Bool) -> Bool {
    return left ? this.reloadingLeft : this.reloadingRight;
  }

  public func SetReloading(left: Bool, value: Bool) {
    if left {
      this.reloadingLeft = value;
    } else {
      this.reloadingRight = value;
    }
  }

  public func Pending(left: Bool) -> Bool {
    return left ? this.pendingLeft : this.pendingRight;
  }

  public func SetPending(left: Bool, value: Bool) {
    if left {
      this.pendingLeft = value;
    } else {
      this.pendingRight = value;
    }
  }

  // Sets the magazine track set of the gun in this hand, before any reload starts (the wrapper reaches the gun as a
  // queued event). Clears it on the gun that had it when the gun changed, unless that gun is now in the other hand.
  public func UpdateFamily(owner: ref<GameObject>, weapon: ref<WeaponObject>, left: Bool) {
    let family = GorillaAkimboTopMag.Family(owner, weapon, left);
    let old: wref<WeaponObject> = left ? this.familyWeaponLeft : this.familyWeaponRight;
    let oldFamily = left ? this.familyLeft : this.familyRight;
    let same = GorillaAkimboTopMag.Same(old, weapon);
    if same && Equals(oldFamily, family) {
      return;
    }
    if !same && !GorillaAkimboTopMag.Same(old, left ? this.familyWeaponRight : this.familyWeaponLeft) {
      GorillaAkimboTopMag.SetFamily(old, n"None");
    }
    GorillaAkimboTopMag.SetFamily(weapon, family);
    if left {
      this.familyLeft = family;
      this.familyWeaponLeft = weapon;
    } else {
      this.familyRight = family;
      this.familyWeaponRight = weapon;
    }
    if IsNameValid(family) {
      let other = GorillaAkimboTopMag.Weapon(owner, !left);
      let audio = IsDefined(other) && IsDefined(other.GetWeaponRecord()) ? other.GetWeaponRecord().AudioName() : n"None";
      ModLog(n"GorillaAkimbo", s"Magazine set \(NameToString(family)), other gun's sound set \(NameToString(audio)).");
    }
  }

  public func Reset() {
    this.busy = false;
    this.reloadingLeft = false;
    this.reloadingRight = false;
    this.pendingLeft = false;
    this.pendingRight = false;
  }
}

@addField(ReloadEvents)
private let m_gorillaTopMag: Bool;

@addField(ReloadEvents)
private let m_gorillaTopMagKind: Int32;

@addField(ReloadEvents)
private let m_gorillaTopMagPair: Bool;

// The clip's own speed, and how far it has played (clip seconds), for the hold.
@addField(ReloadEvents)
private let m_gorillaTopMagSpeed: Float;

@addField(ReloadEvents)
private let m_gorillaTopMagClip: Float;

// Set once the arms were handed back to the dual-wield idle, a few frames before the clip ends.
@addField(ReloadEvents)
private let m_gorillaTopMagHandedBack: Bool;

// The other gun reloads in the same down time (see GorillaTopMagJoin): its shells and when its ammo is all in.
@addField(ReloadEvents)
private let m_gorillaJoin: Bool;

@addField(ReloadEvents)
private let m_gorillaJoinOther: wref<WeaponObject>;

@addField(ReloadEvents)
private let m_gorillaJoinShellTimes: array<Float>;

@addField(ReloadEvents)
private let m_gorillaJoinShellCounts: array<Int32>;

@addField(ReloadEvents)
private let m_gorillaJoinDone: Float;

// Sets up a two-handed top-magazine reload before the game's own OnEnter: no extra reload time, the clip speed
// that seats the new magazine as the ammo lands, the reload state kept until the clip ends, and the gun's own
// reload sounds at that speed. Returns false when the reload isn't one.
@addMethod(ReloadEvents)
private final func GorillaTopMagPrepare(weapon: ref<WeaponObject>, scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  let owner = scriptInterface.executionOwner;
  let left = this.IsLeftWeaponLogic();
  let kind = GorillaAkimboTopMag.Single(owner, weapon, left);
  let pairKind = GorillaAkimboTopMag.Pair(owner, weapon, left);
  if kind == GorillaAkimboTopMag.None() && pairKind == GorillaAkimboTopMag.None() {
    return false;
  }
  this.m_gorillaTopMagPair = pairKind != GorillaAkimboTopMag.None();
  if this.m_gorillaTopMagPair {
    kind = pairKind;
  }
  this.m_gorillaTopMagKind = kind;
  let system = GorillaAkimboReloadSystem.Get(weapon.GetGame());
  system.Clear(weapon.GetItemID(), n"reload");
  GorillaAkimboBody.Apply(weapon, owner);
  let stats = scriptInterface.GetStatsSystem();
  let id = Cast<StatsObjectID>(weapon.GetEntityID());
  let empty = weapon.IsMagazineEmpty();
  let duration = stats.GetStatValue(id, empty ? gamedataStatType.EmptyReloadTime : gamedataStatType.ReloadTime);
  // A pair plays at one speed for both guns, so the slower gun's ammo lands with the later seat.
  let slowest = duration;
  if this.m_gorillaTopMagPair {
    slowest = MaxF(duration, GorillaAkimboTopMag.Duration(GorillaAkimboTopMag.Weapon(owner, !left)));
  }
  let speed = ClampF(GorillaAkimboTopMag.Seated(kind) / MaxF(slowest, 0.05), 0.3, GorillaAkimboReload.MaxSpeed());
  let extra = GorillaAkimboTopMag.Length(kind) / speed - duration - stats.GetStatValue(id, empty ? gamedataStatType.EmptyReloadEndTime : gamedataStatType.ReloadEndTime);
  if extra > 0.0 {
    system.Add(weapon, n"reload", gamedataStatType.ReloadEndTime, gameStatModifierType.Additive, extra);
    system.Add(weapon, n"reload", gamedataStatType.EmptyReloadEndTime, gameStatModifierType.Additive, extra);
  }
  this.m_animReloadData.amountToReload = 0;
  this.m_animReloadData.loopDuration = stats.GetStatValue(id, gamedataStatType.ReloadTime);
  this.m_animReloadData.emptyDuration = stats.GetStatValue(id, gamedataStatType.EmptyReloadTime);
  this.m_animReloadSpeed.reloadSpeed = speed;
  this.m_animReloadSpeed.emptyReloadSpeed = speed;
  this.m_animReloadDataDirty = true;
  this.m_animReloadSpeedDirty = true;
  this.m_gorillaSpeed = speed;
  this.m_gorillaTopMagSpeed = speed;
  this.m_gorillaTopMagClip = 0.0;
  this.m_gorillaTopMagHandedBack = false;
  this.m_gorillaJoin = false;
  ArrayClear(this.m_gorillaJoinShellTimes);
  ArrayClear(this.m_gorillaJoinShellCounts);
  // The gun's own reload sounds, in its clip seconds, at this speed.
  let times: array<Float>;
  let names: array<CName>;
  GorillaAkimboSounds.Get(GorillaAkimboReload.Audio(this.m_weaponRecord, GorillaAkimboReload.Magazine()), empty, times, names);
  ArrayClear(this.m_gorillaSoundTimes);
  ArrayClear(this.m_gorillaSoundNames);
  let i = 0;
  while i < ArraySize(times) {
    ArrayPush(this.m_gorillaSoundTimes, GorillaAkimboTopMag.GunTime(kind, speed, times[i]));
    ArrayPush(this.m_gorillaSoundNames, names[i]);
    i += 1;
  }
  // The magazine track sets, before the reload event (also set ahead in EnterCondition).
  let topMag = GorillaAkimboTopMagSystem.Get(weapon.GetGame());
  topMag.UpdateFamily(owner, weapon, left);
  if this.m_gorillaTopMagPair {
    topMag.UpdateFamily(owner, GorillaAkimboTopMag.Weapon(owner, !left), !left);
  }
  return true;
}

// After the game's own OnEnter: turn off the left-arm overlay and start the clip. A right gun's clip is its own
// reload, played as a non-empty one; a left gun's clip is started in the right hand's part of the graph.
@addMethod(ReloadEvents)
private final func GorillaTopMagStart(scriptInterface: ref<StateGameScriptInterface>) {
  let owner = scriptInterface.executionOwner;
  let topMag = GorillaAkimboTopMagSystem.Get(owner.GetGame());
  topMag.busy = true;
  topMag.busyLeft = this.IsLeftWeaponLogic();
  topMag.busyUntil = EngineTime.ToFloat(GameInstance.GetSimTime(owner.GetGame())) + GorillaAkimboTopMag.Length(this.m_gorillaTopMagKind) / MaxF(this.m_gorillaSpeed, 0.05) + 1.0;
  GorillaAkimboTopMag.LeftHand(scriptInterface, true, 0.0);
  topMag.pair = this.m_gorillaTopMagPair;
  topMag.pairOtherAt = -1.0;
  // One line per reload, to match a recording to its clips: the pick index selects the clip in the arm set and the
  // track in the magazine set alike.
  let pick = IsDefined(this.m_randomSync) ? this.m_randomSync.value : -1;
  let hand: String = this.IsLeftWeaponLogic() ? "left" : "right";
  let magSet: CName = this.IsLeftWeaponLogic() ? topMag.familyLeft : topMag.familyRight;
  let pairText: String = this.m_gorillaTopMagPair ? "yes" : "no";
  ModLog(n"GorillaAkimbo", s"Top-magazine reload: \(hand) hand, pick \(pick), magazine set \(NameToString(magSet)), pair \(pairText), speed \(this.m_gorillaSpeed).");
  if this.m_gorillaTopMagPair {
    // The other gun reloads alongside, at the same speed: its own reload animation, sounds and ammo.
    let other = GorillaAkimboTopMag.Weapon(owner, !this.IsLeftWeaponLogic());
    let otherSpeed = new AnimFeature_WeaponReloadSpeedData();
    otherSpeed.reloadSpeed = this.m_gorillaSpeed;
    otherSpeed.emptyReloadSpeed = this.m_gorillaSpeed;
    scriptInterface.SetAnimationParameterFeature(this.IsLeftWeaponLogic() ? n"RightReloadSpeed" : n"LeftReloadSpeed", otherSpeed);
    topMag.pairOther = other;
    // Only the reloading hand's weapon gets the game's reload event and features; the other gun's own reload
    // animation (and so its magazine track) gets its own, on its side's channels, same variant as the clip.
    if IsDefined(other) {
      let otherLeft = !this.IsLeftWeaponLogic();
      let otherData = new AnimFeature_WeaponReload();
      otherData.emptyReload = false;
      otherData.amountToReload = 0;
      otherData.continueLoop = false;
      otherData.loopDuration = this.m_animReloadData.loopDuration;
      otherData.emptyDuration = this.m_animReloadData.emptyDuration;
      AnimationControllerComponent.ApplyFeature(other, otherLeft ? n"LeftReloadData" : n"RightReloadData", otherData);
      AnimationControllerComponent.ApplyFeature(other, otherLeft ? n"LeftReloadSpeed" : n"RightReloadSpeed", otherSpeed);
      if IsDefined(this.m_randomSync) {
        AnimationControllerComponent.ApplyFeature(other, otherLeft ? n"LeftRandomSync" : n"RandomSync", this.m_randomSync);
      }
      AnimationControllerComponent.PushEvent(other, otherLeft ? n"LeftReload" : n"RightReload");
    }
    if IsDefined(other) && WeaponObject.CanReload(other) {
      let otherEmpty = other.IsMagazineEmpty();
      topMag.pairOtherAt = other.StartReload(GorillaAkimboTopMag.Duration(other));
      let times: array<Float>;
      let names: array<CName>;
      GorillaAkimboSounds.Get(GorillaAkimboReload.Audio(other.GetWeaponRecord(), GorillaAkimboReload.Magazine()), otherEmpty, times, names);
      let i = 0;
      while i < ArraySize(times) {
        GorillaAkimboTopMag.InsertSound(this.m_gorillaSoundTimes, this.m_gorillaSoundNames, GorillaAkimboTopMag.GunTime(this.m_gorillaTopMagKind, this.m_gorillaTopMagSpeed, times[i]), names[i]);
        i += 1;
      }
    }
  }
  this.GorillaTopMagJoin(scriptInterface);
  if !this.IsLeftWeaponLogic() {
    this.m_animReloadData.emptyReload = false;
    scriptInterface.SetAnimationParameterFeature(n"RightReloadData", this.m_animReloadData);
    scriptInterface.SetAnimationParameterFeature(n"RightReloadSpeed", this.m_animReloadSpeed);
    // A pair's left gun plays the same variant as the clip.
    if this.m_gorillaTopMagPair && IsDefined(this.m_randomSync) {
      scriptInterface.SetAnimationParameterFeature(n"LeftRandomSync", this.m_randomSync);
    }
    return;
  }
  let data = new AnimFeature_WeaponReload();
  // A left gun's own clip plays as an empty reload; a pair clip as a non-empty one, like a right gun's.
  data.emptyReload = !this.m_gorillaTopMagPair;
  data.amountToReload = 0;
  data.continueLoop = false;
  data.loopDuration = this.m_animReloadData.loopDuration;
  data.emptyDuration = this.m_animReloadData.emptyDuration;
  let speed = new AnimFeature_WeaponReloadSpeedData();
  speed.reloadSpeed = this.m_animReloadSpeed.reloadSpeed;
  speed.emptyReloadSpeed = this.m_animReloadSpeed.emptyReloadSpeed;
  scriptInterface.SetAnimationParameterFeature(n"RightReloadData", data);
  scriptInterface.SetAnimationParameterFeature(n"RightReloadSpeed", speed);
  // The left gun's own animation reads the left channel.
  scriptInterface.SetAnimationParameterFeature(n"LeftReloadSpeed", speed);
  if IsDefined(this.m_randomSync) {
    scriptInterface.SetAnimationParameterFeature(n"RandomSync", this.m_randomSync);
  }
  scriptInterface.PushAnimationEvent(n"RightReload");
}

// When the reload state ends: the right hand's part of the graph leaves a left gun's clip, the left-arm overlay
// comes back, and a reload the other hand asked for meanwhile starts.
@addMethod(ReloadEvents)
private final func GorillaTopMagEnd(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) {
  let owner = scriptInterface.executionOwner;
  let topMag = GorillaAkimboTopMagSystem.Get(owner.GetGame());
  if !this.m_gorillaTopMagHandedBack {
    this.GorillaTopMagHandBack(scriptInterface);
  }
  this.GorillaTopMagFinishOther(topMag);
  topMag.pair = false;
  topMag.busy = false;
  this.m_gorillaTopMag = false;
  this.m_gorillaJoin = false;
  ArrayClear(this.m_gorillaJoinShellTimes);
  ArrayClear(this.m_gorillaJoinShellCounts);
  // The right hand's own reload data again, so its next reload isn't read as an empty one.
  this.m_animReloadDataDirty = true;
  stateContext.SetConditionBoolParameter(this.IsLeftWeaponLogic() ? n"RightReloadDataDirty" : n"LeftReloadDataDirty", true, true);
}

// The arms go back to the dual-wield idle: the left gun's clip is ended in the graph and the left hand is one-handed
// again, blended over HandBack() so the idle's own layers come in while the arms still move.
@addMethod(ReloadEvents)
private final func GorillaTopMagHandBack(scriptInterface: ref<StateGameScriptInterface>) {
  this.m_gorillaTopMagHandedBack = true;
  if this.IsLeftWeaponLogic() {
    scriptInterface.PushAnimationEvent(n"InterruptReload");
  }
  GorillaAkimboTopMag.LeftHand(scriptInterface, false, GorillaAkimboTopMag.HandBack());
}

// A pair's other gun, or a magazine gun that joined, gets its ammo once its own reload time has passed (or when the
// reload ends early).
@addMethod(ReloadEvents)
private final func GorillaTopMagFinishOther(topMag: ref<GorillaAkimboTopMagSystem>) {
  let other = topMag.pairOther;
  if topMag.pairOtherAt >= 0.0 && IsDefined(other) {
    other.StopReload(gameweaponReloadStatus.Standard);
  }
  topMag.pairOtherAt = -1.0;
}

// The other gun (an SMG or shotgun, not a top-magazine gun) reloads in the same down time when its reload was asked
// for or it ran empty before the guns are down: its ammo starts going in once both guns are out of view, and they
// stay down until it is all in (a shell-by-shell shotgun's last shell), then come up together. Its own reload state
// isn't used. Called at the start and on each update until the guns are down.
@addMethod(ReloadEvents)
private final func GorillaTopMagJoin(scriptInterface: ref<StateGameScriptInterface>) {
  let kind = this.m_gorillaTopMagKind;
  if this.m_gorillaTopMagPair || this.m_gorillaJoin || this.m_gorillaTopMagClip >= GorillaAkimboTopMag.Down(kind) {
    return;
  }
  let owner = scriptInterface.executionOwner;
  let left = this.IsLeftWeaponLogic();
  let topMag = GorillaAkimboTopMagSystem.Get(owner.GetGame());
  let other = GorillaAkimboTopMag.Weapon(owner, !left);
  if !IsDefined(other) || (!topMag.Pending(!left) && !other.IsMagazineEmpty()) {
    return;
  }
  if !WeaponObject.CanReload(other) || !GorillaAkimboHands.IsDualGrip(owner, other.GetItemID()) {
    return;
  }
  let shellTimes: array<Float>;
  let shellCounts: array<Int32>;
  let passStarts: array<Float>;
  let passLengths: array<Float>;
  let otherKind = GorillaAkimboReload.Prepare(other, owner, shellTimes, shellCounts, passStarts, passLengths);
  // Prepare's stat changes are for the gun's own reload state.
  GorillaAkimboReloadSystem.Get(owner.GetGame()).Clear(other.GetItemID(), n"reload");
  if otherKind == 0 || ArraySize(passStarts) == 0 {
    return;
  }
  let n = ArraySize(passStarts);
  let total = passStarts[n - 1] + passLengths[n - 1];
  let now = this.GetInStateTime();
  let start = now + MaxF(GorillaAkimboTopMag.Down(kind) - this.m_gorillaTopMagClip, 0.0) / MaxF(this.m_gorillaTopMagSpeed, 0.05);
  let times: array<Float>;
  let names: array<CName>;
  GorillaAkimboReload.Sounds(other, other.GetWeaponRecord(), otherKind, passStarts, passLengths, times, names);
  let i = 0;
  while i < ArraySize(times) {
    GorillaAkimboTopMag.InsertSound(this.m_gorillaSoundTimes, this.m_gorillaSoundNames, start + times[i], names[i]);
    i += 1;
  }
  if otherKind == GorillaAkimboReload.Shells() {
    // Shells: every pass is loaded here, the last one when the reload would end.
    i = 0;
    while i < ArraySize(shellTimes) {
      ArrayPush(this.m_gorillaJoinShellTimes, start + shellTimes[i]);
      ArrayPush(this.m_gorillaJoinShellCounts, shellCounts[i]);
      i += 1;
    }
    ArrayPush(this.m_gorillaJoinShellTimes, start + total);
    ArrayPush(this.m_gorillaJoinShellCounts, 0);
  } else {
    // A magazine: the gun's own reload, finished when its time is up.
    other.StartReload(start + total - now);
    topMag.pairOther = other;
    topMag.pairOtherAt = start + total;
  }
  this.m_gorillaJoin = true;
  this.m_gorillaJoinOther = other;
  this.m_gorillaJoinDone = start + total;
  topMag.SetPending(!left, false);
  // The reload state, and the block on firing, last as much longer as the guns are held down.
  let hold = this.m_gorillaJoinDone - (now + (GorillaAkimboTopMag.HoldEnd(kind) - this.m_gorillaTopMagClip) / MaxF(this.m_gorillaTopMagSpeed, 0.05));
  if hold > 0.0 {
    let weapon = this.GetWeaponObject(scriptInterface);
    let system = GorillaAkimboReloadSystem.Get(owner.GetGame());
    system.Add(weapon, n"reload", gamedataStatType.ReloadEndTime, gameStatModifierType.Additive, hold);
    system.Add(weapon, n"reload", gamedataStatType.EmptyReloadEndTime, gameStatModifierType.Additive, hold);
    topMag.busyUntil += hold;
  }
}

@addMethod(ReloadEvents)
private final func GorillaTopMagUpdate(timeDelta: Float, scriptInterface: ref<StateGameScriptInterface>) {
  let topMag = GorillaAkimboTopMagSystem.Get(scriptInterface.GetGame());
  let now = this.GetInStateTime();
  let kind = this.m_gorillaTopMagKind;
  this.m_gorillaTopMagClip += timeDelta * this.m_gorillaSpeed;
  if !this.m_gorillaTopMagHandedBack && this.m_gorillaTopMagClip >= GorillaAkimboTopMag.Length(kind) - GorillaAkimboTopMag.HandBack() {
    this.GorillaTopMagHandBack(scriptInterface);
  }
  if topMag.pairOtherAt >= 0.0 && now >= topMag.pairOtherAt {
    this.GorillaTopMagFinishOther(topMag);
  }
  this.GorillaTopMagJoin(scriptInterface);
  if !this.m_gorillaJoin {
    return;
  }
  let other = this.m_gorillaJoinOther;
  while ArraySize(this.m_gorillaJoinShellTimes) > 0 && now >= this.m_gorillaJoinShellTimes[0] {
    if IsDefined(other) {
      GorillaAkimboReload.LoadPass(other, scriptInterface.executionOwner, this.m_gorillaJoinShellCounts[0]);
    }
    ArrayErase(this.m_gorillaJoinShellTimes, 0);
    ArrayErase(this.m_gorillaJoinShellCounts, 0);
  }
  // Out of view, the clip slows so it leaves the hold as the other gun's ammo is all in.
  let speed = this.m_gorillaTopMagSpeed;
  let clip = this.m_gorillaTopMagClip;
  if clip >= GorillaAkimboTopMag.HoldStart(kind) && clip < GorillaAkimboTopMag.HoldEnd(kind) && this.m_gorillaJoinDone > now {
    speed = ClampF((GorillaAkimboTopMag.HoldEnd(kind) - clip) / (this.m_gorillaJoinDone - now), 0.02, this.m_gorillaTopMagSpeed);
  }
  if AbsF(speed - this.m_gorillaSpeed) > 0.001 {
    this.m_gorillaSpeed = speed;
    let feature = new AnimFeature_WeaponReloadSpeedData();
    feature.reloadSpeed = speed;
    feature.emptyReloadSpeed = speed;
    scriptInterface.SetAnimationParameterFeature(n"RightReloadSpeed", feature);
    // A left gun, and a pair's left gun, read the left channel.
    if this.IsLeftWeaponLogic() || this.m_gorillaTopMagPair {
      scriptInterface.SetAnimationParameterFeature(n"LeftReloadSpeed", feature);
    }
  }
}

@wrapMethod(ReloadEvents)
protected func OnExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  GorillaAkimboTopMagSystem.Get(scriptInterface.GetGame()).SetReloading(this.IsLeftWeaponLogic(), false);
  this.GorillaOwnEnd();
  if this.m_gorillaTopMag {
    this.GorillaTopMagEnd(stateContext, scriptInterface);
  }
}

@wrapMethod(ReloadEvents)
protected func OnForcedExit(stateContext: ref<StateContext>, scriptInterface: ref<StateGameScriptInterface>) -> Void {
  wrappedMethod(stateContext, scriptInterface);
  let topMag = GorillaAkimboTopMagSystem.Get(scriptInterface.GetGame());
  topMag.SetReloading(this.IsLeftWeaponLogic(), false);
  this.GorillaOwnEnd();
  if this.m_gorillaTopMag {
    this.GorillaTopMagEnd(stateContext, scriptInterface);
    topMag.SetPending(!this.IsLeftWeaponLogic(), false);
  }
}

// While one hand reloads two-handed, the other hand can't start a reload; asking for one queues it. A
// two-handed reload also waits for the other hand's own reload to finish. Queued reloads start when the hand
// is free and the gun still needs ammo.
@wrapMethod(ReloadDecisions)
protected final const func EnterCondition(const stateContext: ref<StateContext>, const scriptInterface: ref<StateGameScriptInterface>) -> Bool {
  let owner = scriptInterface.executionOwner;
  let left = this.IsLeftWeaponLogic();
  let topMag = GorillaAkimboTopMagSystem.Get(owner.GetGame());
  let weapon = this.GetWeaponObject(scriptInterface);
  let asked = scriptInterface.IsActionJustTapped(n"Reload") || scriptInterface.IsActionJustPressed(n"Reload");
  // The gun's magazine track set, ahead of any reload.
  topMag.UpdateFamily(owner, weapon, left);
  // A pair reloads both guns from one hand's reload, so the other hand never starts its own.
  let mine = GorillaAkimboTopMag.Single(owner, weapon, left) != GorillaAkimboTopMag.None()
    || GorillaAkimboTopMag.Pair(owner, weapon, left) != GorillaAkimboTopMag.None();
  if GorillaAkimboTopMagSystem.Busy(owner.GetGame()) || (mine && topMag.Reloading(!left)) {
    if asked || (IsDefined(weapon) && weapon.IsMagazineEmpty()) {
      topMag.SetPending(left, true);
    }
    return false;
  }
  if topMag.Pending(left) {
    if EngineTime.ToFloat(GameInstance.GetSimTime(owner.GetGame())) < topMag.joinWaitUntil {
      return false;
    }
    topMag.SetPending(left, false);
    if WeaponObject.CanReload(weapon) {
      return true;
    }
  }
  // Asked together with a top-magazine gun that can reload: this gun joins that reload (GorillaTopMagJoin) rather
  // than going first. The key press is seen before the tap the game reloads on, so the queued reload waits a
  // moment for that reload to start, and starts on its own if it doesn't.
  if asked && !mine && IsDefined(weapon) && WeaponObject.CanReload(weapon) {
    let other = GorillaAkimboTopMag.Weapon(owner, !left);
    if GorillaAkimboTopMag.Single(owner, other, !left) != GorillaAkimboTopMag.None() && WeaponObject.CanReload(other) {
      topMag.SetPending(left, true);
      topMag.joinWaitUntil = EngineTime.ToFloat(GameInstance.GetSimTime(owner.GetGame())) + 0.6;
      return false;
    }
  }
  return wrappedMethod(stateContext, scriptInterface);
}
