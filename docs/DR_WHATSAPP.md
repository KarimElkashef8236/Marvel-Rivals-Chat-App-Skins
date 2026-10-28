# Dr Whatsapp

[Back to the main page](../README.md)

Doctor Strange skin + sound mod for Marvel Rivals, updated for the current seasons. Green outfit, WhatsApp logo on the cape and a WhatsApp sound on every one of his abilities.

The original mod is by **Omono** on Nexus: https://www.nexusmods.com/marvelrivals/mods/974. The art and the ult sounds are theirs, used with credit under Omono's Nexus permissions (upload and modify with credit, never sold or used for donation points). I got it working again on the new seasons since the Season 1.5 files stopped working, and gave every other ability its own WhatsApp sound (taken from the WhatsApp Windows app).

Built against game build 1.1.3962284 (Oct 22 2026 patch). That patch didn't touch the skin's textures, but it took a few variants out of Strange's sounds, so the sounds got rebuilt on his new sound bank.

> [!CAUTION]
> **Mods break Marvel Rivals' Terms of Service and can get your account banned, temporary or permanent.** That goes for skin and sound mods like this one too. Use it at your own risk and never in ranked or tournaments. More in the [warning on the main page](../README.md#read-this-first).

![Vanilla Strange on top, Dr Whatsapp under it](media/dr_whatsapp_compare.png)

## Why the old files broke

- **Skin, part 1:** since Season 2 the game only loads skin mods as IoStore files (`.pak` + `.utoc` + `.ucas`). The old mod was a single legacy `.pak`, so the game just ignored it. I converted it with retoc-rivals. It's only 8 textures for the default costume, and all of them still exist under the same names in the current game.
- **Skin, part 2:** converting alone isn't enough. Season 2 also added 3 new properties to Texture2D (`OriginalWidth`, `OriginalHeight`, `LineCountPerFrame`) right before `ImportedSize`, so every property the old textures saved now sits 3 slots later and the game would read them wrong. `build.py` shifts them to the new layout, and it checks the game's own copy of `T_1018001_Body_D` first so it stops if NetEase changes the layout again.
- **Sounds:** the old mod replaced Strange's whole voice and sfx banks with copies from Feb 2025. NetEase changed those banks a lot since then (new sounds added, old ones removed or replaced), so dropping in the old banks would break or mute a bunch of his sounds. The old custom sounds also sat on stuff that barely plays now, like the plain Maelstrom of Madness that the Season 9 team-up loadouts replaced, and only 1 of the 3 portal sound variants. So now every current ability gets its own sound (see below), put into the current banks. Everything else in the banks is untouched.
- Both old paks had a junk `patched_files` entry that the new anticheat reportedly flags. It's gone.

## What's in it

| File | What |
| --- | --- |
| `dist\~mods\DrWhatsapp_9999999_P.pak/.utoc/.ucas` | the skin |
| `dist\~mods\68_DoctorWhatsappSounds_9999999_P.pak` | the sounds |
| `dist\fallback-obfuscated\DrWhatsapp_9999999_P.pak/.utoc/.ucas` | the same skin, obfuscated, only if the normal one doesn't show up (see below) |

**Skin:** Omono's textures for the default costume (1018001): the body, the three equipment textures (the cape and collar are `Equip_03`), the hair and the hair line colour textures, plus the glow and bump texture of `Equip_01`. The suit, cape and collar go WhatsApp green, there's a big WhatsApp logo on the back of the cape and a small one in the Eye of Agamotto on his chest, and his grey hair streak turns green. His face isn't touched.

## Install

The requirements and the easy way to install are on the [main page](../README.md#install). The short version:

Copy everything in `dist\~mods\` to:

```
...\MarvelRivals\MarvelGame\Marvel\Content\Paks\~mods\
```

The folder has to be called exactly `~mods`. Or run:

```
python scripts\install.py
```

(`--uninstall` removes it again, `--game "<path to Content\Paks>"` if your game isn't on D:)

You should end up with:

```
~mods\DrWhatsapp_9999999_P.pak
~mods\DrWhatsapp_9999999_P.utoc
~mods\DrWhatsapp_9999999_P.ucas
~mods\68_DoctorWhatsappSounds_9999999_P.pak
```

The sounds stay a plain `.pak`. That's on purpose, audio mods don't work as IoStore.

### If the skin doesn't show up

`dist\fallback-obfuscated\` has the same skin packed with `--obfuscate` (encrypted IoStore). That was the workaround people used before the Unmount Blocker came out. Use it instead of the normal skin files, not next to them (`python scripts\install.py --obfuscated`). The sounds still need the Unmount Blocker either way.

## Sounds

Every ability plays a WhatsApp sound now. Previews are in [`audio\preview\`](../audio/preview), named by key and ability.

| Key | Ability | WhatsApp sound | When |
| --- | --- | --- | --- |
| Left click | Daggers of Denak | message notification | every dagger volley |
| Left click | Dagger reload | alert tone 4 | when the daggers reload |
| Right click | Shield of the Seraphim | alert tone 6 | raising the shield |
| Shift | Cloak of Levitation | alert tone 2 | flying up |
| E | Gamma Maelstrom (Hulk team-up) | alert tone 9 | the blast |
| E | Psionic Vortex (Invisible Woman team-up) | alert tone 10 | the pull |
| E | Maelstrom of Madness (no team-up) | alert tone 5 | the plain blast, bots still use it |
| F | Pentagram of Farallah | alert tone 1 | pressing F |
| F | Portals open | incoming call ringtone | confirming the second portal |
| F | Portals close | call hang up | when they disappear or you cancel |
| V | Melee | alert tone 3 | the swing |
| Passive | Dark Magic full | alert tone 8 | only you hear it |
| Passive | Anti-Heal curse | alert tone 7 | only you hear it |
| Q | Eye of Agamotto | the original mod's sounds | voice line + ult impact, untouched |

More detail is in [`audio\SOUNDS.md`](../audio/SOUNDS.md). The sounds come from [`audio\whatsapp\`](../audio/whatsapp): the 10 alert tones, the notification, the ringtone and the hang up sound that ship with WhatsApp for Windows.

### How it works

Every ability sound in the game picks one of a few variants and usually plays a couple of extra layers on top. All the variants get the WhatsApp sound (so it plays every time, and for teammates and enemies too), and the extra layers get swapped for silence so the WhatsApp sound comes through clean instead of doubled or mixed with the old whoosh.

The game also puts its own volume and pitch on each sound. Gamma Maelstrom gets pitched down 6 semitones and Dark Magic full up 1, so those clips get shifted the other way first and end up sounding like the preview. Volumes range from -11 dB to +14 dB between abilities, so every clip gets leveled against that and they all come out about as loud as each other when you play (`target_db` in the json). Teammates and enemies still get the game's own offsets on top, like teammates' sounds being quieter.

Want a different sound on something? Change `"sound"` for that ability in `audio\sounds.json` (any file name from `audio\whatsapp\`, or drop your own `.wav`/`.mp3`/`.m4a` in there) and run `python scripts\build.py`. If one ends up too loud or too quiet in game, add `"gain_db": -3` (or whatever) to that ability.

There's no WhatsApp sound for walking through a portal, because the game doesn't play a Strange sound for that at all. Hits, the shield and portal hum loops and the cloak hover are still vanilla too, only the moment you use each ability changed.

The ult voice line only replaces English voice, and it streams (a short piece sits in the bank, the rest is a separate file), so the sound pak also has the clip at `WwiseAudio/Media/English(US)/78/78094833.wem` and `.../24/249885012.wem` so both parts match.

## After a game update

If a patch changes Strange's banks, the sounds can go back to vanilla or go quiet. Just rebuild:

```
python scripts\build.py
python scripts\install.py
```

`build.py` unpacks the original rars in `original\`, converts the skin and rebuilds the sounds on whatever banks the game has now. It needs Python 3 with `cryptography` and `numpy`, and it grabs retoc-rivals-cli v3.9.3 into `tools\` if it isn't there (checked against its sha256). If it says an event or sound id is gone, NetEase changed that sound and it has to be remapped in `audio\sounds.json`.

## Notes

- The skin only changes the default costume (1018001). The sounds are a different story: some of the same sound ids are also in the banks for his other costumes (1018300/302/305/800), and Wwise keeps whichever copy loads first. So if another Strange in the match uses one of those skins, some sounds can swap between you. Same as the original mod.
- The ult voice clip only replaces English voice. Chinese and Japanese voice use different ids and stay vanilla. All the ability sounds work in any language.
- Rogue (1065) has a copy of Strange's shield sounds in her own bank since she can absorb it, so in a match with a Rogue the shield sound can swap between you two, same deal as above.
- The Thanos PvE mode that came with the Oct 22 patch uses the same 3 sound ids as his portals opening for one of its own portal sounds. So in that mode with a Strange in the match, either that portal plays the WhatsApp ringtone (at its own volume, which is louder than his portals for you and your team) or Strange's portals open with the vanilla sound, same deal as above.
- Two things in the game bend the pitch and can't be undone with one clip: enemies hear the portals open ringtone about 2 semitones lower, and the daggers get pitched up when the game pushes an RTPC under 20 (probably low charges). Both are vanilla behaviour.
- The far away LOD textures (`Merge_Texture/T_1018001_LOD2_*`) aren't in the original mod, so from really far he might look vanilla.
- Keep a copy of your `~mods` somewhere else. The launcher's "clear redundant files" can delete it.
- Mods are against Marvel Rivals' Terms of Service and can get your account banned, temporary or permanent. That includes skin and sound mods like this one. Use it at your own risk, never in ranked or tournaments, and don't stack config, UI or VFX mods on top of it, those make the risk even bigger.

## Layout

```
original\   the Season 1.5 rars from Nexus (build.py builds the skin from them)
dist\       the fixed mod, ready to install
audio\      sounds.json (which sound goes on which ability), the WhatsApp sounds,
            the built .wem files and .wav previews
scripts\    build and install scripts, pak, soundbank and texture tools,
            and the preview renderer in scripts\preview\
docs\       this file and the pictures for the main page (docs\media\)
ironman\    Iron Whatsapp (its own readme, sounds, previews and built files)
magneto\    Discordneto (same, plus the sound plan and the logo overlays)
```

`scripts\rivalspak.py` reads and writes Rivals paks the same way repak-rivals does (the game key, partial encryption on each file, Oodle).
