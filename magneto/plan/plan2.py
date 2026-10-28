"""Discord Magneto sound plan, draft 3: picks, replace/mute lists from the kit map, checks against the bank
read from the game with the same leveling logic as scripts/make_sounds.py, previews, sounds.json and
SOUNDS_PLAN.md.

Clips: the 76 official Discord client sounds plus the 6 default soundboard sounds (mp3s in
magneto/discord, listed in inventory2.json). Previews use 44.1 kHz WAVs of the same mp3s.

Runs from two places, the same file in both:
  - the work folder (kit.json etc. in ../kit and ../discord, WAVs in ../discord/wav2)
  - magneto/plan in the repo (kit.json etc. in ./data, the mp3s get decoded to work/decoded/magneto_plan)

    python plan2.py            (check + write sounds.json, SOUNDS_PLAN.md and the previews)
    python plan2.py --check    (check only)
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, r"C:\Dr_WhatsApp\scripts")
from gamefiles import GameFiles  # noqa: E402
from hirc_map import HircMap  # noqa: E402
from paths import DEFAULT_PAKS  # noqa: E402
from wem import RATE, process, read_wav, wav_bytes  # noqa: E402
from wwise_bank import Bank  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Dr_WhatsApp\magneto"
if os.path.exists(os.path.join(HERE, "data", "kit.json")):  # the copy in magneto/plan
    DATA = os.path.join(HERE, "data")
    KIT, INV, USAGE = (os.path.join(DATA, f) for f in ("kit.json", "inventory2.json", "usage.json"))
    WAV = os.path.join(os.path.dirname(REPO), "work", "decoded", "magneto_plan")
    KIT_BANK = None
else:
    MAG = os.path.join(HERE, "..")
    KIT = os.path.join(MAG, "kit", "kit.json")
    INV = os.path.join(MAG, "discord", "inventory2.json")
    USAGE = os.path.join(MAG, "discord", "usage.json")
    WAV = os.path.join(MAG, "discord", "wav2")
    KIT_BANK = os.path.join(MAG, "kit", "bnk_sfx_1037001.bnk")
MP3 = os.path.join(REPO, "discord")
BANK = "Marvel/Content/WwiseAudio/bnk_sfx_1037001.bnk"
P = "sfx_1037001_"

TARGET, MAX_RMS, LIMIT = -22.0, -3.0, 12.0

kit = json.load(open(KIT, encoding="utf-8"))
_inv = json.load(open(INV, encoding="utf-8"))
inv = {s["name"]: s for s in _inv["sounds"] + _inv.get("soundboard", [])}
usage = json.load(open(USAGE, encoding="utf-8"))
moments = {}
for a in kit["abilities"] + kit["legacy_or_unused"]:
    for m in a.get("moments", []):
        moments[m["event"]] = m
for m in kit["movement_and_foley"]:  # these entries are moments themselves
    moments[m["event"]] = m
never = {int(k): v for k, v in kit["never_touch"].items()}


def main_of(ev):
    return list(moments[P + ev]["summary"]["main_media_replaceable"])


def extra_of(ev):
    return list(moments[P + ev]["summary"]["extra_layers_magneto_only"])


def std(*evs):
    """replace = kit main (all variants, Magneto-only), mute = Magneto-only layers under it"""
    rep, mute = [], []
    for e in evs:
        rep += [m for m in main_of(e) if m not in rep]
        mute += [m for m in extra_of(e) if m not in mute]
    return rep, mute


# ---------------------------------------------------------------------------------------------
# What each Discord sound is, for sound_desc in sounds.json and the plan md.
# ---------------------------------------------------------------------------------------------
NICE = {
    "message1": "the normal message ping (DMs, @mentions)",
    "bop_message1": "message ping from the Bop sound pack (Nitro)",
    "stream_user_joined": "a viewer joins the stream",
    "stream_started": "Go Live, a stream starts in your voice channel",
    "clip_save": "clip saved (you saved a clip or screenshot)",
    "soundboard_airhorn": "airhorn from the soundboard",
    "deafen": "you deafen yourself",
    "mention2": "the old @mention ping (Discord doesn't use it any more)",
    "undeafen": "you undeafen",
    "mute": "you mute your mic",
    "unmute": "you unmute your mic",
    "mention3": "the test ping when you switch your headset or mic",
    "asmr_message1": "message ping from the ASMR sound pack (Nitro)",
    "call_calling": "outgoing call, waiting for them to pick up",
    "call_ringing": "incoming call ringtone",
    "message2": "'friend started playing a game' notification",
    "user_join": "someone joins your voice channel",
    "disconnect": "you leave or drop from voice",
    "soundboard_sad_horn": "sad horn (sad trombone) from the soundboard",
    "lofi_message1": "message ping from the Lofi sound pack (Nitro)",
    "soundboard_quack": "quack from the soundboard",
    "ptt_start": "push to talk key pressed",
    "ptt_stop": "push to talk key released",
    "activity_launch": "an Activity starts in your voice channel",
    "discodo": "Discodo easter egg (click the home button 16 times)",
    "ddr-down": "down arrow key in the Ctrl+/ shortcuts popup (easter egg)",
    "activity_user_join": "someone joins the Activity you're in",
    "stage_waiting": "Stage waiting music (a Stage that hasn't started yet)",
    "bit_message1": "message ping from the Retro sound pack (Nitro)",
    "stream_user_left": "a viewer leaves the stream",
    "stream_ended": "a stream ends",
    "camera_on": "you turn your camera on",
    "camera_off": "you turn your camera off",
    "user_leave": "someone leaves your voice channel",
    "vibing_wumpus": "'Vibe with Wumpus' lofi track (take a break screen)",
}

# ---------------------------------------------------------------------------------------------
# The picks. why / gain_note / tech / src go to SOUNDS_PLAN.md; the rest is the sounds.json entry.
# gain_note is the plain version, tech has the ids, cents and bank names for the tech notes.
# ---------------------------------------------------------------------------------------------
PICKS = []


def pick(key, name, moment, sound, when, events, why, gain_note, replace, mute,
         mute_events=(), src="", tech="", prev_note="", **opt):
    PICKS.append(dict(key=key, name=name, moment=moment, sound=sound, sound_desc="Discord: " + NICE[sound],
                      when=when, events=[P + e for e in events], why=why, gain_note=gain_note, tech=tech,
                      replace=replace, mute=mute, mute_events=[P + e for e in mute_events], src=src,
                      prev_note=prev_note, **opt))


# ---- Left click: Iron Volley = the chat
pick("Left click", "Iron Volley", "each volley fired", "message1",
     "every Iron Volley shot (all 4 fire animations)",
     ["left_release"],
     "Iron Volley is you spamming the chat, so every volley is the message ping. The most famous "
     "Discord sound goes on the button you press the most, and it's short enough to never smear on fast fire.",
     "0 dB.",
     *std("left_release"), src="draft 2",
     tech="Enemies hear it 4 semitones lower: the enemy version plays the 3rd-person file at -400 cents and "
          "allies share that file at 0, so the pitch can only be right for one of them.")
pick("Left click", "Iron Volley burst", "orbs burst at the end of each volley", "bop_message1",
     "the orbs bursting after every volley",
     ["left_explo"],
     "The message landing: one soft gliding 'bop' when the orbs pop, so a volley goes 'ping... bop'. "
     "It's a single soft note, so it doesn't put a second tune on every shot.",
     "-6 dB, it follows every shot. The shared debris sound under it keeps playing.",
     *std("left_explo"), gain_db=-6.0, src="draft 2",
     tech="Only the Magneto-only crack and body layers change; the debris tail is in 47+ other banks.")

# ---- Right click: Mag-Cannon = streaming, bigger the more rings
pick("Right click", "Mag-Cannon (1 ring)", "fired with 1 ring", "stream_user_joined",
     "Mag-Cannon fired with 1 ring",
     ["right_release1_play"],
     "Small shot, small stream sound: 'a viewer joined'. The 2 and 3 ring shots go live for real.",
     "0 dB. Its close-up sweetener is muted.",
     *std("right_release1_play"), src="verifier fix")
for tier, rings, end, gain in ((2, "2 rings", 0.314, 1.0), (3, "3 rings, full", None, 2.0)):
    pick("Right click", f"Mag-Cannon ({rings})", f"fired with {rings}", "stream_started",
         f"Mag-Cannon fired with {rings}",
         [f"right_release{tier}_play"],
         {2: "The Go Live run (fast notes going up) cut after 4 notes: you're going live but the shot isn't "
             "full yet.",
          3: "The whole Go Live run, all 6 notes up to the top one: only the full-power shot finishes it."}[tier],
         f"{gain:+.0f} dB (2 / 3 rings go +1 / +2 dB)."
         + (" The vanilla metal sweetener under the full shot stays, it's shared with another hero."
            if tier == 3 else " Its close-up sweetener is muted."),
         *std(f"right_release{tier}_play"), start=0.0 if end else None, end=end, gain_db=gain,
         src="draft 2",
         tech="The 1.2 s full-shot sweetener 575470063 is also in bnk_sfx_1029001, so it isn't touched."
         if tier == 3 else "")
pick("Right click", "Mag-Cannon hit", "the cannon ball hits something", "clip_save",
     "a Mag-Cannon hit (also the full-energy hit)",
     ["right_impact_play"],
     "Hit marker: 'clip saved', as in clip that. Only Magneto's own metal hit layer gets it, the shared "
     "surface impact stays, so a hit still sounds like a hit.",
     "-2 dB. Only you hear it.",
     [584910738, 148345098, 229168851], [], gain_db=-2.0, src="draft 2",
     tech="The 3 Magneto-only 1.17 s layer files (584910738, 148345098, 229168851) are replaced; the main sound "
          "of this event is the shared impact library and is never touched.")
pick("Right click", "Mag-Cannon knock-back", "full-ring hit knocks the target back", "soundboard_airhorn",
     "a full-ring Mag-Cannon knocks someone back (only you and the person hit hear it)",
     ["right_release_debuff_play"],
     "The big play gets the airhorn. You send someone flying across the map and both of you hear it.",
     "-2 dB, it's a long solid blast so it sits a bit lower.",
     *std("right_release_debuff_play"), gain_db=-2.0, src="verifier fix (soundboard)",
     tech="The game plays this event at +2/+3 dB; the clip is leveled down to match.")

# ---- Left Shift: Metallic Curtain = deafen
pick("Left Shift", "Metallic Curtain up", "curtain raised", "deafen",
     "raising the Metallic Curtain",
     ["shift_release_play"],
     "Deafen: the wall goes up and nothing they send gets through to you.",
     "0 dB. The close-up metal sweetener under it is muted.",
     *std("shift_release_play"), src="draft 2")
pick("Left Shift", "Metallic Curtain blocks a shot", "each shot the curtain stops", "mention2",
     "each projectile the curtain stops, can be several a second",
     ["shift_impact_self_play"],
     "Every blocked shot is a tiny bright 'tink' from the old @mention ping, like a ricochet. Shortest and "
     "quietest pick because it can fire several times a second.",
     "-8 dB, only the start of the file: a quiet trill and one bright note, about 0.12 s.",
     *std("shift_impact_self_play"), start=0.0, end=0.15, gain_db=-8.0, src="draft 2 (cut fixed)",
     tech="Some of the tink files are shared between your version (pitched +2 semitones by the game) and "
          "everyone else's (no pitch), so other people hear some of the tinks 2 semitones lower.")
pick("Left Shift", "Metallic Curtain down", "curtain drops / ends", "undeafen",
     "the Metallic Curtain ending",
     ["shift_end_play"],
     "Undeafen: the wall is gone, you can hear (and get hit by) everything again.",
     "0 dB. The sweetener under it is muted.",
     *std("shift_end_play"), src="draft 2")

# ---- E / F: Bulwark = mute
pick("E and F", "Bulwark shield up", "shield appears on the target", "mute",
     "Metal Bulwark (E, on an ally) or Iron Bulwark (F, on himself) appearing",
     ["e_child_start_play"],
     "The shield mutes the damage. E and F both use this moment. It goes on 'shield appears' and not on "
     "the cast, because the cast sound is shared with Rogue (she can copy Iron Bulwark).",
     "0 dB.",
     *std("e_child_start_play"), src="draft 2",
     tech="Every file of e_release_play is also in Rogue's bank. The game plays this event at +2 dB for you, "
          "-20 for allies, -13 for enemies; the clip is leveled to your version.")
pick("E and F", "Bulwark shield down", "shield breaks / expires", "unmute",
     "the Bulwark shield breaking or running out",
     ["e_child_end_play"],
     "Unmute: the damage can reach them again.",
     "0 dB. The sweetener under it is muted.",
     *std("e_child_end_play"), src="draft 2")

# ---- Passive rings: one mention3 ping, 1 / 2 / 3 times
RING_CUT = (0.137, 0.26)  # the 2nd ping of the file on its own (the loudest, clean decay)
RING_EVERY = 0.12         # about the gap between the pings in the file
for n_ring, gain, why in (
        (1, -2.0, "One ping of the headset test ping, so the rings count out loud: ring 1 = 1 ping."),
        (2, -1.0, "Ring 2 = the same ping twice, 1 dB up."),
        (3, 1.0, "Ring 3 = the same ping three times: full Mag-Cannon is ready.")):
    pick("Passive", f"Iron ring {n_ring}" + (" (full)" if n_ring == 3 else ""),
         f"{['1st', '2nd', '3rd'][n_ring - 1]} iron ring forms", "mention3",
         f"the {['1st', '2nd', '3rd'][n_ring - 1]} iron ring forming"
         + (": Mag-Cannon is at full power" if n_ring == 3 else ""),
         [f"passive_absorb{n_ring}_play"], why,
         f"{gain:+.0f} dB (rings go -2 / -1 / +1 dB)"
         + ("." if n_ring == 1 else f", the ping {n_ring} times, {RING_EVERY} s apart.")
         + " Only you and enemies hear ring sounds, the game mutes them for allies.",
         *std(f"passive_absorb{n_ring}_play"), start=RING_CUT[0], end=RING_CUT[1], gain_db=gain,
         src="verifier fix",
         tech="Its vanilla ring layer is muted, the battle-UI tick under it stays (it's in bnk_ui_battle). "
              "The file's 3rd ping is about 15 dB quieter than the first two, so every ring uses the 2nd ping.",
         **({"repeat": n_ring, "every": RING_EVERY} if n_ring > 1 else {}))

# ---- R: reload
pick("R", "Reload", "reload", "asmr_message1",
     "reloading Iron Volley",
     ["r_release_play"],
     "Two soft clicky taps from the ASMR pack's message ping. It has no tune, so a reload sounds like a "
     "real reload and never gets mixed up with a ping or the Go Live run.",
     "-2 dB, the last 2 taps. The long sweetener and the three ring-spin sounds are muted so the reload is "
     "just the taps.",
     *std("r_release_play"), mute_events=["r_absorb1_play", "r_absorb2_play", "r_absorb3_play"],
     start=0.33, gain_db=-2.0, src="draft 2", tech="Cut from 0.33 s. Mutes r_absorb1-3 too.")

# ---- Q: Meteor M = a whole Discord call
LEAD_IN = 0.5
RING_LOOP = inv["call_ringing"]["duration_s"]  # Discord loops the whole 5.369 s file
pick("Q", "Meteor M cast", "ult cast", "call_calling",
     "pressing Q (with 'Fear Magneto!')",
     ["q_start"],
     "Pressing Q is hitting the call button: the first 'boo-doo-doo' of the outgoing calling tone. Only the "
     "first half, so the ringtone can start right after it.",
     "+2 dB, cut after the first phrase. The vanilla swell under it is muted.",
     *std("q_start"), start=0.0, end=0.95, gain_db=2.0, src="verifier fix")
pick("Q", "Meteor M forming", "meteor forming, until it's thrown", "call_ringing",
     "while the meteor forms, until it's thrown",
     ["q_child_start_play"],
     "THE Discord ringtone while the meteor forms, so everyone around hears 'you're getting called' = ult "
     "coming. Throwing the meteor stops it (the game already does that), so throwing = picking up.",
     f"0 dB, full level on purpose, it's the biggest warning in the kit. It starts {LEAD_IN} s after the "
     "forming starts so the calling tone gets out first. The vanilla rumble layer is muted.",
     *std("q_child_start_play"), repeat=1, every=RING_LOOP, lead_in=LEAD_IN, src="verifier fix",
     prev_note=" (full ring, cut short when you throw)",
     tech="q_release has stop actions (0x103) on every forming target: 111860807, 507761464, 524972516 (you), "
          "551659154 (allies), 125012237 (enemies). q_child_damage_play only has play actions.")
pick("Q", "Meteor absorbs a shot", "each shot the meteor swallows", "message2",
     "each projectile the meteor swallows",
     ["q_child_absorb_play"],
     "Every bullet the meteor eats is a message landing while the phone rings: one low note (the "
     "ringtone's key), the first note of the 'friend started playing' ping. Quiet, it can fire a lot.",
     "-8 dB, first note only. The shared impact thunks under it stay.",
     main_of("q_child_absorb_play"), [], start=0.0, end=0.141, gain_db=-8.0, src="draft 2",
     tech="Only the 15 Magneto-only zap files get the clip. The one Magneto-only extra sits in the same random "
          "pick as the 3 shared thunks, so it isn't muted (1 absorb in 4 would lose its thunk).")
rel_main = [744393175, 143313839, 824079349]  # self main = ally/enemy layer
rel_3p = [831444564, 1000982248, 234569062]  # ally/enemy main = self layer
pick("Q", "Meteor M thrown", "meteor thrown", "user_join",
     "throwing the meteor",
     ["q_release"],
     "They picked up. In a real call the join sound plays the moment the other side answers, and the "
     "ringing stops right before it.",
     "+1 dB. The game plays two throw sounds at once, so only one gets the clip and the other is muted, "
     "otherwise everyone would hear it doubled.",
     rel_main, rel_3p + [841967870], gain_db=1.0, src="draft 2",
     tech="Close-up set 744393175/143313839/824079349 gets the clip, 3rd-person set 831444564/1000982248/"
          "234569062 and the 0.7 s sweetener 841967870 are muted (the two sets are crossed between you and "
          "everyone else).")
explo_shared = [465763209, 659074377, 75594779]  # played by all three versions (enemy main, layer for you/allies)
explo_self_main = [414507073]
explo_ally_main = [101597121, 508910138, 191546796]
pick("Q", "Meteor M impact", "meteor impact", "disconnect",
     "the meteor landing",
     ["q_explo"],
     "Then you hang up on everyone it hits.",
     "+2 dB. The big shared explosion under it keeps playing. Everyone hears the clip once.",
     explo_shared, explo_self_main + explo_ally_main + extra_of("q_explo"), gain_db=2.0, src="verifier fix",
     tech="Only the set every version plays (465763209, 659074377, 75594779) gets the clip. Your 1.2 s main "
          "crack 414507073 and the ally-only set 101597121/508910138/191546796 are muted with the other "
          "Magneto-only layers, so nobody hears two copies. Allies hear it 1.5 semitones lower (the game's "
          "-150 cents on their version, shared file). The 4-6 s explosion tails are in 20-32 other banks and "
          "stay.")
pick("Q", "Meteor M shattered", "meteor shattered before it's thrown", "soundboard_sad_horn",
     "the meteor breaking (overload or destroyed) before it's thrown",
     ["q_child_damage_play"],
     "They broke your ult before you could throw it: sad horn from the soundboard.",
     "0 dB. The vanilla crash layer is muted.",
     *std("q_child_damage_play"), src="verifier fix (soundboard)")

# ---- V: melee
pick("V", "Melee", "sword swing", "lofi_message1",
     "the quick melee swing",
     ["v_release_play"],
     "A very high flick falling onto a bell, about as close to a blade 'shing' as Discord gets. It's "
     "the Lofi pack's message ping.",
     "0 dB. The swish sweetener is muted.",
     *std("v_release_play"), src="draft 2")
pick("V", "Melee hit", "melee connects (only you hear it)", "soundboard_quack",
     "the melee connecting (only you hear it)",
     ["v_impact_play"],
     "Bonk them and they quack. The soundboard quack is short, so it works as a hit marker.",
     "-3 dB.",
     *std("v_impact_play"), gain_db=-3.0, src="verifier fix (soundboard)")

# ---- Space: Magnetic Descent = push to talk (only the magnetic swell, the cloth/air foley stays)
pick("Space", "Magnetic Descent start", "hold jump, slow fall starts", "ptt_start",
     "holding jump to float down",
     ["space_drop_start_play"],
     "Holding jump to float is holding your push to talk key: the PTT click when you press it.",
     "-3 dB. Only the magnetic swell gets it, the cloth and air whoosh stays.",
     [766089542, 230208889], [1069493481], gain_db=-3.0, src="draft 2",
     tech="Replaces the swell 766089542/230208889, mutes the 0.6 s extra layer 1069493481.")
pick("Space", "Magnetic Descent end", "let go of jump / land", "ptt_stop",
     "letting go of jump / landing",
     ["space_drop_end_play"],
     "Letting go = releasing push to talk: the lower click out.",
     "-4 dB. Only the hum release gets it, the cloth sound stays.",
     [336935997, 550624621], [721068151], gain_db=-4.0, src="draft 2",
     tech="Replaces the 2 s hum release 336935997/550624621, mutes the 0.4 s extra layer 721068151.")

# ---- C: Metallic Chaos (Scarlet Witch) = an Activity
pick("C", "Metallic Chaos", "team-up activated", "activity_launch",
     "activating the Scarlet Witch team-up",
     ["103796_c_sp2_release_play"],
     "You and Wanda start an Activity together: the rising 'Activity started' run.",
     "+1 dB. The sweetener is muted.",
     *std("103796_c_sp2_release_play"), gain_db=1.0, src="draft 2")
rep, mute = std("103796_left_sp2_release_play", "left_sp_release_play")
pick("C", "Chaos Greatsword swing", "greatsword swing (left click in the team-up)", "discodo",
     "each Chaos Greatsword swing",
     ["103796_left_sp2_release_play", "left_sp_release_play"],
     "The Discodo easter egg chime. Turn Discodo on in Discord and this becomes your message ping, so "
     "it's the team-up version of Iron Volley's ping (both are left click), but sparkly so the two never mix.",
     "0 dB, cut after 4 notes. The sweetener is muted.",
     rep, mute, start=0.0, end=0.548, src="draft 2",
     tech="The old swing event left_sp_release_play is in too because costumes 1037100/101/500/501 still use it.")
pick("C", "Chaos Greatsword hit", "greatsword connects", "ddr-down",
     "a greatsword hit (you and the person hit hear it)",
     ["103796_left_sp2_impact_play"],
     "A little arcade beep from Discord's hidden Ctrl+/ arrow key game, as a hit marker.",
     "-3 dB, cut before its echo.",
     *std("103796_left_sp2_impact_play"), start=0.0, end=0.386, gain_db=-3.0, src="draft 2")
pick("C", "Chaos barrage start", "barrage starts (right click in the team-up)", "activity_user_join",
     "starting the Chaos Greatsword barrage",
     ["103798_right_sp2_start_play"],
     "The swords join in: 'someone joined the Activity', same family as the team-up start.",
     "0 dB. The sweetener is muted.",
     *std("103798_right_sp2_start_play"), src="verifier fix")
pick("C", "Chaos barrage charging", "barrage charging (5.3 s, everyone hears it)", "stage_waiting",
     "while the barrage charges (5.3 s)",
     ["103798_right_sp2_charge_play"],
     "The Stage waiting music: the drums at the start of the track, while you wait for the show to start. "
     "Cut right before the tune kicks in, so the barrage is the drop.",
     "-6 dB, the drums and the fill, about the length of the vanilla charge. Its vanilla layer is muted.",
     *std("103798_right_sp2_charge_play"), start=1.56, end=6.95, gain_db=-6.0, src="verifier fix",
     tech="Cut 1.56-6.95 s of the 92.5 s track: first kick at 1.6 s, the fill ends at 6.85 s, the melody starts "
          "at 7.15 s. The clip is 5.39 s against the 5.31 s vanilla charge.")
pick("C", "Chaos barrage sword", "barrage: each sword fired", "bit_message1",
     "every greatsword the barrage fires",
     ["103798_right_sp2_release_play"],
     "A short retro 'pew' for every sword. It's the Retro pack's message ping, cut before its low thump "
     "so it's short enough to repeat every tick.",
     "-3 dB. The loud sweetener is muted.",
     *std("103798_right_sp2_release_play"), start=0.0, end=0.32, gain_db=-3.0, src="draft 2")
pick("C", "Chaos barrage mark", "barrage: a mark is burned (only you hear it)", "stream_user_left",
     "a mark being used up during the barrage (only you hear it)",
     ["103798_right_sp2_lv2_play"],
     "Each mark the barrage burns is a viewer leaving the stream.",
     "-3 dB. Its layer is muted.",
     *std("103798_right_sp2_lv2_play"), gain_db=-3.0, src="draft 2")
pick("C", "Chaos barrage last mark", "barrage: the last mark is burned (only you hear it)", "stream_ended",
     "the last mark used up: the barrage is over (only you hear it)",
     ["103798_right_sp2_lv3_play"],
     "Last mark gone: stream over.",
     "-1 dB. Its layer is muted.",
     *std("103798_right_sp2_lv3_play"), gain_db=-1.0, src="draft 2")

# ---- X: Magnetic Resonance (Emma Frost) = camera
pick("X", "Magnetic Resonance", "projection cast", "camera_on",
     "casting the Emma Frost projection",
     ["103703_x_sp2_release_play"],
     "The projection is a live video of you running around somewhere else: camera on.",
     "0 dB. The ally version's layer is muted.",
     *std("103703_x_sp2_release_play"), src="draft 2")
pick("X", "Magnetic Resonance end", "projection destroyed or recalled", "camera_off",
     "the projection being destroyed or recalled",
     ["103703_x_sp2_end_play"],
     "Camera off: the copy is gone. Allies don't hear this one, the game mutes it for them.",
     "0 dB. The sweetener is muted.",
     *std("103703_x_sp2_end_play"), src="draft 2")

# ---- Death: Magneto left the channel
pick("Death", "Magneto dies", "death fall (back, front, sides, chain-sawed)", "user_leave",
     "Magneto dying (the body fall of every death animation)",
     ["fall_b_play", "fall_f_play", "fall_lr_play", "fall_chain_play"],
     "Magneto left the channel. Everyone near you hears it when you go down, every match.",
     "-2 dB. Replaces the body fall sound.",
     *std("fall_b_play", "fall_f_play", "fall_lr_play", "fall_chain_play"), gain_db=-2.0, src="verifier fix",
     tech="fall_b/f/lr/chain_play fire at t=0.01-0.03 of Dead_B/F/L/R and ChainSawed. All Magneto-only, no "
          "other hero or costume bank. The generic fall_play stays vanilla (nothing says when it plays).")

# optional, not in "abilities" (make_sounds ignores this key): move it into "abilities" to use it
OPTIONAL = [
    dict(key="C", name="Metallic Chaos timer", sound="vibing_wumpus", sound_desc="Discord: " + NICE["vibing_wumpus"],
         when="under the whole team-up (8.9 s, only you hear it)", gain_db=-10.0, start=0.0, end=8.78,
         events=[P + "103796_c_sp2_count_play"], replace=main_of("103796_c_sp2_count_play"),
         mute=extra_of("103796_c_sp2_count_play"),
         note="Quiet lofi music under the team-up, cut on the beat before 8.8 s; the music stopping is your "
              "'time's up'. Off because the vanilla timer hum is useful info. The rare ringtone "
              "(call_ringing_beat) works here too: only you hear this one, so nobody mixes it up with the ult."),
]

# sources: every Discord sound the plan uses (picks + optional), official name + where it came from
SOURCES = {}
for a in PICKS + OPTIONAL:
    s = a["sound"]
    where = "Discord soundboard" if inv[s].get("pack") == "soundboard" else "Discord web client"
    SOURCES[s] = f"{NICE[s]} ({where}, {inv[s]['url']})"

REPEATS_OK = {"stream_started": "Mag-Cannon 2 and 3 rings", "mention3": "iron rings"}


# ---------------------------------------------------------------------------------------------
def resample(a, rate, target=RATE):
    """FFT resample, the same way the wav2 files were made"""
    if rate == target:
        return a
    n, m = len(a), int(round(len(a) * target / rate))
    spec = np.fft.rfft(a, axis=0)
    out = np.zeros((m // 2 + 1, a.shape[1]), dtype=complex)
    k = min(len(spec), len(out))
    out[:k] = spec[:k]
    return np.fft.irfft(out, n=m, axis=0) * (m / n)


def load_clip(name):
    """44.1 kHz stereo WAV of a Discord mp3 (decoded with scripts/mf_decode.py the first time)"""
    wav = os.path.join(WAV, name + ".wav")
    if not os.path.exists(wav):
        import mf_decode
        ch, rate, bits, pcm = mf_decode.decode(os.path.abspath(os.path.join(MP3, name + ".mp3")))
        a = np.frombuffer(pcm, dtype="<i2").astype(np.float64).reshape(-1, ch)
        a = np.repeat(a, 2, axis=1) if ch == 1 else a[:, :2]
        os.makedirs(WAV, exist_ok=True)
        open(wav, "wb").write(wav_bytes(resample(a, rate)))
    return read_wav(wav)


def ring(clip, repeat, every):
    """the clip `repeat` times, one starting every `every` seconds (overlap-added if every is short)"""
    step = int(round(every * RATE))
    if repeat > 1 and step < 1:
        raise ValueError("every must be > 0 when repeat > 1")
    body = np.zeros(((repeat - 1) * step + len(clip), 2))
    for k in range(repeat):
        body[k * step:k * step + len(clip)] += clip
    return body


def render(a):
    """(preview clip, game clip), the same steps as make_sounds plus ringing (repeat / every / lead_in):
    game clip = lead_in s of silence, then the clip `repeat` times, one every `every` s. The preview is
    the rings without the lead-in (the sequence previews use the game clip, lead-in included)."""
    clip = process(load_clip(a["sound"]), a.get("start"), a.get("end"))
    game = clip
    if a.get("repeat"):
        body = ring(clip, a["repeat"], a.get("every", 0.0))
        game = np.concatenate([np.zeros((int(round(a.get("lead_in", 0) * RATE)), 2)), body])
        clip = body
    if a.get("pad_to"):
        pad = int(a["pad_to"] * RATE) - len(game)
        if pad > 0:
            game = np.concatenate([game, np.zeros((pad, 2))])
    return clip, game


def main():
    check_only = "--check" in sys.argv
    game = GameFiles(DEFAULT_PAKS)
    data, src = game.read(BANK)
    if KIT_BANK and os.path.exists(KIT_BANK):
        print(f"bank from {src}: {len(data)} bytes, same as kit copy: {data == open(KIT_BANK, 'rb').read()}")
    else:
        print(f"bank from {src}: {len(data)} bytes")
    bank = Bank(data)
    names = set()
    for a in PICKS + OPTIONAL:
        for e in a["events"] + a.get("mute_events", []):
            names |= {e, e + "_p2", e + "_p3"}
    hm = HircMap(bank, names)
    by_name = {n: eid for eid, n in hm.events().items()}

    def variants(e):
        assert e in by_name, f"event {e} not in bank"
        return [v for v in (e, e + "_p2", e + "_p3") if v in by_name]

    problems, used, report = [], {}, []
    muted_all = {}
    # the clips exist (preview WAV here, mp3 in the repo for the build) and the cuts are inside the file
    for a in PICKS + OPTIONAL:
        s = a["sound"]
        if s not in inv:
            problems.append(f"{a['name']}: {s} is not in inventory2.json")
            continue
        if not os.path.exists(os.path.join(MP3, s + ".mp3")):
            problems.append(f"{a['name']}: no {s}.mp3 in {MP3}")
        elif not os.path.exists(os.path.join(WAV, s + ".wav")):
            load_clip(s)  # decode it now
        for k in ("start", "end"):
            if a.get(k) is not None and not 0 <= a[k] < inv[s]["duration_s"]:
                problems.append(f"{a['name']}: {k} {a[k]} outside the {inv[s]['duration_s']} s file")
        if a.get("start") is not None and a.get("end") is not None and a["start"] >= a["end"]:
            problems.append(f"{a['name']}: start {a['start']} is not before end {a['end']}")
        if a.get("repeat", 1) > 1 and not a.get("every", 0) > 0:
            problems.append(f"{a['name']}: repeat {a['repeat']} needs every > 0")
    for i, a in enumerate(PICKS, 1):
        rep, mute = [int(m) for m in a["replace"]], [int(m) for m in a["mute"]]
        if not rep:
            problems.append(f"{a['name']}: nothing to replace")
        # every replace / mute media is played by one of the events
        allchains = {}
        for e in a["events"]:
            for v in variants(e):
                for m, c in hm.media_chains(by_name[v]).items():
                    allchains.setdefault(m, []).append((v, c))
        for m in rep:
            if m not in allchains:
                problems.append(f"{a['name']}: replace {m} not played by its events")
            if m in never:
                problems.append(f"{a['name']}: replace {m} is never_touch ({never[m]})")
        for m in mute:
            if m in never:
                problems.append(f"{a['name']}: mute {m} is never_touch ({never[m]})")
            if m in rep:
                problems.append(f"{a['name']}: {m} both replaced and muted")
            if m not in allchains:
                problems.append(f"{a['name']}: mute {m} not played by its events")
            if m in muted_all and muted_all[m] != a["name"]:
                problems.append(f"mute {m} in both {muted_all[m]} and {a['name']}")
            muted_all[m] = a["name"]
        # make_sounds leveling (explicit replace list, same code path as make_sounds)
        levels = {}
        for e in a["events"]:
            base = hm.media_chains(by_name[e])
            base_main = [m for m in rep if m in base]
            ref_vol = sum(base[m][0] for m in base_main) / len(base_main) if base_main else None
            for v in variants(e):
                chains = hm.media_chains(by_name[v])
                for m in [m for m in rep if m in chains]:
                    if m in used and used[m] != a["name"]:
                        problems.append(f"media {m} in both {used[m]} and {a['name']}")
                    if m in used:
                        continue
                    used[m] = a["name"]
                    vol, pitch = base[m] if m in base_main else (
                        ref_vol if ref_vol is not None else chains[m][0], chains[m][1])
                    if not a.get("pitch_fix", True):
                        pitch = 0
                    raw = TARGET - vol + a.get("gain_db", 0.0)
                    lvl = max(min(raw, MAX_RMS), -40.0)
                    levels[m] = (vol, pitch, lvl, raw)
                    if raw > MAX_RMS or raw < -40:
                        problems.append(f"{a['name']}: media {m} level {raw:.1f} outside -40..{MAX_RMS} "
                                        f"(clamped to {lvl:.1f})")
        missing = [m for m in rep if m not in used or used[m] != a["name"]]
        if missing:
            problems.append(f"{a['name']}: replace media never reached by the leveling loop: {missing}")
        # what each listener hears: Discord copies (with in-game pitch), vanilla layers left
        heard = {}
        for e in a["events"]:
            for v in variants(e):
                chains = hm.media_chains(by_name[v])
                copies, left = [], []
                for m, (vol, pitch) in chains.items():
                    if m in rep:
                        copies.append((m, vol, pitch - (levels[m][1] if m in levels else 0)))
                    elif m not in mute:
                        left.append(m)
                kg = next((vv["groups"] for vv in moments.get(e, {}).get("variants", []) if vv["event"] == v), [])
                groups = [g for g in kg if set(g["media"]) & set(rep)]
                heard[v] = dict(groups=len(groups), muted_by_mix=all(c[1] < -60 for c in copies) if copies else False,
                                pitches=sorted({round(c[2]) for c in copies}),
                                vanilla_left=sorted(set(left)))
                if len(groups) > 1:
                    problems.append(f"{a['name']}: {v} plays {len(groups)} copies of the clip at once")
        a["_levels"], a["_heard"] = levels, heard
        report.append(a)

    # mute_events media must not be replaced anywhere
    for a in PICKS:
        for e in a["mute_events"]:
            for v in variants(e):
                m, x = hm.split_event(by_name[v])
                for mm in m + x:
                    if mm in used:
                        problems.append(f"{a['name']}: mute_event media {mm} is replaced by {used[mm]}")
                    if mm in never:
                        print(f"   note: {e} media {mm} is never_touch, make_sounds skips it")
    for m, n in muted_all.items():
        if m in used:
            problems.append(f"muted media {m} ({n}) is replaced by {used[m]}")
    # optional entries don't clash with the main ones
    for o in OPTIONAL:
        for m in o["replace"] + o["mute"]:
            if m in used or m in muted_all:
                problems.append(f"optional {o['name']}: {m} already used by {used.get(m, muted_all.get(m))}")
            if m in never:
                problems.append(f"optional {o['name']}: {m} is never_touch")

    # repeats: a sound on more than one pick must be a deliberate ladder inside one ability
    by_sound = defaultdict(list)
    for a in PICKS:
        by_sound[a["sound"]].append(a)
    for s, lst in by_sound.items():
        if len(lst) > 1 and s not in REPEATS_OK:
            problems.append(f"{s} is on {len(lst)} picks: {[x['name'] for x in lst]}")

    for a in report:
        h = a["_heard"]
        lv = [v[2] for v in a["_levels"].values()]
        clip, g = render(a)
        a["_len"], a["_game_len"] = len(clip) / RATE, len(g) / RATE
        print(f"{a['key']:10} {a['name']:32} {a['sound']:22} rep {len(a['replace']):2} mute {len(a['mute']):2} "
              f"level {min(lv):6.1f}..{max(lv):6.1f}  clip {a['_len']:.3f}s" +
              (f" game {a['_game_len']:.3f}s" if a['_game_len'] != a['_len'] else ""))
        for v, d in h.items():
            flag = "  <-- muted by the mix" if d["muted_by_mix"] else ""
            dbl = f"  x{d['groups']} copies" if d["groups"] > 1 else ""
            print(f"      {v[len(P):]:40} pitch {d['pitches']} vanilla left {len(d['vanilla_left'])}{dbl}{flag}")
    all_lv = [v[2] for a in report for v in a["_levels"].values()]
    print(f"\n{len(PICKS)} picks, {len(by_sound)} different Discord sounds, "
          f"{len(used)} media replaced, {len(muted_all)} muted, levels {min(all_lv):.1f}..{max(all_lv):.1f} dB")
    print("repeats:", {s: len(v) for s, v in by_sound.items() if len(v) > 1})
    print("\nPROBLEMS:" if problems else "\nno problems", *problems, sep="\n  ")
    if problems:
        sys.exit(1)
    if check_only:
        return
    write_outputs(report, min(all_lv), max(all_lv))


def fmt_trim(a):
    s, e = a.get("start"), a.get("end")
    src = inv[a["sound"]]["duration_s"]
    if s is None and e is None:
        return f"full ({src:.2f} s file)"
    return f"{s or 0:.3f}-{e:.3f} s" if e else f"from {s:.3f} s to the end ({src:.2f} s file)"


# the ult strung together: (file label, [(pick, start time, stop time or None)])
SEQS = [
    ("quick throw at 2.5 s", [("Meteor M cast", 0.0, None), ("Meteor M forming", 0.0, 2.5),
                              ("Meteor M thrown", 2.5, None), ("Meteor M impact", 3.9, None)]),
    ("late throw at 5.6 s", [("Meteor M cast", 0.0, None), ("Meteor M forming", 0.0, 5.57),
                             ("Meteor M thrown", 5.57, None), ("Meteor M impact", 6.97, None)]),
    ("shattered at 3.5 s", [("Meteor M cast", 0.0, None), ("Meteor M forming", 0.0, None),
                            ("Meteor M shattered", 3.5, None)]),
]


def write_outputs(report, lv_min, lv_max):
    prev = os.path.join(REPO, "preview")
    os.makedirs(prev, exist_ok=True)
    # delete ONLY the old generated preview WAVs, keep every PNG and anything else
    deleted = []
    for f in sorted(glob.glob(os.path.join(prev, "*.wav"))):
        b = os.path.basename(f)
        if re.match(r"^\d\d .*\.wav$", b) or re.match(r"^Q - Meteor M sequence.*\.wav$", b):
            os.remove(f)
            deleted.append(b)
    print(f"deleted {len(deleted)} old preview wavs")
    rows = []
    written = []
    for i, a in enumerate(report, 1):
        clip, game = render(a)
        fn = re.sub(r'[\\/:*?"<>|]', "-", f"{i:02d} {a['key']} - {a['name']}{a.get('prev_note', '')}.wav")
        open(os.path.join(prev, fn), "wb").write(wav_bytes(clip))
        a["_file"], a["_len"], a["_game_len"] = fn, len(clip) / RATE, len(game) / RATE
        a["_trim"] = fmt_trim(a)
        rows.append(a)
        written.append(fn)
        print(f"wrote {fn} ({len(clip) / RATE:.2f} s)")

    # the ult strung together with example timing: cast and forming start together (the forming clip
    # has its lead-in), the throw stops the ringing, impact 1.4 s after the throw. The shatter has no stop
    # for the ringing (same as the vanilla rumble). Each clip at its preview level + its gain_db.
    by = {a["name"]: a for a in rows}
    seq_files = []
    for label, seq in SEQS:
        ends = []
        parts = []
        for name, t, stop in seq:
            a = by[name]
            _, g = render(a)
            g = g * 10 ** (a.get("gain_db", 0.0) / 20)
            if stop is not None:
                g = g[:int((stop - t) * RATE)].copy()
                n = min(int(0.03 * RATE), len(g))
                g[-n:] *= np.linspace(1, 0, n)[:, None]
            parts.append((int(t * RATE), g))
            ends.append(int(t * RATE) + len(g))
        mix = np.zeros((max(ends) + int(0.3 * RATE), 2))
        for s, g in parts:
            mix[s:s + len(g)] += g
        mix *= 10 ** (-1 / 20) * 32768 / np.abs(mix).max()
        seq_name = f"Q - Meteor M sequence ({label}).wav"
        open(os.path.join(prev, seq_name), "wb").write(wav_bytes(mix))
        written.append(seq_name)
        seq_files.append((seq_name, label, seq, len(mix) / RATE))
        print(f"wrote {seq_name} ({len(mix) / RATE:.2f} s)")

    keys = ["key", "name", "sound", "sound_desc", "when", "start", "end", "gain_db", "pitch_fix",
            "repeat", "every", "lead_in", "pad_to", "prev_note", "events", "replace", "mute", "mute_events"]
    abilities = []
    for a in rows:
        d = {}
        for k in keys:
            if k in a and a[k] not in (None, [], (), ""):
                d[k] = a[k]
        if d.get("start") == 0.0 and "end" not in d:
            d.pop("start")
        if d.get("gain_db") == 0.0:
            d.pop("gain_db")
        abilities.append(d)
    k48 = sorted({a["sound"] for a in rows + OPTIONAL} & {n for n, s in inv.items() if "48000" in s["original_format"]})
    rings = [a["name"] for a in rows if a.get("repeat")]
    cfg = {
        "hero": "Magneto (1037), default costume 1037001",
        "dir": "magneto",
        "src": "discord",
        "bank": BANK,
        "pak": "70_DiscordMagnetoSounds_9999999_P.pak",
        "target_db": TARGET,
        "_notes": [
            "Built by scripts/build_magneto.py (make_sounds.py + build_audio.py) into magneto/dist/~mods.",
            "Clips: the official Discord client sounds (mp3, from discord.com/assets) and the default soundboard "
            "sounds (soundboard_*.mp3, from cdn.discordapp.com/soundboard-sounds/<id>) in magneto/discord "
            "(the 'src' folder). Clips that aren't 44.1 kHz get resampled when they're decoded.",
            f"'repeat' / 'every' / 'lead_in' ({', '.join(rings)}): game clip = lead_in s of silence, "
            "then the clip 'repeat' times, one every 'every' s. 'prev_note' is added to the preview file name.",
            "'optional_abilities' is ignored by make_sounds; move an entry into 'abilities' to use it.",
            "Levels: the same rule as Iron Man (target_db against the game's own volume on each file). "
            "The ally versions the game mutes (-100 dB) are never used as the reference, make_sounds "
            "levels against the self version.",
        ],
        "sources": SOURCES,
        "never_touch": {str(k): v for k, v in sorted(never.items())},
        "abilities": abilities,
        "optional_abilities": [{k: v for k, v in o.items() if k != "note"} | {"note": o["note"]} for o in OPTIONAL],
        "max_rms_db": MAX_RMS,
        "limit_db": LIMIT,
    }
    open(os.path.join(REPO, "sounds.json"), "w", encoding="utf-8").write(
        json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
    json.dump([{k: v for k, v in a.items() if not k.startswith("_levels")} for a in rows],
              open(os.path.join(HERE, "picks_resolved2.json"), "w", encoding="utf-8"), indent=1, default=str)
    from plan2_md import render_md
    open(os.path.join(REPO, "SOUNDS_PLAN.md"), "w", encoding="utf-8").write(
        render_md(rows, OPTIONAL, inv, usage, NICE, seq_files, LEAD_IN, k48, (lv_min, lv_max)))
    print("wrote sounds.json, SOUNDS_PLAN.md")
    json.dump({"deleted": deleted, "written": written},
              open(os.path.join(HERE, "files_written.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
