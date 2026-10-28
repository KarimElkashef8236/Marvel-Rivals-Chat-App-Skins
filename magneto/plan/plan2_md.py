"""SOUNDS_PLAN.md for Discord Magneto (called from plan2.py)."""

NOT_USED = [
    ("user_moved", "A mod moving you to another voice channel. It was on the knock-back in draft 2, the airhorn has "
                   "that spot now. Swap it back onto pick 07 if you like the 'moved you to another channel' joke "
                   "more than the airhorn."),
    ("call_ringing_beat", "The rare ringtone, about 1 in 2000 calls (1 in 1000 rolls a rare ringtone, then it's "
                          "this one or Snow Halation). It was on the barrage charge, but two ringtones in one kit "
                          "made the charge sound like the ult coming. It's the other choice for the optional timer "
                          "bed, where only you hear it."),
    ("soundboard_cricket", "Soundboard crickets, 2 s of chirps. Nothing in the kit is an awkward silence."),
    ("soundboard_golf_clap", "Soundboard golf clap. Quiet scattered claps, they'd get lost in a fight."),
    ("soundboard_ba_dum_tss", "Soundboard rimshot, 1.6 s. Too long for a hit marker. Swap it onto the melee hit "
                              "instead of the quack if you want the joke. (Soundboard id 7 is the same file.)"),
    ("reconnect", "'Invited to Speak' on Stages (it used to be the reconnect sound). A 4 note tune that starts "
                  "with the same jump up as user joined (the meteor throw)."),
    ("message3", "New message in the channel you're reading. Too close to the message ping (both land on the "
                 "same high note), it would blur Iron Volley."),
    ("mention1", "Old @mention ping, one long ping. Too close to the ring ping."),
    ("activity_end / activity_user_left", "The rest of the Activity set. Nothing in the team-up ends or leaves on "
                                          "its own, and activity_end is one more falling phrase next to deafen "
                                          "and disconnect."),
    ("clip_error", "Clip failed to save. A fail sound, but the sad horn got the broken meteor."),
    ("ddr-left / ddr-up / ddr-right", "The other arrow keys of the Ctrl+/ easter egg. Only the greatsword hit "
                                      "still uses one."),
    ("ducky_message1", "Ducky pack message ping. Four other packs' pings are already in the plan, one more would "
                       "be a repeat by ear."),
    ("call_ringing_snow_halation", "The other rare ringtone, a 35 s song. Too long for anything here."),
    ("call_ringing_snowsgiving", "Old winter ringtone, Discord doesn't play it any more."),
    ("halloween_* ({halloween} files, 2 are misspelled leftovers)",
     "Halloween pack versions of the call, mute, deafen, join, leave, disconnect and message sounds. Busier "
     "remixes of sounds already in the plan, so they'd sound like repeats. Fun idea for a spooky version: "
     "halloween_call_calling on the cast and halloween_call_ringing on the forming."),
    ("winter_* ({winter} files)", "Winter pack versions, same reason. The current Discord can't even turn that "
                                  "pack on."),
    ("poggermode_enabled / poggermode_applause / poggermode_achievement_unlock / poggermode_message_send",
     "Party Mode (hidden). Hardly anyone has heard them."),
    ("vibing_wumpus", "Lofi track from the take a break screen. Ready as the optional team-up timer bed below."),
    ("overlayunlock / human_man / robot_man / hang_status_select / success",
     "Barely or never played by Discord (plant watered, bug report sent, two 2016 voice clips), nobody knows them."),
]


def cell(s):
    return str(s).replace("|", "/").replace("\n", " ")


def render_md(rows, optional, inv, usage, nice, seq_files, lead_in, k48, lv_range):
    out = []
    w = out.append
    by = {a["name"]: a for a in rows}
    num = {a["name"]: f"{i:02d}" for i, a in enumerate(rows, 1)}
    cast, form = by["Meteor M cast"], by["Meteor M forming"]

    w("# Discord Magneto: sound plan\n")
    w("This is the plan the sound pak is built from: every pick, why, the cuts and gains, and one preview per "
      "moment in `preview/`. `sounds.json` (same format as `ironman/sounds.json`) is what "
      "`scripts\\build_magneto.py` builds. To swap a sound, change it in `plan/plan2.py`, run it, listen, "
      "then rebuild.\n")
    w("**The previews are all at the same volume.** They're cut and leveled the same way `make_sounds.py` "
      "does it, but the Gain column below only gets added in game. So a -8 dB pick will be a lot quieter in "
      "game than its preview, and a +2 dB one a bit louder. The three ult sequence files do have the gains in.\n")

    w("## Fixed since the second draft\n")
    w("- **Soundboard sounds are in.** Quack, airhorn and sad horn are used; cricket, golf clap and ba dum tss "
      "are downloaded too (`discord/soundboard_*.mp3`). They come straight from Discord's CDN, no login needed.")
    w("- **Iron rings count properly now.** The file's 3rd ping is about 15 dB quieter than the other two, so "
      "the full ring sounded almost like ring 2. Now every ring is the same single ping, played 1, 2 or 3 times.")
    w("- **Mag-Cannon 1 ring** is 'a viewer joined the stream' instead of two low notes of Go Live. 2 rings is "
      "Go Live cut after 4 notes, 3 rings the whole run.")
    w("- **Ult timing.** The cast is only the first 'boo-doo-doo' of the calling tone now, and the ringtone "
      f"starts {lead_in} s after it, so the ring takes about as long as the vanilla forming sound. There are three ult sequence "
      "previews (quick throw, late throw, meteor broken) so you hear how it really gets cut.")
    w("- **user_leave is on Magneto dying**, so you hear it every match. The broken meteor gets the soundboard "
      "sad horn.")
    w("- **Barrage charge** is the drums from the Stage waiting music, not the rare ringtone, so nobody mixes "
      "it up with the ult. The barrage start is 'someone joined the Activity', so the team-up opens with "
      "Activity sounds.")
    w("- **Meteor impact plays once for everyone.** You and your allies used to hear two copies at once.")
    w("- **Curtain block tink** is cut after its bright note ends instead of in the middle of it.")
    w("- **Melee hit** quacks now (it was an arrow key beep from a hidden easter egg nobody knows).\n")

    w("## The idea\n")
    w("Every ability is one Discord feature, so you can tell them apart with your eyes shut:\n")
    w("- **Iron Volley** is the chat: message ping on every shot, a soft 'bop' when the orbs burst.")
    w("- **Mag-Cannon** is streaming: 1 ring = a viewer joins, 2 rings = Go Live cut short, 3 rings = the whole "
      "Go Live run. A hit gets 'clip saved', a full-ring knock-back gets the airhorn.")
    w("- **Metallic Curtain** is deafen: wall up = deafen, wall down = undeafen, blocked shots go 'tink'.")
    w("- **Metal / Iron Bulwark** is mute: shield up = mute, shield down = unmute.")
    w("- **The iron rings** count out loud: 1 ping, 2 pings, 3 pings (full Mag-Cannon).")
    w("- **Reload** is two soft taps, no tune.")
    w("- **Meteor M** is a whole Discord call: calling on the cast, the ringtone while it forms, 'user joined' "
      "when you throw it (they picked up), disconnect on impact. Break it before the throw and it's the sad horn.")
    w("- **Melee** is the Lofi pack's ping, and a melee hit quacks.")
    w("- **Magnetic Descent** is push to talk: hold jump = hold the PTT key.")
    w("- **Metallic Chaos** (Scarlet Witch) starts an Activity. The barrage is the show: someone joins, the "
      "Stage waiting drums while it charges, a retro 'pew' per sword, viewers leave per mark, stream ended on "
      "the last one.")
    w("- **Magnetic Resonance** (Emma Frost) is your camera: on when the projection appears, off when it's gone.")
    w("- **Dying** is leaving the channel: user_leave on every death fall.\n")
    w("The C and X sounds only play when Scarlet Witch or Emma Frost is on your team. Vanilla voice lines stay "
      "(\"Fear Magneto!\", \"For Mutantkind!\", the ability and team-up lines), same as Iron Man.\n")

    w("## Picks\n")
    w("| # | Key | Ability / moment | Discord sound | What it is in Discord | Why | Preview |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    for a in rows:
        w(f"| {num[a['name']]} | {cell(a['key'])} | **{cell(a['name'])}**: {cell(a['moment'])} | `{a['sound']}` | "
          f"{cell(nice[a['sound']])} | {cell(a['why'])} | `{a['_file']}` |")
    w("")

    w("## Cuts and gain\n")
    w("| # | Sound | Cut (seconds of the Discord file) | Clip length | Gain and notes |")
    w("| --- | --- | --- | --- | --- |")
    for a in rows:
        length = f"{a['_len']:.2f} s"
        if a.get("repeat", 1) > 1:
            length = f"{a['_len']:.2f} s ({a['repeat']} pings)"
        if a.get("lead_in"):
            length += f", {a['_game_len']:.2f} s in game with the {a['lead_in']} s wait"
        w(f"| {num[a['name']]} | `{a['sound']}` | {cell(a['_trim'])} | {length} | {cell(a['gain_note'])} |")
    w("")
    w("Each clip is leveled against the game's own volume on the sound it replaces (`target_db` -22 plus the "
      "gain), so they all land about as loud as each other in game, like Iron Man. Every level lands between "
      f"{lv_range[0]:.0f} and {lv_range[1]:.0f} dB, inside the -3 / -40 dB limits.\n")

    w("## The ult, start to finish\n")
    w(f"1. **Q**: the first 'boo-doo-doo' of `call_calling` ({cast['_len']:.2f} s), under \"Fear Magneto!\".")
    w(f"2. **Meteor forming**: `call_ringing`, the real incoming call ringtone, {lead_in} s later. One full ring "
      f"is {form['_len']:.2f} s, so it runs {form['_game_len']:.2f} s in all, a bit longer than the 5.57 s "
      "vanilla forming sound. Throwing stops it, so in a match you hear as much of the ring as you wait.")
    w("3. **Each shot the meteor eats**: one quiet low note (`message2`).")
    w("4. **Throw**: the ring stops (the game already does that), then `user_join`. Throwing = picking up.")
    w("5. **Impact**: `disconnect`, with the big shared explosion under it.")
    w("6. **Broken before the throw**: the soundboard sad horn. Nothing stops the ring here (the game has no "
      "stop for it, same as the vanilla rumble), so it keeps ringing under the sad horn until the clip ends. "
      "Same if you die mid-ult.\n")
    w("Ult sequence previews (made-up timing, gains applied):\n")
    for fn, label, seq, secs in seq_files:
        if "shattered" in label:
            t = next(t for n, t, _ in seq if n == "Meteor M shattered")
            desc = f"meteor broken at {t} s, the ring keeps going under the sad horn"
        else:
            t = next(t for n, t, _ in seq if n == "Meteor M thrown")
            desc = (f"throw at {t} s, so you hear {t - lead_in:.1f} s of ring, impact "
                    f"{next(tt for n, tt, _ in seq if n == 'Meteor M impact') - t:.1f} s later")
        w(f"- `{fn}`: {desc}.")
    w(f"\n`{form['_file']}` is the whole ring on its own. You'll only hear all of it if you hold the meteor "
      "the whole time.\n")

    w("## Repeats\n")
    w("Only two sounds are on more than one moment, both inside one ability and both on purpose:\n")
    w("- `stream_started` on Mag-Cannon 2 and 3 rings: 4 notes of the Go Live run, then all 6. The bigger the "
      "shot, the more of the run you hear.")
    w("- `mention3` on the three iron rings: one ping played 1, 2 or 3 times. That's the whole point, you "
      "count the rings by ear.\n")
    w("Close cousins, different files: `stream_user_joined` (1 ring) and `stream_user_left` (barrage mark) "
      "sound alike, they're Discord's viewer joined / viewer left pair; `activity_user_join` (barrage start) is a rising 3 note chime a "
      "bit like `user_join` (meteor throw), but higher; `ptt_stop` sounds a bit like the start of "
      "`user_leave`.\n")

    w("## Discord sounds used\n")
    used = {}
    for a in rows:
        used.setdefault(a["sound"], []).append(num[a["name"]])
    groups = {}
    for s, where in used.items():
        pack = inv[s].get("pack") or "default"
        origin = ("Soundboard" if pack == "soundboard" else "Default Discord sounds" if pack == "default"
                  else "Nitro sound packs")
        label = f"`{s}` ({', '.join(where)})" if origin != "Nitro sound packs" else \
            f"`{s}` ({pack.capitalize() if pack != 'asmr' else 'ASMR'} pack, {', '.join(where)})"
        groups.setdefault(origin, []).append(label)
    for origin in ("Default Discord sounds", "Soundboard", "Nitro sound packs"):
        if origin in groups:
            w(f"- **{origin}**: {', '.join(groups[origin])}")
    w("")
    big = [n for n, u in usage.items() if u.get("recognisability", 0) >= 4]
    mid_out = [n for n, u in usage.items() if u.get("recognisability", 0) == 3 and n not in used]
    w(f"{len(used)} different Discord sounds over {len(rows)} moments (the numbers are the picks). All "
      f"{len(big)} of the really well known ones are in (message ping, ringtone, calling, join, leave, "
      "disconnect, mute, unmute, deafen, undeafen, Go Live, stream ended, quack, airhorn). Well known ones "
      f"left out: {', '.join('`' + n + '`' for n in mid_out)}, see below.\n"
      if all(n in used for n in big) else
      f"{len(used)} different Discord sounds over {len(rows)} moments.\n")
    w("Heads up: a few picks are Discord in name only, bits nobody will recognise on their own: the "
      "curtain tink (`mention2`), the meteor eating a shot (`message2`) and the greatsword hit (`ddr-down`). "
      "They fire a lot, so they're short on purpose, and the first two are quiet too.\n")

    w("## Discord sounds not used, and why\n")
    n_hal = sum(1 for n in inv if n.startswith("halloween_"))
    n_win = sum(1 for n in inv if n.startswith("winter_"))
    for s, why in NOT_USED:
        w(f"- `{s.format(halloween=n_hal, winter=n_win)}`: {why}")
    w("")

    w("## Who hears what\n")
    w("- Every pick covers your version, the ally version and the enemy version of its sound, so everyone "
      "hears the Discord sound, except where the game itself mutes a version: allies never hear the ring "
      "sounds, the meteor eating a shot, the descent start/end or the projection end.")
    w("- Some moments only exist for some people: the knock-back and the greatsword hit (you and the person "
      "hit), the Mag-Cannon hit, the melee hit and the barrage marks (only you).")
    w("- Enemies hear the Iron Volley ping 4 semitones lower, allies hear the meteor impact 1.5 semitones lower, "
      "and other people hear some curtain tinks 2 semitones lower. The game pitches those itself and the files "
      "are shared, so it can't be right for everyone.")
    w("- The sound pak changes the sound bank almost every Magneto costume uses, so most Magneto skins will "
      "sound like Discord Magneto, not only the default one. Same as the Iron Man note.\n")

    w("## What stays vanilla, and why\n")
    w("- **Voice lines**: all of them.")
    w("- **E / F cast whoosh**: Rogue has the same files (she copies Iron Bulwark), so it stays. The Discord mute "
      "plays a moment later when the shield appears.")
    w("- **Layers shared with other heroes**: the Mag-Cannon full-ring sweetener, the tick under the ring "
      "sounds, the long explosion tails under the meteor impact, the debris under the Iron Volley burst and the "
      "surface impacts under the Mag-Cannon hit and the meteor eating a shot. They keep playing under or after "
      "the Discord sounds.")
    w("- **Loops and beds**: curtain hum, shield hum, descent hum, meteor fly-by and the team-up timer bed. They "
      "tell you the wall or shield is still up and how long the team-up lasts, and no short Discord clip loops "
      "cleanly. The timer bed has an optional Discord version below.")
    w("- **Shield taking a hit and debris hitting the meteor**: shared impact sounds and physics spam.")
    w("- **Movement and foley**: footsteps, cloth, flying (also during the ult), jump, land, taking damage. The "
      "cloth/air whoosh of Magnetic Descent stays under the push to talk click too. The one generic body fall "
      "that isn't tied to a death animation stays too, since nothing says when it plays.")
    w("- **Enemy-only fly-bys** (Iron Volley, Mag-Cannon, meteor) and all controller vibration.")
    w("- **Old unused team-ups and abilities**, except the old greatsword swing, which some costumes still use "
      "(it's in the greatsword pick).\n")

    w("## Optional extra (in `sounds.json` under `optional_abilities`)\n")
    w("Ready to move into `abilities` if you want it. It's off for the reason in the note.\n")
    w("| Key | Moment | Plays on | Sound | Cut | Gain | Note |")
    w("| --- | --- | --- | --- | --- | --- | --- |")
    for o in optional:
        cut = f"{o.get('start') or 0:.2f}-{o['end']:.2f} s" if o.get("end") else "full"
        w(f"| {o['key']} | {cell(o['name'])} | {cell(o['when'])} | `{o['sound']}`: {cell(nice[o['sound']])} | "
          f"{cut} | {o['gain_db']:+.0f} dB | {cell(o['note'])} |")
    w("")

    w("## Check in game\n")
    w("- The gap between pressing Q and the ringtone. The cast and the forming sound are started by different "
      "parts of the ult, so the ring might come in a bit later than in the previews.")
    w("- How long the ring keeps going after the meteor gets broken or you die mid-ult.")
    w("- The barrage charge clip is 5.39 s and the vanilla charge is 5.31 s, so the drum fill might touch the "
      "first sword.")
    w("- The quiet ones (-8 dB curtain tink and meteor absorb) in a real fight: too quiet or just right.")
    w("- The airhorn on the knock-back at -2 dB: fun or too much.\n")

    w("## Building\n")
    w("`python scripts\\build_magneto.py` builds the skin and the sounds. For the sounds it runs "
      "`make_sounds.py` and `build_audio.py` with this `sounds.json`: the clips come from the `src` folder "
      "(`magneto/discord`), clips that aren't 44.1 kHz get resampled, `repeat` / `every` / `lead_in` make the "
      "rings and the ringtone, and `prev_note` goes on the end of a preview's file name. It only replaces the "
      "numbered previews, so the three ult sequence files stay. Some spiky clips (melee, melee hit, ring 2, "
      "meteor thrown) come out a few dB quieter in game than their gain says, because the leveling won't "
      "boost anything more than 12 dB. Same rule as Iron Man.\n")
    w("Playing against another Magneto in the 1037300 or 1037304 costume: those costumes' banks share some "
      "of these sound ids, and the game keeps whichever copy loads first, so some sounds can come out vanilla "
      "for you (or Discord for them). Same thing as with Iron Man's costumes.\n")

    w("## Tech notes\n")
    w("Bank: `bnk_sfx_1037001.bnk`, checked against the copy in the game today. Only costumes 1037300 and "
      "1037304 have their own sound table, and they still fall back to this bank for the team-ups, Space and "
      "some E/V sounds. The `q_lvup_*` ult events of 1037304 use the same files as the normal ult. "
      "The `never_touch` list in `sounds.json` is every file of these moments that another bank also holds "
      "(other heroes, the shared impact and battle UI banks). Changing one of those could change them too.\n")
    tech = {}
    for a in rows:
        if a.get("tech"):
            tech.setdefault(a["tech"], []).append(a)
    for t, lst in tech.items():
        nums = [num[a["name"]] for a in lst]
        label = nums[0] if len(nums) == 1 else f"{nums[0]}-{nums[-1]}"
        w(f"- **{label} {cell(' / '.join(a['name'] for a in lst))}**: {cell(t)}")
    w("")

    w("## Checks\n")
    w("My check script is `plan/plan2.py` (`python magneto/plan/plan2.py --check` to only check, without "
      "`--check` it also rewrites `sounds.json`, this file and the previews, so swap a sound in the picks there "
      "and run it to hear the new preview). It reads the bank straight from the game and checks that every "
      "replaced or muted file is really played by its moment, that none is shared with another bank, that no "
      "file is in two picks or both replaced and muted, that no sound is used twice except the two repeats "
      "above, that every clip exists as an mp3 in `discord/`, and that every level stays inside the limits "
      "using the same leveling as `make_sounds.py`.\n")
    return "\n".join(out)
