# AutoDL Art ComfyUI API notes

## Supported workflows

### Text-to-video

## Known workflow

- Workflow ID: `minimax_h3_lightx2v_no_pic`
- Submit: `POST https://autodl.art/api/v1/comfyui/comfyui_workflow/{workflow_id}`
- Result: `/api/v1/comfyui/comfyui_workflow/result/{task_id}`
- Authorization header: raw ComfyUI-group token in `Authorization`; do not add `Bearer`.

## Request Body

```json
{
  "duration": 5,
  "prompt": "...",
  "resolution": "768p横"
}
```

`prompt` is required. `duration` is optional and accepts 1–15. `resolution` is a workflow enum; `768p横` produces a 1344×768 horizontal video in the currently observed workflow.

Do not send `width` or `height`; this workflow rejects undefined parameters.

### Reference-image-to-video

- Workflow ID: `minimax_h3_z0902`
- Submit: `POST https://autodl.art/api/v1/comfyui/comfyui_workflow/minimax_h3_z0902`
- Authorization header and result polling are the same as text-to-video.

Request fields:

```json
{
  "duration": 8,
  "prompt": "保持参考人物身份与服装……",
  "ref_image_0": "https://example.com/character.png",
  "ref_image_1": "data:image/png;base64,...",
  "seed": 123456
}
```

- `prompt`: required, 1–10000 characters.
- `duration`: optional integer, 1–15.
- `ref_image_0`: required; HTTP(S) URL or base64 image, jpeg/png/webp.
- `ref_image_1`–`ref_image_5`: optional, same accepted image formats.
- `resolution`: optional workflow-specific enum. Defaults to `768p横(1376*768)` in the helper. Confirmed values are:
  - `480p竖(480*864)`
  - `480p横(864*480)`
  - `768p竖(768*1376)`
  - `768p横(1376*768)`
  - `1088p竖(1088*1920)`
  - `1088p横(1920*1088)`
  - `1440p竖(1440*2560)`
  - `1440p横(2560*1440)`

The shorter text-to-video value `768p横` is rejected by this image-to-video workflow.
- `seed`: optional integer, 1–999999999999999.

The helper additionally accepts local jpeg/png/webp paths and converts them to base64 data URLs. Relative paths resolve from the manifest directory. Do not send `width` or `height`.

### Nine-image-to-video, up to 12 seconds

- Workflow ID: `minimax_h3_b99_003_12s`
- Submit: `POST https://www.autodl.art/api/v1/comfyui/comfyui_workflow/minimax_h3_b99_003_12s`
- Authorization header and result polling are the same as the other workflows.

`prompt` is required (1–10000 characters). `duration` is optional and accepts integers from 1–12. `ref_image_0` is required; `ref_image_1`–`ref_image_8`, `resolution`, and `seed` are optional. Images accept jpeg/png/webp. Seed accepts 1–999999999999999.

Confirmed resolution enums are `736p竖`, `736p横`, and `736p(1:1)`; the helper defaults to `736p横`. Local image paths are converted to base64 data URLs and relative paths resolve from the manifest directory.

### First-and-last-frame-to-video

- Workflow ID: `minimax_h3_b99_002`
- Submit: `POST https://www.autodl.art/api/v1/comfyui/comfyui_workflow/minimax_h3_b99_002`
- Authorization header and result polling are the same as the other workflows.

Request fields:

```json
{
  "duration": 6,
  "first_frame": "https://example.com/first.png",
  "last_frame": "https://example.com/last.png",
  "prompt": "前景物体完全遮住镜头，在遮挡期间完成场景变化，再移开显露目标场景。",
  "resolution": "736p横",
  "seed": 123456
}
```

- `first_frame`: required; HTTP(S) URL or base64 image, jpeg/png/webp.
- `last_frame`: required; HTTP(S) URL or base64 image, jpeg/png/webp.
- `prompt`: required, 1–10000 characters.
- `duration`: optional integer, 1–15.
- `resolution`: optional enum. Confirmed values are:
  - `736p竖`
  - `736p横`
  - `736p(1:1)`
- `seed`: optional integer, 1–999999999999999.

The helper defaults this workflow to `736p横`. It also accepts local jpeg/png/webp paths for both endpoint frames, converts them to base64 data URLs, and resolves relative paths from the manifest directory. Do not send `width` or `height`.

### Six-image, three-audio-to-video

- Workflow ID: `minimax_h3_z0903`
- Submit: `POST https://www.autodl.art/api/v1/comfyui/comfyui_workflow/minimax_h3_z0903`
- Authorization header and result polling are the same as the other workflows.

`prompt` is required (1–10000 characters). `duration` is optional (integer, 1–15). `ref_image_0` and `ref_audio_0` are required. `ref_image_1`–`ref_image_5`, `ref_audio_1`–`ref_audio_2`, `resolution`, and `seed` are optional. Images accept jpeg/png/webp; audio accepts mpeg/wav/flac. The helper also accepts local files and resolves relative paths from the manifest directory.

Confirmed resolution enums:

- `480p竖(480*864)`
- `480p横(864*480)`
- `768p竖(768*1376)`
- `768p横(1376*768)`
- `1088p竖(1088*1920)`
- `1088p横(1920*1088)`
- `1440p竖(1440*2560)`
- `1440p横(2560*1440)`

The helper defaults to `768p横(1376*768)`. Do not send `width` or `height`.

### IndexTTS2 speech synthesis

- Workflow ID: `indextts2-v1`
- Submit: `POST https://www.autodl.art/api/v1/comfyui/comfyui_workflow/indextts2-v1`
- Authorization header and result polling are the same as the other workflows.

Required fields:

- `prompt_text`: synthesis text, 1–2048 characters.
- `prompt_simple`: timbre reference audio, URL or base64 mp3/wav.
- `emo_control_method`: one of `与音色参考音频相同`, `使用情感参考音频`, or `使用情感向量控制`.

Optional numeric emotion fields accept 0–1.4: `emo_afraid`, `emo_angry`, `emo_calm`, `emo_disgusted`, `emo_happy`, `emo_melancholic`, and `emo_sad`. `emo_random` is boolean. `emo_ref_audio` accepts URL or base64 mp3/wav. `emo_surprised` is passed through because its enum choices were not supplied in the available workflow documentation; do not invent an option.

The helper additionally accepts local mp3/wav paths for `prompt_simple` and `emo_ref_audio`, converting them to base64 data URLs. Relative paths resolve from the manifest directory. Successful output is downloaded to the `音频` directory and recorded as `audio_file` in `任务状态.json`.

## Response behavior

AutoDL commonly wraps valid results:

```json
{
  "code": "Success",
  "data": {
    "task_id": "...",
    "status": "QUEUED"
  },
  "msg": ""
}
```

Unwrap a dictionary in `data`. Poll statuses include `QUEUED`, `RUNNING`, and `SUCCESS`; failures may use `FAILED`, `FAILURE`, `CANCELLED`, or `CANCELED`.

The official documentation verified on 2026-10-07 specifies GET for result polling. The helper uses GET directly. Source: https://autodl.art/docs/comfyui_api/ . Create a token at https://autodl.art/large-model/tokens and choose the ComfyUI group. The official text-to-video example uses resolution `480p竖`; the full enum list still requires checking the workflow panel.

On `SUCCESS`, `results` contains objects with a resource `url`. These URLs expire quickly; download immediately.
