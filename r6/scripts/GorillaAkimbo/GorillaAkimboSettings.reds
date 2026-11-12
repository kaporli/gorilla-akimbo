// Gorilla Akimbo settings, shown in Mod Settings when it is installed. Without it the defaults apply.
module GorillaAkimbo

public enum GorillaAkimboFiring {
  Vanilla = 0,
  Both = 1,
  Alternate = 2
}

public enum GorillaAkimboShellReload {
  OneAtATime = 0,
  AllAtOnce = 1
}

public class GorillaAkimboSettings extends IScriptable {
  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.displayName", "SMGs")
  @runtimeProperty("ModSettings.description", "Gorilla Arms let you dual-wield SMGs. Applies to guns you equip from now on.")
  public let smgs: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "smgs")
  @runtimeProperty("ModSettings.displayName", "Power SMGs")
  @runtimeProperty("ModSettings.description", "Saratoga, Pulsar, Shigure and Guillotine.")
  public let powerSmgs: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "smgs")
  @runtimeProperty("ModSettings.displayName", "Smart SMGs")
  @runtimeProperty("ModSettings.description", "Shingen, Dian and Warden.")
  public let smartSmgs: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "smgs")
  @runtimeProperty("ModSettings.displayName", "Tech SMGs")
  @runtimeProperty("ModSettings.description", "Senkoh.")
  public let techSmgs: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.displayName", "Shotguns")
  @runtimeProperty("ModSettings.description", "Gorilla Arms let you dual-wield shotguns. Applies to guns you equip from now on.")
  public let shotguns: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "shotguns")
  @runtimeProperty("ModSettings.displayName", "Power shotguns")
  @runtimeProperty("ModSettings.description", "Carnage, Tactician, Crusher, Pozhar, Igla and Testera.")
  public let powerShotguns: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "shotguns")
  @runtimeProperty("ModSettings.displayName", "Smart shotguns")
  @runtimeProperty("ModSettings.description", "Zhuo and Palica.")
  public let smartShotguns: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "shotguns")
  @runtimeProperty("ModSettings.displayName", "Tech shotguns")
  @runtimeProperty("ModSettings.description", "Satara.")
  public let techShotguns: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "shotguns")
  @runtimeProperty("ModSettings.displayName", "Magazine shotguns")
  @runtimeProperty("ModSettings.description", "Shotguns that reload a magazine, for example Pozhar, Crusher and Zhuo.")
  public let magazineShotguns: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "shotguns")
  @runtimeProperty("ModSettings.displayName", "Shell-by-shell shotguns")
  @runtimeProperty("ModSettings.description", "Shotguns that load one shell at a time, for example Carnage and Tactician.")
  public let shellShotguns: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Weapons")
  @runtimeProperty("ModSettings.category.order", "1")
  @runtimeProperty("ModSettings.dependency", "shotguns")
  @runtimeProperty("ModSettings.displayName", "Double-barrel shotguns")
  @runtimeProperty("ModSettings.description", "Igla, Satara, Palica and Testera.")
  public let doubleBarrels: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Firing")
  @runtimeProperty("ModSettings.category.order", "2")
  @runtimeProperty("ModSettings.displayName", "Independent firing")
  @runtimeProperty("ModSettings.description", "Left mouse button fires the left gun, right mouse button the right gun (left and right trigger on a controller). Aim with its own key: mouse button 4 or left stick click, rebindable in Key Bindings with Unified Keybinds. Replaces Firing below.")
  public let independentFiring: Bool = false;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Firing")
  @runtimeProperty("ModSettings.category.order", "2")
  @runtimeProperty("ModSettings.displayName", "Firing")
  @runtimeProperty("ModSettings.description", "How one fire button uses both guns. Vanilla: full-auto pairs fire together, other pairs alternate on taps. Both at once: every shot fires both guns. Alternate: the guns take turns, so a faster gun waits for the slower one.")
  @runtimeProperty("ModSettings.displayValues.Vanilla", "Vanilla")
  @runtimeProperty("ModSettings.displayValues.Both", "Both at once")
  @runtimeProperty("ModSettings.displayValues.Alternate", "Alternate")
  public let firing: GorillaAkimboFiring = GorillaAkimboFiring.Vanilla;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Firing")
  @runtimeProperty("ModSettings.category.order", "2")
  @runtimeProperty("ModSettings.displayName", "Remove Double Trouble's damage penalty")
  @runtimeProperty("ModSettings.description", "Double Trouble cuts each gun's damage by 37.5% while dual-wielding. On removes that for every dual-wielded pair, pistols included. Applies the next time you draw both guns.")
  public let noDamagePenalty: Bool = false;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Reload")
  @runtimeProperty("ModSettings.category.order", "3")
  @runtimeProperty("ModSettings.displayName", "Shell-by-shell shotgun reload")
  @runtimeProperty("ModSettings.description", "One at a time: shells load one by one, as in the base game. All at once: every shell loads in the time one shell takes.")
  @runtimeProperty("ModSettings.displayValues.OneAtATime", "One at a time")
  @runtimeProperty("ModSettings.displayValues.AllAtOnce", "All at once")
  public let shellReload: GorillaAkimboShellReload = GorillaAkimboShellReload.OneAtATime;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Body scaling")
  @runtimeProperty("ModSettings.category.order", "4")
  @runtimeProperty("ModSettings.displayName", "Recoil scales with Body")
  @runtimeProperty("ModSettings.description", "Dual-wielded guns that need Gorilla Arms kick less with every Body point, like the game's attribute bonuses.")
  public let recoilScaling: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Body scaling")
  @runtimeProperty("ModSettings.category.order", "4")
  @runtimeProperty("ModSettings.dependency", "recoilScaling")
  @runtimeProperty("ModSettings.displayName", "Recoil reduction per Body point (%)")
  @runtimeProperty("ModSettings.description", "Recoil goes down by this much for every Body point. 2 gives -40% at Body 20.")
  @runtimeProperty("ModSettings.min", "0")
  @runtimeProperty("ModSettings.max", "4.5")
  @runtimeProperty("ModSettings.step", "0.1")
  public let recoilPerPoint: Float = 2.0;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Body scaling")
  @runtimeProperty("ModSettings.category.order", "4")
  @runtimeProperty("ModSettings.displayName", "Fire rate scales with Body")
  @runtimeProperty("ModSettings.description", "Dual-wielded guns that need Gorilla Arms fire faster with every Body point.")
  public let fireRateScaling: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Body scaling")
  @runtimeProperty("ModSettings.category.order", "4")
  @runtimeProperty("ModSettings.dependency", "fireRateScaling")
  @runtimeProperty("ModSettings.displayName", "Fire rate per Body point (%)")
  @runtimeProperty("ModSettings.description", "Fire rate goes up by this much for every Body point. 2 gives +40% at Body 20.")
  @runtimeProperty("ModSettings.min", "0")
  @runtimeProperty("ModSettings.max", "10")
  @runtimeProperty("ModSettings.step", "0.1")
  public let fireRatePerPoint: Float = 2.0;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Body scaling")
  @runtimeProperty("ModSettings.category.order", "4")
  @runtimeProperty("ModSettings.displayName", "Reload speed scales with Body")
  @runtimeProperty("ModSettings.description", "Dual-wielded guns that need Gorilla Arms reload faster with every Body point.")
  public let reloadScaling: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Body scaling")
  @runtimeProperty("ModSettings.category.order", "4")
  @runtimeProperty("ModSettings.dependency", "reloadScaling")
  @runtimeProperty("ModSettings.displayName", "Reload speed per Body point (%)")
  @runtimeProperty("ModSettings.description", "Reload speed goes up by this much for every Body point. 3 gives +60% at Body 20.")
  @runtimeProperty("ModSettings.min", "0")
  @runtimeProperty("ModSettings.max", "10")
  @runtimeProperty("ModSettings.step", "0.1")
  public let reloadPerPoint: Float = 3.0;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Smart Link")
  @runtimeProperty("ModSettings.category.order", "5")
  @runtimeProperty("ModSettings.displayName", "Smart Link on both guns")
  @runtimeProperty("ModSettings.description", "Bullets from a Smart gun in the left hand go to the targets Smart Link locks, like the right gun's. Off: only the right gun's bullets track, as in the base game.")
  public let smartLinkBoth: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Assault rifles")
  @runtimeProperty("ModSettings.category.order", "6")
  @runtimeProperty("ModSettings.displayName", "Assault rifles")
  @runtimeProperty("ModSettings.description", "Gorilla Arms let you dual-wield assault rifles. Applies to guns you equip from now on.")
  public let rifles: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Assault rifles")
  @runtimeProperty("ModSettings.category.order", "6")
  @runtimeProperty("ModSettings.dependency", "rifles")
  @runtimeProperty("ModSettings.displayName", "Power assault rifles")
  @runtimeProperty("ModSettings.description", "Ajax, Kyubi, Copperhead, Umbra and Masamune.")
  public let powerRifles: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Assault rifles")
  @runtimeProperty("ModSettings.category.order", "6")
  @runtimeProperty("ModSettings.dependency", "rifles")
  @runtimeProperty("ModSettings.displayName", "Smart assault rifles")
  @runtimeProperty("ModSettings.description", "Sidewinder, Divided We Stand and Hercules.")
  public let smartRifles: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Pistols and revolvers")
  @runtimeProperty("ModSettings.category.order", "7")
  @runtimeProperty("ModSettings.displayName", "Tech and Smart pistols")
  @runtimeProperty("ModSettings.description", "Dual-wield Tech and Smart pistols, which the game leaves out. No Gorilla Arms needed. Applies to guns you equip from now on.")
  public let pistols: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Pistols and revolvers")
  @runtimeProperty("ModSettings.category.order", "7")
  @runtimeProperty("ModSettings.dependency", "pistols")
  @runtimeProperty("ModSettings.displayName", "Smart pistols")
  @runtimeProperty("ModSettings.description", "Yukimura, Kappa and Chao.")
  public let smartPistols: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Pistols and revolvers")
  @runtimeProperty("ModSettings.category.order", "7")
  @runtimeProperty("ModSettings.dependency", "pistols")
  @runtimeProperty("ModSettings.displayName", "Tech pistols")
  @runtimeProperty("ModSettings.description", "Kenshin, Omaha, Grit and Ticon.")
  public let techPistols: Bool = true;

  @runtimeProperty("ModSettings.mod", "Gorilla Akimbo")
  @runtimeProperty("ModSettings.category", "Pistols and revolvers")
  @runtimeProperty("ModSettings.category.order", "7")
  @runtimeProperty("ModSettings.displayName", "Tech revolvers")
  @runtimeProperty("ModSettings.description", "Dual-wield Quasar and Burya, which the game leaves out. No Gorilla Arms needed. Applies to guns you equip from now on.")
  public let revolvers: Bool = true;

  // Whether a gun of this group (GorillaAkimboGuns.Group) is switched on: the group's switch, then the gun's kind
  // (Power, Smart, Tech). A new group needs its switches above and its line here.
  public func Allows(group: CName, item: ref<gameItemData>) -> Bool {
    switch group {
      case n"smg":
        return this.smgs && IsEvolutionAllowed(item, this.powerSmgs, this.smartSmgs, this.techSmgs);
      case n"shotgun":
        return this.shotguns && IsEvolutionAllowed(item, this.powerShotguns, this.smartShotguns, this.techShotguns);
      case n"rifle":
        return this.rifles && IsEvolutionAllowed(item, this.powerRifles, this.smartRifles, true);
      case n"pistol":
        return this.pistols && IsEvolutionAllowed(item, true, this.smartPistols, this.techPistols);
      case n"revolver":
        return this.revolvers;
    }
    return false;
  }
}

// Holds the settings for the session and reapplies them when they change.
public class GorillaAkimboConfig extends ScriptableSystem {
  private let m_settings: ref<GorillaAkimboSettings>;
  private let m_bodyListener: ref<GorillaAkimboBodyListener>;

  private func OnAttach() {
    this.m_settings = new GorillaAkimboSettings();
    GorillaAkimboConfig.Register(this, this.m_settings);
  }

  private func OnDetach() {
    GorillaAkimboConfig.Unregister(this, this.m_settings);
  }

  @if(ModuleExists("ModSettingsModule"))
  private static func Register(self: ref<IScriptable>, settings: ref<IScriptable>) {
    ModSettings.RegisterListenerToClass(settings);
    ModSettings.RegisterListenerToModifications(self);
  }

  @if(!ModuleExists("ModSettingsModule"))
  private static func Register(self: ref<IScriptable>, settings: ref<IScriptable>) {}

  @if(ModuleExists("ModSettingsModule"))
  private static func Unregister(self: ref<IScriptable>, settings: ref<IScriptable>) {
    ModSettings.UnregisterListenerToClass(settings);
    ModSettings.UnregisterListenerToModifications(self);
  }

  @if(!ModuleExists("ModSettingsModule"))
  private static func Unregister(self: ref<IScriptable>, settings: ref<IScriptable>) {}

  private final func OnPlayerAttach(request: ref<PlayerAttachRequest>) -> Void {
    let player = request.owner;
    if !IsDefined(player) {
      return;
    }
    this.m_bodyListener = new GorillaAkimboBodyListener();
    this.m_bodyListener.m_owner = player;
    this.m_bodyListener.SetStatType(gamedataStatType.Strength);
    GameInstance.GetStatsSystem(this.GetGameInstance()).RegisterListener(Cast<StatsObjectID>(player.GetEntityID()), this.m_bodyListener);
    GorillaAkimboBody.UpdateTooltip(player);
  }

  private final func OnPlayerDetach(request: ref<PlayerDetachRequest>) -> Void {
    if IsDefined(this.m_bodyListener) && IsDefined(request.owner) {
      GameInstance.GetStatsSystem(this.GetGameInstance()).UnregisterListener(Cast<StatsObjectID>(request.owner.GetEntityID()), this.m_bodyListener);
    }
    this.m_bodyListener = null;
  }

  public cb func OnModSettingsChange() -> Void {
    GorillaAkimboDamage.Apply(this.m_settings);
    let player = GameInstance.GetPlayerSystem(this.GetGameInstance()).GetLocalPlayerMainGameObject();
    if IsDefined(player) {
      GorillaAkimboBody.Refresh(player);
      GorillaAkimboBody.UpdateTooltip(player);
    }
  }

  public static func Get(game: GameInstance) -> ref<GorillaAkimboSettings> {
    let config = GameInstance.GetScriptableSystemsContainer(game).Get(n"GorillaAkimbo.GorillaAkimboConfig") as GorillaAkimboConfig;
    if IsDefined(config) && IsDefined(config.m_settings) {
      return config.m_settings;
    }
    return new GorillaAkimboSettings();
  }
}

// Body changes: the drawn guns get the new scaling and the Gorilla Arms tooltip the new values.
public class GorillaAkimboBodyListener extends ScriptStatsListener {
  public let m_owner: wref<GameObject>;

  public func OnStatChanged(ownerID: StatsObjectID, statType: gamedataStatType, diff: Float, total: Float) -> Void {
    if IsDefined(this.m_owner) {
      GorillaAkimboBody.Refresh(this.m_owner);
      GorillaAkimboBody.UpdateTooltip(this.m_owner);
    }
  }
}
