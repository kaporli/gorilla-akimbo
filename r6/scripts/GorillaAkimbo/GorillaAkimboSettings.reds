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
  @runtimeProperty("ModSettings.displayName", "Shotguns")
  @runtimeProperty("ModSettings.description", "Gorilla Arms let you dual-wield shotguns. Applies to guns you equip from now on.")
  public let shotguns: Bool = true;

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
  @runtimeProperty("ModSettings.description", "Dual-wielded SMGs and shotguns kick less with every Body point, like the game's attribute bonuses.")
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
  @runtimeProperty("ModSettings.description", "Dual-wielded SMGs and shotguns fire faster with every Body point.")
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
  @runtimeProperty("ModSettings.description", "Dual-wielded SMGs and shotguns reload faster with every Body point.")
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
