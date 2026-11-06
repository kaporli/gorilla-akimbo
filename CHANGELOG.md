# Changelog

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
