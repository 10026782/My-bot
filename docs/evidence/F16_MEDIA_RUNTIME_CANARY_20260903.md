# F16 Media — deployed-SHA runtime canary evidence

**Evidence date:** 03/09/2026 (Asia/Jerusalem)
**Environment:** Render production, service `srv-d80ehsf7f7vs73cq5rn0`
**Deployed SHA:** `0f80122525c5bbc9e3b115a4f7c4e131ac47070b`
**Evidence level:** `RUNTIME_VERIFIED` for the canonical basic Telegram Media canary

## Preconditions verified

A read-only Render check before the canary established that the latest deploy was
`live` at the exact SHA above, `FEATURE_MEDIA_UPLOAD=true`,
`FEATURE_VOICE_NOTES=true`, the canonical `GOOGLE_DRIVE_FOLDER_ID` key was
present, and `GET /health` returned HTTP 200 with `{"status":"ok"}`.

## Canary observations

The owner supplied the real Telegram inputs. Render logs were then inspected in
the corresponding UTC windows.

| Israel time | Input | Runtime result |
|---|---|---|
| 22:31 | Photo | Drive upload returned 200, Airtable `Media Files` write returned 200, and the bot returned a Drive link. |
| 22:36 | MP4 sent as a Telegram document | Drive upload returned 200, Airtable `Media Files` write returned 200, and the bot returned a Drive link. This is extra positive coverage beyond the required photo canary. |
| 23:02 | Telegram voice note | OpenAI STT returned 200 and the bot returned the transcript. |
| 23:11 | Voice note requesting a save action | STT succeeded, the approval interaction was shown, owner confirmation executed `media_save_to_memory`, and a Business Memory record was created. |
| 23:12 and follow-up forward | Previously used photo sent again / forwarded | A new provider `logical_media_key` was observed and a new Drive/Airtable asset was created. This is consistent with the accepted F16-M5 boundary: Telegram identity is provider-ID based and content-hash deduplication is not an F16 requirement. |

## Scope reconciliation

The canonical runtime requirement was one real Telegram voice note plus one real
photo through the basic flow. Both passed on the deployed SHA. F16 Media intake
is event-driven: sending supported media invokes the handler directly; there is
no `/media` command or upload button required by the F16 contract.

Telegram `audio` (music/audio-file messages), `video_note` (round video), and
saving the original voice-note bytes to Drive are not part of the accepted F16
canary. Their absence does not reopen F16. They may be considered only as
separately authorized capabilities.

## Verdict

`F16 BASIC TELEGRAM MEDIA CANARY — RUNTIME_VERIFIED`

No deployment, configuration, schema, or production-data mutation was performed
by this documentation update. The user-triggered canary itself created the test
records described above.
