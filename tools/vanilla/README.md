# Game methods with small edits

Some of the game's weapon and grenade methods read the fire button or stop the guns inline. Independent firing and the
grenade throw need those methods with one detail changed. `derive.py` takes each method's source from the decompiled
game scripts, applies the edits listed in it and writes `r6/scripts/GorillaAkimbo/GorillaAkimboVanilla.reds`. Each
method there runs only under its condition; otherwise the game's (or another mod's) method runs.

Game scripts (the unmodded `final.redscripts`):

```
redscript-cli decompile -i "<game>/r6/cache/final.redscripts" -o <dir> -f
set GA_GAMESCRIPTS=<dir>
```

| Command | What it does |
|---|---|
| `python tools/vanilla/derive.py` | Regenerates the file. Lists methods whose game source differs from `baseline.json`. Stops if an edit no longer matches. |
| `python tools/vanilla/derive.py --check` | Exit 1 if the game source, the baseline or the generated file differ. Run before a release. |
| `python tools/vanilla/derive.py --accept` | Also records the current game source in `baseline.json`. |

After a game update: decompile, run `derive.py`, read each reported method, fix the entry if an edit stopped
matching, check the hand-written copy named for a watched method, then `--accept`.
