# Discord Magneto: sound plan

This is the plan the sound pak is built from: every pick, why, the cuts and gains, and one preview per moment in `preview/`. `sounds.json` (same format as `ironman/sounds.json`) is what `scripts\build_magneto.py` builds. To swap a sound, change it in `plan/plan2.py`, run it, listen, then rebuild.

**The previews are all at the same volume.** They're cut and leveled the same way `make_sounds.py` does it, but the Gain column below only gets added in game. So a -8 dB pick will be a lot quieter in game than its preview, and a +2 dB one a bit louder. The three ult sequence files do have the gains in.

## Fixed since the second draft

- **Soundboard sounds are in.** Quack, airhorn and sad horn are used; cricket, golf clap and ba dum tss are downloaded too (`discord/soundboard_*.mp3`). They come straight from Discord's CDN, no login needed.
- **Iron rings count properly now.** The file's 3rd ping is about 15 dB quieter than the other two, so the full ring sounded almost like ring 2. Now every ring is the same single ping, played 1, 2 or 3 times.
- **Mag-Cannon 1 ring** is 'a viewer joined the stream' instead of two low notes of Go Live. 2 rings is Go Live cut after 4 notes, 3 rings the whole run.
- **Ult timing.** The cast is only the first 'boo-doo-doo' of the calling tone now, and the ringtone starts 0.5 s after it, so the ring takes about as long as the vanilla forming sound. There are three ult sequence previews (quick throw, late throw, meteor broken) so you hear how it really gets cut.
- **user_leave is on Magneto dying**, so you hear it every match. The broken meteor gets the soundboard sad horn.
- **Barrage charge** is the drums from the Stage waiting music, not the rare ringtone, so nobody mixes it up with the ult. The barrage start is 'someone joined the Activity', so the team-up opens with Activity sounds.
- **Meteor impact plays once for everyone.** You and your allies used to hear two copies at once.
- **Curtain block tink** is cut after its bright note ends instead of in the middle of it.
- **Melee hit** quacks now (it was an arrow key beep from a hidden easter egg nobody knows).

## The idea

Every ability is one Discord feature, so you can tell them apart with your eyes shut:

- **Iron Volley** is the chat: message ping on every shot, a soft 'bop' when the orbs burst.
- **Mag-Cannon** is streaming: 1 ring = a viewer joins, 2 rings = Go Live cut short, 3 rings = the whole Go Live run. A hit gets 'clip saved', a full-ring knock-back gets the airhorn.
- **Metallic Curtain** is deafen: wall up = deafen, wall down = undeafen, blocked shots go 'tink'.
- **Metal / Iron Bulwark** is mute: shield up = mute, shield down = unmute.
- **The iron rings** count out loud: 1 ping, 2 pings, 3 pings (full Mag-Cannon).
- **Reload** is two soft taps, no tune.
- **Meteor M** is a whole Discord call: calling on the cast, the ringtone while it forms, 'user joined' when you throw it (they picked up), disconnect on impact. Break it before the throw and it's the sad horn.
- **Melee** is the Lofi pack's ping, and a melee hit quacks.
- **Magnetic Descent** is push to talk: hold jump = hold the PTT key.
- **Metallic Chaos** (Scarlet Witch) starts an Activity. The barrage is the show: someone joins, the Stage waiting drums while it charges, a retro 'pew' per sword, viewers leave per mark, stream ended on the last one.
- **Magnetic Resonance** (Emma Frost) is your camera: on when the projection appears, off when it's gone.
- **Dying** is leaving the channel: user_leave on every death fall.

The C and X sounds only play when Scarlet Witch or Emma Frost is on your team. Vanilla voice lines stay ("Fear Magneto!", "For Mutantkind!", the ability and team-up lines), same as Iron Man.

## Picks

| # | Key | Ability / moment | Discord sound | What it is in Discord | Why | Preview |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | Left click | **Iron Volley**: each volley fired | `message1` | the normal message ping (DMs, @mentions) | Iron Volley is you spamming the chat, so every volley is the message ping. The most famous Discord sound goes on the button you press the most, and it's short enough to never smear on fast fire. | `01 Left click - Iron Volley.wav` |
| 02 | Left click | **Iron Volley burst**: orbs burst at the end of each volley | `bop_message1` | message ping from the Bop sound pack (Nitro) | The message landing: one soft gliding 'bop' when the orbs pop, so a volley goes 'ping... bop'. It's a single soft note, so it doesn't put a second tune on every shot. | `02 Left click - Iron Volley burst.wav` |
| 03 | Right click | **Mag-Cannon (1 ring)**: fired with 1 ring | `stream_user_joined` | a viewer joins the stream | Small shot, small stream sound: 'a viewer joined'. The 2 and 3 ring shots go live for real. | `03 Right click - Mag-Cannon (1 ring).wav` |
| 04 | Right click | **Mag-Cannon (2 rings)**: fired with 2 rings | `stream_started` | Go Live, a stream starts in your voice channel | The Go Live run (fast notes going up) cut after 4 notes: you're going live but the shot isn't full yet. | `04 Right click - Mag-Cannon (2 rings).wav` |
| 05 | Right click | **Mag-Cannon (3 rings, full)**: fired with 3 rings, full | `stream_started` | Go Live, a stream starts in your voice channel | The whole Go Live run, all 6 notes up to the top one: only the full-power shot finishes it. | `05 Right click - Mag-Cannon (3 rings, full).wav` |
| 06 | Right click | **Mag-Cannon hit**: the cannon ball hits something | `clip_save` | clip saved (you saved a clip or screenshot) | Hit marker: 'clip saved', as in clip that. Only Magneto's own metal hit layer gets it, the shared surface impact stays, so a hit still sounds like a hit. | `06 Right click - Mag-Cannon hit.wav` |
| 07 | Right click | **Mag-Cannon knock-back**: full-ring hit knocks the target back | `soundboard_airhorn` | airhorn from the soundboard | The big play gets the airhorn. You send someone flying across the map and both of you hear it. | `07 Right click - Mag-Cannon knock-back.wav` |
| 08 | Left Shift | **Metallic Curtain up**: curtain raised | `deafen` | you deafen yourself | Deafen: the wall goes up and nothing they send gets through to you. | `08 Left Shift - Metallic Curtain up.wav` |
| 09 | Left Shift | **Metallic Curtain blocks a shot**: each shot the curtain stops | `mention2` | the old @mention ping (Discord doesn't use it any more) | Every blocked shot is a tiny bright 'tink' from the old @mention ping, like a ricochet. Shortest and quietest pick because it can fire several times a second. | `09 Left Shift - Metallic Curtain blocks a shot.wav` |
| 10 | Left Shift | **Metallic Curtain down**: curtain drops / ends | `undeafen` | you undeafen | Undeafen: the wall is gone, you can hear (and get hit by) everything again. | `10 Left Shift - Metallic Curtain down.wav` |
| 11 | E and F | **Bulwark shield up**: shield appears on the target | `mute` | you mute your mic | The shield mutes the damage. E and F both use this moment. It goes on 'shield appears' and not on the cast, because the cast sound is shared with Rogue (she can copy Iron Bulwark). | `11 E and F - Bulwark shield up.wav` |
| 12 | E and F | **Bulwark shield down**: shield breaks / expires | `unmute` | you unmute your mic | Unmute: the damage can reach them again. | `12 E and F - Bulwark shield down.wav` |
| 13 | Passive | **Iron ring 1**: 1st iron ring forms | `mention3` | the test ping when you switch your headset or mic | One ping of the headset test ping, so the rings count out loud: ring 1 = 1 ping. | `13 Passive - Iron ring 1.wav` |
| 14 | Passive | **Iron ring 2**: 2nd iron ring forms | `mention3` | the test ping when you switch your headset or mic | Ring 2 = the same ping twice, 1 dB up. | `14 Passive - Iron ring 2.wav` |
| 15 | Passive | **Iron ring 3 (full)**: 3rd iron ring forms | `mention3` | the test ping when you switch your headset or mic | Ring 3 = the same ping three times: full Mag-Cannon is ready. | `15 Passive - Iron ring 3 (full).wav` |
| 16 | R | **Reload**: reload | `asmr_message1` | message ping from the ASMR sound pack (Nitro) | Two soft clicky taps from the ASMR pack's message ping. It has no tune, so a reload sounds like a real reload and never gets mixed up with a ping or the Go Live run. | `16 R - Reload.wav` |
| 17 | Q | **Meteor M cast**: ult cast | `call_calling` | outgoing call, waiting for them to pick up | Pressing Q is hitting the call button: the first 'boo-doo-doo' of the outgoing calling tone. Only the first half, so the ringtone can start right after it. | `17 Q - Meteor M cast.wav` |
| 18 | Q | **Meteor M forming**: meteor forming, until it's thrown | `call_ringing` | incoming call ringtone | THE Discord ringtone while the meteor forms, so everyone around hears 'you're getting called' = ult coming. Throwing the meteor stops it (the game already does that), so throwing = picking up. | `18 Q - Meteor M forming (full ring, cut short when you throw).wav` |
| 19 | Q | **Meteor absorbs a shot**: each shot the meteor swallows | `message2` | 'friend started playing a game' notification | Every bullet the meteor eats is a message landing while the phone rings: one low note (the ringtone's key), the first note of the 'friend started playing' ping. Quiet, it can fire a lot. | `19 Q - Meteor absorbs a shot.wav` |
| 20 | Q | **Meteor M thrown**: meteor thrown | `user_join` | someone joins your voice channel | They picked up. In a real call the join sound plays the moment the other side answers, and the ringing stops right before it. | `20 Q - Meteor M thrown.wav` |
| 21 | Q | **Meteor M impact**: meteor impact | `disconnect` | you leave or drop from voice | Then you hang up on everyone it hits. | `21 Q - Meteor M impact.wav` |
| 22 | Q | **Meteor M shattered**: meteor shattered before it's thrown | `soundboard_sad_horn` | sad horn (sad trombone) from the soundboard | They broke your ult before you could throw it: sad horn from the soundboard. | `22 Q - Meteor M shattered.wav` |
| 23 | V | **Melee**: sword swing | `lofi_message1` | message ping from the Lofi sound pack (Nitro) | A very high flick falling onto a bell, about as close to a blade 'shing' as Discord gets. It's the Lofi pack's message ping. | `23 V - Melee.wav` |
| 24 | V | **Melee hit**: melee connects (only you hear it) | `soundboard_quack` | quack from the soundboard | Bonk them and they quack. The soundboard quack is short, so it works as a hit marker. | `24 V - Melee hit.wav` |
| 25 | Space | **Magnetic Descent start**: hold jump, slow fall starts | `ptt_start` | push to talk key pressed | Holding jump to float is holding your push to talk key: the PTT click when you press it. | `25 Space - Magnetic Descent start.wav` |
| 26 | Space | **Magnetic Descent end**: let go of jump / land | `ptt_stop` | push to talk key released | Letting go = releasing push to talk: the lower click out. | `26 Space - Magnetic Descent end.wav` |
| 27 | C | **Metallic Chaos**: team-up activated | `activity_launch` | an Activity starts in your voice channel | You and Wanda start an Activity together: the rising 'Activity started' run. | `27 C - Metallic Chaos.wav` |
| 28 | C | **Chaos Greatsword swing**: greatsword swing (left click in the team-up) | `discodo` | Discodo easter egg (click the home button 16 times) | The Discodo easter egg chime. Turn Discodo on in Discord and this becomes your message ping, so it's the team-up version of Iron Volley's ping (both are left click), but sparkly so the two never mix. | `28 C - Chaos Greatsword swing.wav` |
| 29 | C | **Chaos Greatsword hit**: greatsword connects | `ddr-down` | down arrow key in the Ctrl+/ shortcuts popup (easter egg) | A little arcade beep from Discord's hidden Ctrl+/ arrow key game, as a hit marker. | `29 C - Chaos Greatsword hit.wav` |
| 30 | C | **Chaos barrage start**: barrage starts (right click in the team-up) | `activity_user_join` | someone joins the Activity you're in | The swords join in: 'someone joined the Activity', same family as the team-up start. | `30 C - Chaos barrage start.wav` |
| 31 | C | **Chaos barrage charging**: barrage charging (5.3 s, everyone hears it) | `stage_waiting` | Stage waiting music (a Stage that hasn't started yet) | The Stage waiting music: the drums at the start of the track, while you wait for the show to start. Cut right before the tune kicks in, so the barrage is the drop. | `31 C - Chaos barrage charging.wav` |
| 32 | C | **Chaos barrage sword**: barrage: each sword fired | `bit_message1` | message ping from the Retro sound pack (Nitro) | A short retro 'pew' for every sword. It's the Retro pack's message ping, cut before its low thump so it's short enough to repeat every tick. | `32 C - Chaos barrage sword.wav` |
| 33 | C | **Chaos barrage mark**: barrage: a mark is burned (only you hear it) | `stream_user_left` | a viewer leaves the stream | Each mark the barrage burns is a viewer leaving the stream. | `33 C - Chaos barrage mark.wav` |
| 34 | C | **Chaos barrage last mark**: barrage: the last mark is burned (only you hear it) | `stream_ended` | a stream ends | Last mark gone: stream over. | `34 C - Chaos barrage last mark.wav` |
| 35 | X | **Magnetic Resonance**: projection cast | `camera_on` | you turn your camera on | The projection is a live video of you running around somewhere else: camera on. | `35 X - Magnetic Resonance.wav` |
| 36 | X | **Magnetic Resonance end**: projection destroyed or recalled | `camera_off` | you turn your camera off | Camera off: the copy is gone. Allies don't hear this one, the game mutes it for them. | `36 X - Magnetic Resonance end.wav` |
| 37 | Death | **Magneto dies**: death fall (back, front, sides, chain-sawed) | `user_leave` | someone leaves your voice channel | Magneto left the channel. Everyone near you hears it when you go down, every match. | `37 Death - Magneto dies.wav` |

## Cuts and gain

| # | Sound | Cut (seconds of the Discord file) | Clip length | Gain and notes |
| --- | --- | --- | --- | --- |
| 01 | `message1` | full (0.43 s file) | 0.26 s | 0 dB. |
| 02 | `bop_message1` | full (0.37 s file) | 0.20 s | -6 dB, it follows every shot. The shared debris sound under it keeps playing. |
| 03 | `stream_user_joined` | full (1.66 s file) | 0.60 s | 0 dB. Its close-up sweetener is muted. |
| 04 | `stream_started` | 0.000-0.314 s | 0.28 s | +1 dB (2 / 3 rings go +1 / +2 dB). Its close-up sweetener is muted. |
| 05 | `stream_started` | full (1.79 s file) | 0.77 s | +2 dB (2 / 3 rings go +1 / +2 dB). The vanilla metal sweetener under the full shot stays, it's shared with another hero. |
| 06 | `clip_save` | full (1.04 s file) | 0.40 s | -2 dB. Only you hear it. |
| 07 | `soundboard_airhorn` | full (2.89 s file) | 1.73 s | -2 dB, it's a long solid blast so it sits a bit lower. |
| 08 | `deafen` | full (0.80 s file) | 0.53 s | 0 dB. The close-up metal sweetener under it is muted. |
| 09 | `mention2` | 0.000-0.150 s | 0.11 s | -8 dB, only the start of the file: a quiet trill and one bright note, about 0.12 s. |
| 10 | `undeafen` | full (0.88 s file) | 0.64 s | 0 dB. The sweetener under it is muted. |
| 11 | `mute` | full (0.54 s file) | 0.39 s | 0 dB. |
| 12 | `unmute` | full (0.54 s file) | 0.41 s | 0 dB. The sweetener under it is muted. |
| 13 | `mention3` | 0.137-0.260 s | 0.12 s | -2 dB (rings go -2 / -1 / +1 dB). Only you and enemies hear ring sounds, the game mutes them for allies. |
| 14 | `mention3` | 0.137-0.260 s | 0.24 s (2 pings) | -1 dB (rings go -2 / -1 / +1 dB), the ping 2 times, 0.12 s apart. Only you and enemies hear ring sounds, the game mutes them for allies. |
| 15 | `mention3` | 0.137-0.260 s | 0.36 s (3 pings) | +1 dB (rings go -2 / -1 / +1 dB), the ping 3 times, 0.12 s apart. Only you and enemies hear ring sounds, the game mutes them for allies. |
| 16 | `asmr_message1` | from 0.330 s to the end (1.09 s file) | 0.69 s | -2 dB, the last 2 taps. The long sweetener and the three ring-spin sounds are muted so the reload is just the taps. |
| 17 | `call_calling` | 0.000-0.950 s | 0.68 s | +2 dB, cut after the first phrase. The vanilla swell under it is muted. |
| 18 | `call_ringing` | full (5.37 s file) | 5.32 s, 5.82 s in game with the 0.5 s wait | 0 dB, full level on purpose, it's the biggest warning in the kit. It starts 0.5 s after the forming starts so the calling tone gets out first. The vanilla rumble layer is muted. |
| 19 | `message2` | 0.000-0.141 s | 0.10 s | -8 dB, first note only. The shared impact thunks under it stay. |
| 20 | `user_join` | full (1.16 s file) | 0.73 s | +1 dB. The game plays two throw sounds at once, so only one gets the clip and the other is muted, otherwise everyone would hear it doubled. |
| 21 | `disconnect` | full (1.29 s file) | 0.74 s | +2 dB. The big shared explosion under it keeps playing. Everyone hears the clip once. |
| 22 | `soundboard_sad_horn` | full (2.81 s file) | 2.51 s | 0 dB. The vanilla crash layer is muted. |
| 23 | `lofi_message1` | full (0.83 s file) | 0.71 s | 0 dB. The swish sweetener is muted. |
| 24 | `soundboard_quack` | full (1.08 s file) | 0.27 s | -3 dB. |
| 25 | `ptt_start` | full (0.09 s file) | 0.09 s | -3 dB. Only the magnetic swell gets it, the cloth and air whoosh stays. |
| 26 | `ptt_stop` | full (0.12 s file) | 0.11 s | -4 dB. Only the hum release gets it, the cloth sound stays. |
| 27 | `activity_launch` | full (1.55 s file) | 0.76 s | +1 dB. The sweetener is muted. |
| 28 | `discodo` | 0.000-0.548 s | 0.51 s | 0 dB, cut after 4 notes. The sweetener is muted. |
| 29 | `ddr-down` | 0.000-0.386 s | 0.37 s | -3 dB, cut before its echo. |
| 30 | `activity_user_join` | full (1.03 s file) | 0.61 s | 0 dB. The sweetener is muted. |
| 31 | `stage_waiting` | 1.560-6.950 s | 5.39 s | -6 dB, the drums and the fill, about the length of the vanilla charge. Its vanilla layer is muted. |
| 32 | `bit_message1` | 0.000-0.320 s | 0.29 s | -3 dB. The loud sweetener is muted. |
| 33 | `stream_user_left` | full (1.66 s file) | 0.51 s | -3 dB. Its layer is muted. |
| 34 | `stream_ended` | full (1.66 s file) | 0.51 s | -1 dB. Its layer is muted. |
| 35 | `camera_on` | full (0.98 s file) | 0.38 s | 0 dB. The ally version's layer is muted. |
| 36 | `camera_off` | full (2.05 s file) | 0.30 s | 0 dB. The sweetener is muted. |
| 37 | `user_leave` | full (1.03 s file) | 0.65 s | -2 dB. Replaces the body fall sound. |

Each clip is leveled against the game's own volume on the sound it replaces (`target_db` -22 plus the gain), so they all land about as loud as each other in game, like Iron Man. Every level lands between -28 and -5 dB, inside the -3 / -40 dB limits.

## The ult, start to finish

1. **Q**: the first 'boo-doo-doo' of `call_calling` (0.68 s), under "Fear Magneto!".
2. **Meteor forming**: `call_ringing`, the real incoming call ringtone, 0.5 s later. One full ring is 5.32 s, so it runs 5.82 s in all, a bit longer than the 5.57 s vanilla forming sound. Throwing stops it, so in a match you hear as much of the ring as you wait.
3. **Each shot the meteor eats**: one quiet low note (`message2`).
4. **Throw**: the ring stops (the game already does that), then `user_join`. Throwing = picking up.
5. **Impact**: `disconnect`, with the big shared explosion under it.
6. **Broken before the throw**: the soundboard sad horn. Nothing stops the ring here (the game has no stop for it, same as the vanilla rumble), so it keeps ringing under the sad horn until the clip ends. Same if you die mid-ult.

Ult sequence previews (made-up timing, gains applied):

- `Q - Meteor M sequence (quick throw at 2.5 s).wav`: throw at 2.5 s, so you hear 2.0 s of ring, impact 1.4 s later.
- `Q - Meteor M sequence (late throw at 5.6 s).wav`: throw at 5.57 s, so you hear 5.1 s of ring, impact 1.4 s later.
- `Q - Meteor M sequence (shattered at 3.5 s).wav`: meteor broken at 3.5 s, the ring keeps going under the sad horn.

`18 Q - Meteor M forming (full ring, cut short when you throw).wav` is the whole ring on its own. You'll only hear all of it if you hold the meteor the whole time.

## Repeats

Only two sounds are on more than one moment, both inside one ability and both on purpose:

- `stream_started` on Mag-Cannon 2 and 3 rings: 4 notes of the Go Live run, then all 6. The bigger the shot, the more of the run you hear.
- `mention3` on the three iron rings: one ping played 1, 2 or 3 times. That's the whole point, you count the rings by ear.

Close cousins, different files: `stream_user_joined` (1 ring) and `stream_user_left` (barrage mark) sound alike, they're Discord's viewer joined / viewer left pair; `activity_user_join` (barrage start) is a rising 3 note chime a bit like `user_join` (meteor throw), but higher; `ptt_stop` sounds a bit like the start of `user_leave`.

## Discord sounds used

- **Default Discord sounds**: `message1` (01), `stream_user_joined` (03), `stream_started` (04, 05), `clip_save` (06), `deafen` (08), `mention2` (09), `undeafen` (10), `mute` (11), `unmute` (12), `mention3` (13, 14, 15), `call_calling` (17), `call_ringing` (18), `message2` (19), `user_join` (20), `disconnect` (21), `ptt_start` (25), `ptt_stop` (26), `activity_launch` (27), `discodo` (28), `ddr-down` (29), `activity_user_join` (30), `stage_waiting` (31), `stream_user_left` (33), `stream_ended` (34), `camera_on` (35), `camera_off` (36), `user_leave` (37)
- **Soundboard**: `soundboard_airhorn` (07), `soundboard_sad_horn` (22), `soundboard_quack` (24)
- **Nitro sound packs**: `bop_message1` (Bop pack, 02), `asmr_message1` (ASMR pack, 16), `lofi_message1` (Lofi pack, 23), `bit_message1` (Retro pack, 32)

34 different Discord sounds over 37 moments (the numbers are the picks). All 14 of the really well known ones are in (message ping, ringtone, calling, join, leave, disconnect, mute, unmute, deafen, undeafen, Go Live, stream ended, quack, airhorn). Well known ones left out: `user_moved`, `call_ringing_beat`, `soundboard_cricket`, `soundboard_golf_clap`, `soundboard_ba_dum_tss`, see below.

Heads up: a few picks are Discord in name only, bits nobody will recognise on their own: the curtain tink (`mention2`), the meteor eating a shot (`message2`) and the greatsword hit (`ddr-down`). They fire a lot, so they're short on purpose, and the first two are quiet too.

## Discord sounds not used, and why

- `user_moved`: A mod moving you to another voice channel. It was on the knock-back in draft 2, the airhorn has that spot now. Swap it back onto pick 07 if you like the 'moved you to another channel' joke more than the airhorn.
- `call_ringing_beat`: The rare ringtone, about 1 in 2000 calls (1 in 1000 rolls a rare ringtone, then it's this one or Snow Halation). It was on the barrage charge, but two ringtones in one kit made the charge sound like the ult coming. It's the other choice for the optional timer bed, where only you hear it.
- `soundboard_cricket`: Soundboard crickets, 2 s of chirps. Nothing in the kit is an awkward silence.
- `soundboard_golf_clap`: Soundboard golf clap. Quiet scattered claps, they'd get lost in a fight.
- `soundboard_ba_dum_tss`: Soundboard rimshot, 1.6 s. Too long for a hit marker. Swap it onto the melee hit instead of the quack if you want the joke. (Soundboard id 7 is the same file.)
- `reconnect`: 'Invited to Speak' on Stages (it used to be the reconnect sound). A 4 note tune that starts with the same jump up as user joined (the meteor throw).
- `message3`: New message in the channel you're reading. Too close to the message ping (both land on the same high note), it would blur Iron Volley.
- `mention1`: Old @mention ping, one long ping. Too close to the ring ping.
- `activity_end / activity_user_left`: The rest of the Activity set. Nothing in the team-up ends or leaves on its own, and activity_end is one more falling phrase next to deafen and disconnect.
- `clip_error`: Clip failed to save. A fail sound, but the sad horn got the broken meteor.
- `ddr-left / ddr-up / ddr-right`: The other arrow keys of the Ctrl+/ easter egg. Only the greatsword hit still uses one.
- `ducky_message1`: Ducky pack message ping. Four other packs' pings are already in the plan, one more would be a repeat by ear.
- `call_ringing_snow_halation`: The other rare ringtone, a 35 s song. Too long for anything here.
- `call_ringing_snowsgiving`: Old winter ringtone, Discord doesn't play it any more.
- `halloween_* (12 files, 2 are misspelled leftovers)`: Halloween pack versions of the call, mute, deafen, join, leave, disconnect and message sounds. Busier remixes of sounds already in the plan, so they'd sound like repeats. Fun idea for a spooky version: halloween_call_calling on the cast and halloween_call_ringing on the forming.
- `winter_* (9 files)`: Winter pack versions, same reason. The current Discord can't even turn that pack on.
- `poggermode_enabled / poggermode_applause / poggermode_achievement_unlock / poggermode_message_send`: Party Mode (hidden). Hardly anyone has heard them.
- `vibing_wumpus`: Lofi track from the take a break screen. Ready as the optional team-up timer bed below.
- `overlayunlock / human_man / robot_man / hang_status_select / success`: Barely or never played by Discord (plant watered, bug report sent, two 2016 voice clips), nobody knows them.

## Who hears what

- Every pick covers your version, the ally version and the enemy version of its sound, so everyone hears the Discord sound, except where the game itself mutes a version: allies never hear the ring sounds, the meteor eating a shot, the descent start/end or the projection end.
- Some moments only exist for some people: the knock-back and the greatsword hit (you and the person hit), the Mag-Cannon hit, the melee hit and the barrage marks (only you).
- Enemies hear the Iron Volley ping 4 semitones lower, allies hear the meteor impact 1.5 semitones lower, and other people hear some curtain tinks 2 semitones lower. The game pitches those itself and the files are shared, so it can't be right for everyone.
- The sound pak changes the sound bank almost every Magneto costume uses, so most Magneto skins will sound like Discord Magneto, not only the default one. Same as the Iron Man note.

## What stays vanilla, and why

- **Voice lines**: all of them.
- **E / F cast whoosh**: Rogue has the same files (she copies Iron Bulwark), so it stays. The Discord mute plays a moment later when the shield appears.
- **Layers shared with other heroes**: the Mag-Cannon full-ring sweetener, the tick under the ring sounds, the long explosion tails under the meteor impact, the debris under the Iron Volley burst and the surface impacts under the Mag-Cannon hit and the meteor eating a shot. They keep playing under or after the Discord sounds.
- **Loops and beds**: curtain hum, shield hum, descent hum, meteor fly-by and the team-up timer bed. They tell you the wall or shield is still up and how long the team-up lasts, and no short Discord clip loops cleanly. The timer bed has an optional Discord version below.
- **Shield taking a hit and debris hitting the meteor**: shared impact sounds and physics spam.
- **Movement and foley**: footsteps, cloth, flying (also during the ult), jump, land, taking damage. The cloth/air whoosh of Magnetic Descent stays under the push to talk click too. The one generic body fall that isn't tied to a death animation stays too, since nothing says when it plays.
- **Enemy-only fly-bys** (Iron Volley, Mag-Cannon, meteor) and all controller vibration.
- **Old unused team-ups and abilities**, except the old greatsword swing, which some costumes still use (it's in the greatsword pick).

## Optional extra (in `sounds.json` under `optional_abilities`)

Ready to move into `abilities` if you want it. It's off for the reason in the note.

| Key | Moment | Plays on | Sound | Cut | Gain | Note |
| --- | --- | --- | --- | --- | --- | --- |
| C | Metallic Chaos timer | under the whole team-up (8.9 s, only you hear it) | `vibing_wumpus`: 'Vibe with Wumpus' lofi track (take a break screen) | 0.00-8.78 s | -10 dB | Quiet lofi music under the team-up, cut on the beat before 8.8 s; the music stopping is your 'time's up'. Off because the vanilla timer hum is useful info. The rare ringtone (call_ringing_beat) works here too: only you hear this one, so nobody mixes it up with the ult. |

## Check in game

- The gap between pressing Q and the ringtone. The cast and the forming sound are started by different parts of the ult, so the ring might come in a bit later than in the previews.
- How long the ring keeps going after the meteor gets broken or you die mid-ult.
- The barrage charge clip is 5.39 s and the vanilla charge is 5.31 s, so the drum fill might touch the first sword.
- The quiet ones (-8 dB curtain tink and meteor absorb) in a real fight: too quiet or just right.
- The airhorn on the knock-back at -2 dB: fun or too much.

## Building

`python scripts\build_magneto.py` builds the skin and the sounds. For the sounds it runs `make_sounds.py` and `build_audio.py` with this `sounds.json`: the clips come from the `src` folder (`magneto/discord`), clips that aren't 44.1 kHz get resampled, `repeat` / `every` / `lead_in` make the rings and the ringtone, and `prev_note` goes on the end of a preview's file name. It only replaces the numbered previews, so the three ult sequence files stay. Some spiky clips (melee, melee hit, ring 2, meteor thrown) come out a few dB quieter in game than their gain says, because the leveling won't boost anything more than 12 dB. Same rule as Iron Man.

Playing against another Magneto in the 1037300 or 1037304 costume: those costumes' banks share some of these sound ids, and the game keeps whichever copy loads first, so some sounds can come out vanilla for you (or Discord for them). Same thing as with Iron Man's costumes.

## Tech notes

Bank: `bnk_sfx_1037001.bnk`, checked against the copy in the game today. Only costumes 1037300 and 1037304 have their own sound table, and they still fall back to this bank for the team-ups, Space and some E/V sounds. The `q_lvup_*` ult events of 1037304 use the same files as the normal ult. The `never_touch` list in `sounds.json` is every file of these moments that another bank also holds (other heroes, the shared impact and battle UI banks). Changing one of those could change them too.

- **01 Iron Volley**: Enemies hear it 4 semitones lower: the enemy version plays the 3rd-person file at -400 cents and allies share that file at 0, so the pitch can only be right for one of them.
- **02 Iron Volley burst**: Only the Magneto-only crack and body layers change; the debris tail is in 47+ other banks.
- **05 Mag-Cannon (3 rings, full)**: The 1.2 s full-shot sweetener 575470063 is also in bnk_sfx_1029001, so it isn't touched.
- **06 Mag-Cannon hit**: The 3 Magneto-only 1.17 s layer files (584910738, 148345098, 229168851) are replaced; the main sound of this event is the shared impact library and is never touched.
- **07 Mag-Cannon knock-back**: The game plays this event at +2/+3 dB; the clip is leveled down to match.
- **09 Metallic Curtain blocks a shot**: Some of the tink files are shared between your version (pitched +2 semitones by the game) and everyone else's (no pitch), so other people hear some of the tinks 2 semitones lower.
- **11 Bulwark shield up**: Every file of e_release_play is also in Rogue's bank. The game plays this event at +2 dB for you, -20 for allies, -13 for enemies; the clip is leveled to your version.
- **13-15 Iron ring 1 / Iron ring 2 / Iron ring 3 (full)**: Its vanilla ring layer is muted, the battle-UI tick under it stays (it's in bnk_ui_battle). The file's 3rd ping is about 15 dB quieter than the first two, so every ring uses the 2nd ping.
- **16 Reload**: Cut from 0.33 s. Mutes r_absorb1-3 too.
- **18 Meteor M forming**: q_release has stop actions (0x103) on every forming target: 111860807, 507761464, 524972516 (you), 551659154 (allies), 125012237 (enemies). q_child_damage_play only has play actions.
- **19 Meteor absorbs a shot**: Only the 15 Magneto-only zap files get the clip. The one Magneto-only extra sits in the same random pick as the 3 shared thunks, so it isn't muted (1 absorb in 4 would lose its thunk).
- **20 Meteor M thrown**: Close-up set 744393175/143313839/824079349 gets the clip, 3rd-person set 831444564/1000982248/234569062 and the 0.7 s sweetener 841967870 are muted (the two sets are crossed between you and everyone else).
- **21 Meteor M impact**: Only the set every version plays (465763209, 659074377, 75594779) gets the clip. Your 1.2 s main crack 414507073 and the ally-only set 101597121/508910138/191546796 are muted with the other Magneto-only layers, so nobody hears two copies. Allies hear it 1.5 semitones lower (the game's -150 cents on their version, shared file). The 4-6 s explosion tails are in 20-32 other banks and stay.
- **25 Magnetic Descent start**: Replaces the swell 766089542/230208889, mutes the 0.6 s extra layer 1069493481.
- **26 Magnetic Descent end**: Replaces the 2 s hum release 336935997/550624621, mutes the 0.4 s extra layer 721068151.
- **28 Chaos Greatsword swing**: The old swing event left_sp_release_play is in too because costumes 1037100/101/500/501 still use it.
- **31 Chaos barrage charging**: Cut 1.56-6.95 s of the 92.5 s track: first kick at 1.6 s, the fill ends at 6.85 s, the melody starts at 7.15 s. The clip is 5.39 s against the 5.31 s vanilla charge.
- **37 Magneto dies**: fall_b/f/lr/chain_play fire at t=0.01-0.03 of Dead_B/F/L/R and ChainSawed. All Magneto-only, no other hero or costume bank. The generic fall_play stays vanilla (nothing says when it plays).

## Checks

My check script is `plan/plan2.py` (`python magneto/plan/plan2.py --check` to only check, without `--check` it also rewrites `sounds.json`, this file and the previews, so swap a sound in the picks there and run it to hear the new preview). It reads the bank straight from the game and checks that every replaced or muted file is really played by its moment, that none is shared with another bank, that no file is in two picks or both replaced and muted, that no sound is used twice except the two repeats above, that every clip exists as an mp3 in `discord/`, and that every level stays inside the limits using the same leveling as `make_sounds.py`.
