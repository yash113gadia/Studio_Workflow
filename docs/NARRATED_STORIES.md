# Narrated vertical stories

1. Open **New video**, select **Narrated story**, and paste a reviewed short story or adaptation. Blank lines separate story moments. Long passages split into shorter shots. The planner preserves your words; it does not shorten, translate, or adapt a novel automatically.
2. Choose **English** or **Hindi / Hinglish** to match the text. Create a separate storyboard for each language version. The page includes English, Hindi and Hinglish examples.
3. Plan the shots, then review each **Action / visual description** separately from its **Narration transcript**. Edit visual prompts into English when needed by the image model. Narrated stories default to 2.5D camera motion over stills.
4. Generate speech using a matching installed Windows System.Speech voice, or use **Upload WAV** in each shot. Uploads must be complete PCM WAV files, mono/stereo, up to 20 MB and 120 seconds. You can record narration yourself or import audio produced by another tool.
5. Preview and select each recording before rendering the clip. Studio measures the WAV and extends the shot to include the recording plus padding. The chosen Windows narrator name is saved with the storyboard.
6. Select a keyframe from the library or generate one, render the clip, then assemble the master. Export creates the video and an SRT subtitle file. Caption burn-in requires an FFmpeg build with the subtitles/libass filter and fonts covering the script.

Changing the transcript or language clears the selected narration and clip so stale audio cannot be exported. Changing a generated voice preserves uploaded recordings. **Generate all** with missing-only generation preserves already selected recordings. Assembly stops if speech is missing, a clip is too short, or FFmpeg fails.

This workflow adds no paid API calls. Automatic novel adaptation and direct premium TTS integration are not connected. Windows speech needs an installed voice for the requested language; it does not fall back to a different language silently.

## Verification

The narration tests cover source preservation in English/Hindi/Hinglish, real WAV timing, malformed uploads, language/voice changes, missing-only batch behavior, and failure handling.

A local HTTP check exported English and Hindi 1080×1920 H.264/AAC videos using uploaded WAV fixtures, existing keyframes, the real job worker, 2.5D rendering and FFmpeg assembly. Both videos passed full decode, range streaming and Unicode SRT checks. The fixtures used installed macOS voices solely to exercise upload and export. Windows SAPI, Chatterbox, browser interaction and caption burn-in were not exercised in that check.
