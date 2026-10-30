# Latvian voice

## Can the robot itself speak Latvian?

| Option | Status | Details |
|---|---|---|
| 1. Official Latvian voice pack on the robot | **UNVERIFIED / not controllable from this app** | `deebot-client` has **no command to read or change the robot's voice language** for any model. It only has volume and the YIKO voice-assistant on/off. No public source lists Latvian among the X9 PRO OMNI's voice languages. Check yourself in **Ecovacs Home → robot → Settings → Voice / Voice language**. If Latvian is listed, select it there. The app cannot do it for you. |
| 2. Latvian announcements through Home Assistant | **IMPLEMENTED** | Spoken on a speaker via HA TTS, or sent as a phone notification. Details below. |
| 3. Custom audio files on the robot | **NOT SUPPORTED** | There is no documented mechanism. Community approaches need root or firmware access, which this project rejects because of bricking and security risk. The app never claims the robot can speak arbitrary Latvian audio. Research, pre-generated Latvian clips, and a gated procedure are in [robot-voice-lv/](../robot-voice-lv/README.md). |

The robot's own voice is therefore whatever language the Ecovacs app offers.
Latvian speech comes from **your speakers or phones**, through Home Assistant.

## Free, local Latvian TTS: Piper

[Piper](https://github.com/rhasspy/piper) runs on the Raspberry Pi with no cloud
and no cost. It includes the Latvian voice **`lv_LV-aivars-medium`** (listed in
Piper's `VOICES.md`).

1. In HA, go to **Settings → Add-ons → Add-on store → Piper** and install it.
   On HA Container, run the `rhasspy/wyoming-piper` container instead.
2. In the Piper add-on configuration, set **voice: `lv_LV-aivars-medium`** and start it.
3. Go to **Settings → Devices & services**. The **Wyoming Protocol**
   integration is discovered; add it. A `tts.piper` entity appears.
4. Test it in HA under **Developer tools → Actions**:
   ```yaml
   action: tts.speak
   target: { entity_id: tts.piper }
   data:
     media_player_entity_id: media_player.virtuve
     message: "Sveiki! Šī ir pārbaude."
   ```
5. In the app, open **Iestatījumi → Paziņojumi latviski**:
   - **Runas balss (TTS):** `tts.piper`
   - **Skaļrunis:** your `media_player.…`, for example a Google/Nest speaker, Sonos, or VLC on the Pi
   - **Skaļums:** optional; the app sets it before speaking if the speaker supports it
   - **Valodas kods:** leave empty for Piper. The voice already defines the language.
   - Press **Pārbaudīt**. You should hear "Šis ir pārbaudes paziņojums no robota lietotnes."
   - Press **Saglabāt** and switch on **Ieslēgt paziņojumus latviski**.

Other TTS engines: Google Translate TTS (`tts.google_translate_*`, language
`lv`) also speaks Latvian and costs nothing, but sends the text to Google. It
also works with the app. Use language code `lv`.

## Phone notifications instead of a speaker

With the HA Companion app on the phone, a `notify.mobile_app_<phone>` service
exists. Choose it under **Ziņa tālrunī**. You can use it together with the speaker or on its own.

## Which messages, and when

See [HOME_ASSISTANT.md §6](HOME_ASSISTANT.md#6-which-events-are-announced-and-how-reliable-are-they).
The app announces only events it can detect reliably, never repeats a message
within 5 minutes, and stays silent when it reconnects. It needs no microphone,
no paid speech API, and no continuous cloud listening.
