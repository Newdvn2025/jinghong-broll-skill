---
name: jinghong-broll
description: Generate, monitor, download, and organize AutoDL Art media, including MiniMax H3 B-roll and IndexTTS2 speech synthesis with voice and emotion references. Use for new generated video or speech audio, not editing existing media.
---

# Jinghong B-roll Skill

Turn an editorial need into useful, clearly named B-roll while preserving the user's story, visual direction, and authorization boundaries.

## Guide a first-time user

When the user asks how to start or gives a vague request, explain the flow in Chinese: configure the AutoDL Art token locally, provide narration or a visual need, review a shot plan, request generation, then retrieve the named media files. Check Python 3.10+ availability and token configuration without displaying secret values. If configuration is missing, give local `.env` instructions and use `--env-file`; do not ask the user to paste the token into chat. Do not invent the current platform UI location for obtaining a token.

Ask only for missing information that materially affects the plan: narration or subject, horizontal/vertical format, desired style, reference file paths, and approximate clip count/duration. Offer a small first batch, typically one test clip or three planned 4–5 second shots. If the user only wants onboarding or planning, do not submit paid tasks.

Before a planned batch is generated, present a readable shot list mapping each clip to the narration, visual action, duration, aspect ratio, workflow, and required references. If the user already explicitly authorized generation with sufficient details, proceed without asking for redundant confirmation. Explain that platform generation is paid and that the script does not enforce a monetary budget; do not invent prices. Use only confirmed resolution enums, and resolve an unsupported vertical text-to-video request before submission rather than silently producing horizontal footage.

After generation, report success/failure counts and absolute output paths, and explain that the user can import the clips into their editor. For an interrupted batch, reuse the original manifest and output directory to query recorded tasks. For changed prompts, use a new batch directory. Do not promise automatic recovery of missing downloaded files or automatic editing into a finished video.

## Choose the mode

- If the user asks only for ideas, coverage, prompts, or a shot list, plan the B-roll and do not call the API.
- If the user explicitly asks to generate, render, submit, run, or download footage, create the plan and run `scripts/autodl_broll.py`.
- If source narration, transcript, timeline, or edit notes exist, inspect them first. Cover genuine visual gaps rather than generating one clip per sentence by default.
- Use `minimax_h3_lightx2v_no_pic` for text-only generation.
- Use `minimax_h3_z0902` when the user supplies reference images or when identity/style continuity materially benefits from a reference image. This mode requires `ref_image_0` and accepts up to `ref_image_5`.
- Use `minimax_h3_z0903` for high-quality audio-visual fusion from references. It requires `ref_image_0` and `ref_audio_0`, and accepts up to 6 images and 3 audio clips.
- Use `minimax_h3_b99_003_12s` for a 1–12 second video with up to 9 reference images. It requires `ref_image_0`.
- Use `minimax_h3_b99_002` when the user supplies a first frame and a last frame or wants a controlled A-to-B transition. This mode requires both `first_frame` and `last_frame`.
- Use `indextts2-v1` to synthesize speech from text while cloning a reference timbre and optionally controlling emotion.

## Generate IndexTTS2 speech

Use the same batch manifest structure, with one speech item per `clips` entry:

```json
{
  "workflow_id": "indextts2-v1",
  "clips": [
    {
      "id": "01",
      "title": "平静旁白",
      "prompt_text": "这是要合成的口播文本。",
      "prompt_simple": "assets/voice-reference.wav",
      "emo_control_method": "使用情感向量控制",
      "emo_calm": 1.0,
      "emo_happy": 0.15,
      "emo_random": false
    }
  ]
}
```

`prompt_simple` is the required timbre reference audio. It accepts HTTP(S), base64/data URLs, or local mp3/wav files. `emo_ref_audio` is optional and uses the same formats. The three confirmed `emo_control_method` values are `与音色参考音频相同`, `使用情感参考音频`, and `使用情感向量控制`. Read [references/autodl_api.md](references/autodl_api.md) for emotion fields and limits. Only use reference audio the user is authorized to provide.

## Plan useful coverage

Create a JSON manifest with one object per clip. Each clip needs a stable `id`, concise Chinese `title`, generation `prompt`, `duration`, and `resolution`.

- Default to 4–5 seconds; use longer clips only when the action needs time to read. The workflow accepts 1–15 seconds.
- Default to `768p横` for text-to-video, `768p横(1376*768)` for the multi-image workflows, and `736p横` for `minimax_h3_b99_002`. Use another resolution only when the user provides an enum value supported by their workflow.
- Make each clip earn its place: establish context, demonstrate an action, reveal a detail, bridge an edit, or visualize an abstract idea.
- Match neighboring footage in subject, wardrobe, location, time of day, color, light direction, lens feel, and realism.
- Describe one readable shot rather than a montage. State framing, subject action, environment, light, camera behavior, continuity anchors, and a clean ending.
- Avoid generated captions, logos, watermarks, UI text, and unnecessary dialogue unless requested.
- For multiple text-to-video clips featuring the same person, repeat the same concrete identity anchors in every prompt and disclose that text-only generation cannot guarantee identity lock.

Use this text-to-video manifest shape:

```json
{
  "workflow_id": "minimax_h3_lightx2v_no_pic",
  "clips": [
    {
      "id": "01",
      "title": "窗边工作的手部细节",
      "duration": 4,
      "resolution": "768p横",
      "prompt": "一条完整、可直接生成的视频提示词"
    }
  ]
}
```

For reference-image-to-video, switch the workflow and add one or more reference images:

```json
{
  "workflow_id": "minimax_h3_z0902",
  "clips": [
    {
      "id": "01",
      "title": "参考人物走入庭院",
      "duration": 8,
      "resolution": "768p横(1376*768)",
      "prompt": "保持参考人物身份、服装和场景，人物完成一个清楚动作……",
      "ref_image_0": "assets/character-reference.png",
      "seed": 123456
    }
  ]
}
```

Reference images may be HTTP(S) URLs, `data:image/...;base64` values, raw base64 strings, or local jpeg/png/webp paths. Relative paths resolve from the manifest file. Reuse the same character reference as `ref_image_0` across clips when identity continuity matters; use additional reference slots only when they contribute distinct subject, wardrobe, location, or style information. `minimax_h3_z0902` accepts up to six images and defaults to `768p横(1376*768)`; its eight exact resolution enum strings differ from the text-to-video workflow and are listed in [references/autodl_api.md](references/autodl_api.md).

For a longer multi-image set, use the 12-second workflow:

```json
{
  "workflow_id": "minimax_h3_b99_003_12s",
  "clips": [
    {
      "id": "01",
      "title": "九图一致性镜头",
      "duration": 12,
      "resolution": "736p横",
      "prompt": "保持所有参考图中的人物、服装和场景一致，完成一个连续清楚的动作……",
      "ref_image_0": "assets/character.png",
      "ref_image_8": "assets/style.webp",
      "seed": 123456
    }
  ]
}
```

This workflow accepts `ref_image_0` through `ref_image_8`, defaults to `736p横`, and supports `736p竖`, `736p横`, and `736p(1:1)`.

For six-image, three-audio generation, use this shape:

```json
{
  "workflow_id": "minimax_h3_z0903",
  "clips": [
    {
      "id": "01",
      "title": "音画融合镜头",
      "duration": 15,
      "resolution": "768p横(1376*768)",
      "prompt": "保持参考人物、场景和声音风格，完成一个清楚连续的动作……",
      "ref_image_0": "assets/character.png",
      "ref_image_1": "assets/location.webp",
      "ref_audio_0": "assets/voice.wav",
      "ref_audio_1": "assets/ambience.flac",
      "seed": 123456
    }
  ]
}
```

`ref_audio_0` is required; `ref_audio_1` and `ref_audio_2` are optional. Audio inputs may be HTTP(S) URLs, `data:audio/...;base64` values, raw base64 strings, or local mp3/wav/flac paths. Use only audio the user is authorized to provide. Relative paths resolve from the manifest file. Read [references/autodl_api.md](references/autodl_api.md) for the exact resolution enums.

For first-and-last-frame-to-video, use this shape:

```json
{
  "workflow_id": "minimax_h3_b99_002",
  "clips": [
    {
      "id": "01",
      "title": "遮挡转场",
      "duration": 6,
      "resolution": "736p横",
      "prompt": "前景物体横向掠过并完全遮住镜头，在全遮挡期间完成场景变化，随后物体移开，平滑显露目标场景；保持运动方向和镜头速度连续。",
      "first_frame": "assets/01-A.png",
      "last_frame": "assets/01-B.png",
      "seed": 123456
    }
  ]
}
```

`first_frame` and `last_frame` accept the same URL, data URL, raw base64, and local image inputs as reference images. They are required visual endpoints rather than optional style references. This workflow supports `736p竖`, `736p横`, and `736p(1:1)`.

For additional prompt decisions, read [references/broll_prompting.md](references/broll_prompting.md).

## Generate and retrieve

Run from the directory where the user wants the output:

```bash
python3 <skill-directory>/scripts/autodl_broll.py manifest.json --output-dir broll输出
```

The script reads the token from `AUTODL_ART_TOKEN`. If the project keeps it in a local env file, pass `--env-file /absolute/path/to/config.evn`. Local reference and endpoint images are converted to base64 data URLs before submission. Never put the token in a manifest, prompt, source file, task log, or assistant response.

The script:

- writes one request Body per clip;
- persists every `task_id` immediately;
- resumes without resubmitting recorded tasks;
- polls unfinished tasks and downloads short-lived result URLs promptly;
- names video outputs `<id>-<title>.mp4`, saves IndexTTS2 results as wav/mp3 when identifiable, and records the exact mapping in `任务状态.json`.

After it finishes, verify that every requested item has status `SUCCESS` and exactly one non-empty media file. For video, check codec, dimensions, and approximate duration when `ffprobe` is available; for audio, check codec, channels, sample rate, and duration. Report failures separately; do not automatically resubmit failed paid jobs without fresh user authorization.

Read [references/autodl_api.md](references/autodl_api.md) when using reference-image-to-video, diagnosing API behavior, or adapting another AutoDL workflow.

Copy [references/first_last_manifest_example.json](references/first_last_manifest_example.json) when starting a first-and-last-frame batch.
