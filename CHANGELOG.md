# Changelog

## 2.1.0 (2026-11-06)

In-game settings with [Mod Settings](https://www.nexusmods.com/cyberpunk2077/mods/4885), independent firing and Body scaling.

- Settings: pair SMGs, magazine shotguns, shell-by-shell shotguns and double-barrels or not; fire both guns at once or alternate them; remove Double Trouble's 37.5% damage penalty; load all shells of a shell-by-shell shotgun at once. Without Mod Settings, the defaults apply (the same behavior as 2.0.1).
- Independent firing (setting, off by default): the left mouse button fires the left gun, the right mouse button the right gun (left and right trigger on a controller). Aiming moves to its own key, mouse button 4 or the left stick click by default, rebindable in Key Bindings with [Unified Keybinds](https://www.nexusmods.com/cyberpunk2077/mods/37156). Needs [Input Loader](https://www.nexusmods.com/cyberpunk2077/mods/4575). Each gun's own button also cuts its shell-by-shell reload short.
- Body scaling: every Body point gives dual-wielded SMGs and shotguns -2% recoil, +2% fire rate and +3% reload speed (-40%, +40% and +60% at Body 20). Each can be changed or turned off in the settings. Raising Body applies to drawn guns right away.
- The Gorilla Arms tooltip shows the Body scaling in its Body Attuned block.

## 2.0.1 (2026-11-06)

- Fixed a crash when a dual-wielded SMG or shotgun reloads, most often when both guns reload at once. The reload animations pointed at fallback poses of other clips.

## 2.0.0 (2026-11-06)

Dual-wielded SMGs and shotguns get their own reload animations, timing and sounds. Needs [ArchiveXL](https://www.nexusmods.com/cyberpunk2077/mods/4198) now.

- Custom one-handed reload animations for dual-wielded SMGs and shotguns, for male and female V, made from the game's pistol dual-wield reload. The gun tips up while the magazine drops, goes down out of view, and rises back once its ammo is in. Shell-by-shell shotguns go straight down. In 1.0.1 the right gun played its two-handed reload, which swings the gun across the screen.
- Each hand reloads on its own: only the gun that needs ammo goes down, and the other can keep firing. In 1.0.1 the left gun's reload didn't animate and the right gun's moved both arms.
- Reload timing from each gun's live reload stats, so mixed pairs (SMG + shotgun, pistol + SMG) each time themselves. The rise waits for that gun's ammo, so the magazine no longer floats into the gun.
- Shell-by-shell shotguns stay down for the whole reload and load one shell at a time, at the times a single shotgun would (including the gap between shells and the longer first shell from empty). The ammo counter fills shell by shell, and firing mid-reload keeps the loaded shells.
- Both guns play their own reload sounds, timed to their own reloads. In 1.0.1 the left gun's reload had no animation, and so no sound.
- The dual-wield ammo counter no longer cuts off the left gun's count when both guns have long icons.

## 1.0.1 (2026-10-31)

- Renamed from Gorilla Grip to Gorilla Akimbo: files now go to `r6/scripts/GorillaAkimbo` and `r6/tweaks/GorillaAkimbo`. No gameplay changes.
- Manual installs: delete the old `r6/scripts/GorillaGrip` and `r6/tweaks/GorillaGrip` folders, or both versions load.

## 1.0.0 (2026-10-31)

- First release for Cyberpunk 2077 2.5.
- Gorilla Arms make SMGs and shotguns dual-wieldable with Double Trouble.
- Tooltip lines on Gorilla Arms and in Double Trouble's weapon box.
