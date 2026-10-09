#!/usr/bin/env python3
"""Jinghong B-roll Skill: generate and organize AutoDL MiniMax H3 media from a JSON manifest."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = "https://autodl.art/api/v1/comfyui"
DEFAULT_WORKFLOW = "minimax_h3_lightx2v_no_pic"
IMAGE_TO_VIDEO_WORKFLOW = "minimax_h3_z0902"
IMAGE_AUDIO_TO_VIDEO_WORKFLOW = "minimax_h3_z0903"
FIRST_LAST_WORKFLOW = "minimax_h3_b99_002"
MULTI_IMAGE_12S_WORKFLOW = "minimax_h3_b99_003_12s"
INDEXTTS2_WORKFLOW = "indextts2-v1"
FINAL = {"SUCCESS", "FAILED", "FAILURE", "CANCELLED", "CANCELED"}
REF_IMAGE_KEYS = tuple(f"ref_image_{index}" for index in range(9))
REF_AUDIO_KEYS = tuple(f"ref_audio_{index}" for index in range(3))
FIRST_LAST_IMAGE_KEYS = ("first_frame", "last_frame")
FIRST_LAST_RESOLUTIONS = {"736p竖", "736p横", "736p(1:1)"}
MULTI_IMAGE_12S_RESOLUTIONS = {"736p竖", "736p横", "736p(1:1)"}
MULTI_IMAGE_RESOLUTIONS = {
    "480p竖(480*864)", "480p横(864*480)",
    "768p竖(768*1376)", "768p横(1376*768)",
    "1088p竖(1088*1920)", "1088p横(1920*1088)",
    "1440p竖(1440*2560)", "1440p横(2560*1440)",
}
ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AUDIO_MIME_TYPES = {"audio/mpeg", "audio/wav", "audio/flac", "audio/x-wav"}
INDEXTTS2_AUDIO_MIME_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav"}
INDEXTTS2_CONTROL_METHODS = {"与音色参考音频相同", "使用情感参考音频", "使用情感向量控制"}
INDEXTTS2_EMOTION_KEYS = (
    "emo_afraid", "emo_angry", "emo_calm", "emo_disgusted",
    "emo_happy", "emo_melancholic", "emo_sad",
)


class APIError(RuntimeError):
    pass


def load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


class Client:
    def __init__(self, token: str, timeout: float = 60) -> None:
        self.token = token
        self.timeout = timeout

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{BASE_URL}/{path.lstrip('/')}", data=data, method=method,
            headers={"Authorization": self.token, "Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise APIError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise APIError(f"无法连接 AutoDL：{exc.reason}") from exc
        if not isinstance(payload, dict):
            raise APIError("AutoDL 返回了非对象 JSON")
        if "code" in payload:
            if payload.get("code") != "Success":
                raise APIError(f"{payload.get('code')}：{payload.get('msg', payload)}")
            if isinstance(payload.get("data"), dict):
                return payload["data"]
        return payload

    def submit(self, workflow: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", f"comfyui_workflow/{urllib.parse.quote(workflow, safe='')}", body)

    def result(self, task_id: str) -> dict[str, Any]:
        path = f"comfyui_workflow/result/{urllib.parse.quote(task_id, safe='')}"
        return self.request("GET", path)


def safe_name(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|\r\n]+", "-", value).strip(" .-")
    return value[:80] or "未命名镜头"


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def normalize_media(
    value: Any, manifest_dir: Path, key: str, allowed_mime_types: set[str], kind: str
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} 必须是{kind} URL、data URL、base64 字符串或本地文件路径")
    value = value.strip()
    if value.startswith(("http://", "https://")):
        return value
    if value.startswith("data:"):
        header, separator, payload = value.partition(",")
        mime_type = header[5:].split(";", 1)[0].lower()
        if not separator or ";base64" not in header.lower() or mime_type not in allowed_mime_types:
            raise ValueError(f"{key} 的 base64 data URL 媒体类型不受支持")
        try:
            base64.b64decode(payload, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError(f"{key} 包含无效 base64 数据") from exc
        return value
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = manifest_dir / candidate
    try:
        is_file = candidate.is_file()
    except OSError:
        is_file = False
    if is_file:
        mime_type = mimetypes.guess_type(candidate.name)[0]
        if mime_type == "image/jpg":
            mime_type = "image/jpeg"
        if mime_type not in allowed_mime_types:
            raise ValueError(f"{key} 本地{kind}文件格式不受支持：{candidate}")
        encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
    try:
        base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"{key} 不是有效 URL、data URL、base64 字符串或本地文件：{value}") from exc
    return value


def normalize_ref_image(value: Any, manifest_dir: Path, key: str) -> str:
    return normalize_media(value, manifest_dir, key, ALLOWED_IMAGE_MIME_TYPES, "图片")


def normalize_ref_audio(value: Any, manifest_dir: Path, key: str) -> str:
    normalized = normalize_media(value, manifest_dir, key, ALLOWED_AUDIO_MIME_TYPES, "音频")
    if normalized.startswith("data:audio/x-wav;"):
        normalized = "data:audio/wav;" + normalized.split(";", 1)[1]
    return normalized


def normalize_indextts2_audio(value: Any, manifest_dir: Path, key: str) -> str:
    normalized = normalize_media(value, manifest_dir, key, INDEXTTS2_AUDIO_MIME_TYPES, "音频")
    if normalized.startswith("data:audio/x-wav;"):
        normalized = "data:audio/wav;" + normalized.split(";", 1)[1]
    return normalized


def result_urls(result: dict[str, Any]) -> list[str]:
    found = []
    for item in result.get("results", []):
        if isinstance(item, str) and item.startswith(("http://", "https://")):
            found.append(item)
        elif isinstance(item, dict):
            for key in ("url", "file_url", "video_url", "audio_url", "image_url"):
                value = item.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    found.append(value)
                    break
    return found


def download(url: str, destination: Path, timeout: float = 180) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as source, temporary.open("wb") as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)
    temporary.replace(destination)


def validate_manifest(value: Any, manifest_dir: Path) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(value, dict) or not isinstance(value.get("clips"), list) or not value["clips"]:
        raise ValueError("manifest 必须包含非空 clips 数组")
    workflow = str(value.get("workflow_id") or DEFAULT_WORKFLOW)
    seen = set()
    clips = []
    for index, raw in enumerate(value["clips"], 1):
        if not isinstance(raw, dict):
            raise ValueError(f"第 {index} 个 clip 不是对象")
        clip_id = safe_name(str(raw.get("id") or f"{index:02d}"))
        title = safe_name(str(raw.get("title") or f"镜头{index:02d}"))
        key = f"{clip_id}-{title}"
        if key in seen:
            raise ValueError(f"重复镜头键：{key}")
        seen.add(key)
        if workflow == INDEXTTS2_WORKFLOW:
            prompt_text = str(raw.get("prompt_text") or "").strip()
            if not 1 <= len(prompt_text) <= 2048:
                raise ValueError(f"{key} 的 prompt_text 长度必须在 1–2048")
            if raw.get("prompt_simple") is None:
                raise ValueError(f"{key} 使用 {INDEXTTS2_WORKFLOW} 时必须提供 prompt_simple")
            control_method = str(raw.get("emo_control_method") or "").strip()
            if control_method not in INDEXTTS2_CONTROL_METHODS:
                allowed = "、".join(sorted(INDEXTTS2_CONTROL_METHODS))
                raise ValueError(f"{key} 的 emo_control_method 必须是 {allowed} 之一")
            clip = {
                "key": key, "id": clip_id, "title": title,
                "prompt_text": prompt_text,
                "prompt_simple": normalize_indextts2_audio(
                    raw["prompt_simple"], manifest_dir, f"{key}.prompt_simple"
                ),
                "emo_control_method": control_method,
            }
            if raw.get("emo_ref_audio") is not None:
                clip["emo_ref_audio"] = normalize_indextts2_audio(
                    raw["emo_ref_audio"], manifest_dir, f"{key}.emo_ref_audio"
                )
            for emotion_key in INDEXTTS2_EMOTION_KEYS:
                if raw.get(emotion_key) is None:
                    continue
                if isinstance(raw[emotion_key], bool):
                    raise ValueError(f"{key}.{emotion_key} 必须是 0–1.4 的数字")
                try:
                    emotion_value = float(raw[emotion_key])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{key}.{emotion_key} 必须是 0–1.4 的数字") from exc
                if not 0 <= emotion_value <= 1.4:
                    raise ValueError(f"{key}.{emotion_key} 必须在 0–1.4")
                clip[emotion_key] = emotion_value
            if raw.get("emo_random") is not None:
                if not isinstance(raw["emo_random"], bool):
                    raise ValueError(f"{key}.emo_random 必须是布尔值")
                clip["emo_random"] = raw["emo_random"]
            if raw.get("emo_surprised") is not None:
                clip["emo_surprised"] = raw["emo_surprised"]
            clips.append(clip)
            continue
        duration = int(raw.get("duration", 5))
        max_duration = 12 if workflow == MULTI_IMAGE_12S_WORKFLOW else 15
        if not 1 <= duration <= max_duration:
            raise ValueError(f"{key} 的 duration 必须在 1–{max_duration}")
        prompt = str(raw.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(f"{key} 缺少 prompt")
        if len(prompt) > 10000:
            raise ValueError(f"{key} 的 prompt 长度必须在 1–10000")
        clip = {"key": key, "id": clip_id, "title": title, "duration": duration, "prompt": prompt}
        if raw.get("resolution") is not None:
            clip["resolution"] = str(raw["resolution"])
        elif workflow in {IMAGE_TO_VIDEO_WORKFLOW, IMAGE_AUDIO_TO_VIDEO_WORKFLOW}:
            clip["resolution"] = "768p横(1376*768)"
        elif workflow == FIRST_LAST_WORKFLOW:
            clip["resolution"] = "736p横"
        elif workflow == MULTI_IMAGE_12S_WORKFLOW:
            clip["resolution"] = "736p横"
        else:
            clip["resolution"] = "768p横"
        if workflow == FIRST_LAST_WORKFLOW and clip["resolution"] not in FIRST_LAST_RESOLUTIONS:
            allowed = "、".join(sorted(FIRST_LAST_RESOLUTIONS))
            raise ValueError(f"{key} 的 resolution 必须是 {allowed} 之一")
        if workflow == MULTI_IMAGE_12S_WORKFLOW and clip["resolution"] not in MULTI_IMAGE_12S_RESOLUTIONS:
            allowed = "、".join(sorted(MULTI_IMAGE_12S_RESOLUTIONS))
            raise ValueError(f"{key} 的 resolution 必须是 {allowed} 之一")
        if workflow in {IMAGE_TO_VIDEO_WORKFLOW, IMAGE_AUDIO_TO_VIDEO_WORKFLOW} and clip["resolution"] not in MULTI_IMAGE_RESOLUTIONS:
            allowed = "、".join(sorted(MULTI_IMAGE_RESOLUTIONS))
            raise ValueError(f"{key} 的 resolution 必须是 {allowed} 之一")
        for ref_key in (*REF_IMAGE_KEYS, *FIRST_LAST_IMAGE_KEYS):
            if raw.get(ref_key) is not None:
                clip[ref_key] = normalize_ref_image(raw[ref_key], manifest_dir, f"{key}.{ref_key}")
        for ref_key in REF_AUDIO_KEYS:
            if raw.get(ref_key) is not None:
                clip[ref_key] = normalize_ref_audio(raw[ref_key], manifest_dir, f"{key}.{ref_key}")
        if workflow == IMAGE_TO_VIDEO_WORKFLOW and "ref_image_0" not in clip:
            raise ValueError(f"{key} 使用 {IMAGE_TO_VIDEO_WORKFLOW} 时必须提供 ref_image_0")
        if workflow == MULTI_IMAGE_12S_WORKFLOW and "ref_image_0" not in clip:
            raise ValueError(f"{key} 使用 {MULTI_IMAGE_12S_WORKFLOW} 时必须提供 ref_image_0")
        if workflow == IMAGE_AUDIO_TO_VIDEO_WORKFLOW:
            for required_key in ("ref_image_0", "ref_audio_0"):
                if required_key not in clip:
                    raise ValueError(f"{key} 使用 {IMAGE_AUDIO_TO_VIDEO_WORKFLOW} 时必须提供 {required_key}")
        if workflow in {IMAGE_TO_VIDEO_WORKFLOW, IMAGE_AUDIO_TO_VIDEO_WORKFLOW}:
            for unsupported_key in REF_IMAGE_KEYS[6:]:
                if unsupported_key in clip:
                    raise ValueError(f"{key} 使用 {workflow} 时不支持 {unsupported_key}")
        if workflow == FIRST_LAST_WORKFLOW:
            for frame_key in FIRST_LAST_IMAGE_KEYS:
                if frame_key not in clip:
                    raise ValueError(f"{key} 使用 {FIRST_LAST_WORKFLOW} 时必须提供 {frame_key}")
        if raw.get("seed") is not None:
            if isinstance(raw["seed"], bool):
                raise ValueError(f"{key} 的 seed 必须是整数")
            try:
                seed = int(raw["seed"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} 的 seed 必须是整数") from exc
            if not 1 <= seed <= 999999999999999:
                raise ValueError(f"{key} 的 seed 必须在 1–999999999999999")
            clip["seed"] = seed
        clips.append(clip)
    return workflow, clips


def request_body(clip: dict[str, Any]) -> dict[str, Any]:
    if "prompt_text" in clip:
        keys = (
            "prompt_text", "prompt_simple", "emo_control_method", "emo_ref_audio",
            *INDEXTTS2_EMOTION_KEYS, "emo_random", "emo_surprised",
        )
        return {key: clip[key] for key in keys if key in clip}
    body = {"duration": clip["duration"], "prompt": clip["prompt"]}
    for key in ("resolution", *REF_IMAGE_KEYS, *REF_AUDIO_KEYS, *FIRST_LAST_IMAGE_KEYS, "seed"):
        if key in clip:
            body[key] = clip[key]
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("broll输出"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--poll-interval", type=int, default=15)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        load_env(args.env_file)
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    workflow, clips = validate_manifest(manifest, manifest_path.parent)
    bodies_dir = args.output_dir / "请求Body"
    media_dir = args.output_dir / ("音频" if workflow == INDEXTTS2_WORKFLOW else "视频")
    state_path = args.output_dir / "任务状态.json"
    for clip in clips:
        save_json(bodies_dir / f"{clip['key']}.json", request_body(clip))
    if args.prepare_only:
        print(f"已准备 {len(clips)} 个请求 Body：{bodies_dir}")
        return 0

    token = os.environ.get("AUTODL_ART_TOKEN", "").strip()
    if not token:
        raise SystemExit("缺少 AUTODL_ART_TOKEN；请设置环境变量或使用 --env-file")
    client = Client(token)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
        "workflow_id": workflow, "manifest": str(args.manifest.resolve()), "clips": {}
    }
    if state.get("workflow_id") != workflow:
        raise ValueError(
            f"输出目录已有工作流 {state.get('workflow_id')} 的状态，不能改用 {workflow}；请使用新的输出目录"
        )
    for clip in clips:
        record = state["clips"].setdefault(clip["key"], {
            "id": clip["id"], "title": clip["title"], "duration": clip.get("duration"),
            "resolution": clip.get("resolution"), "status": "NOT_SUBMITTED"
        })
        if record.get("task_id"):
            continue
        response = client.submit(workflow, request_body(clip))
        task_id = response.get("task_id")
        if not task_id:
            raise APIError(f"{clip['key']} 未返回 task_id：{response}")
        record.update(task_id=task_id, status=str(response.get("status", "QUEUED")).upper())
        save_json(state_path, state)
        print(f"已提交 {clip['key']}：{task_id}", flush=True)
        time.sleep(1)

    while True:
        active = 0
        for clip in clips:
            record = state["clips"][clip["key"]]
            if record["status"] in FINAL:
                continue
            active += 1
            response = client.result(record["task_id"])
            status = str(response.get("status", "UNKNOWN")).upper()
            record["status"] = status
            print(f"{clip['key']}：{status}", flush=True)
            if status == "SUCCESS":
                urls = result_urls(response)
                if len(urls) != 1:
                    raise APIError(f"{clip['key']} 成功但返回 {len(urls)} 个资源")
                suffix = ".wav" if workflow == INDEXTTS2_WORKFLOW else ".mp4"
                if workflow == INDEXTTS2_WORKFLOW:
                    url_suffix = Path(urllib.parse.urlparse(urls[0]).path).suffix.lower()
                    if url_suffix in {".mp3", ".wav"}:
                        suffix = url_suffix
                destination = media_dir / f"{clip['key']}{suffix}"
                download(urls[0], destination)
                record["audio_file" if workflow == INDEXTTS2_WORKFLOW else "video_file"] = str(destination.resolve())
                print(f"已下载：{destination}", flush=True)
            elif status in FINAL:
                record["error"] = response
            save_json(state_path, state)
        if active == 0:
            break
        time.sleep(max(args.poll_interval, 1))
    failures = [key for key, record in state["clips"].items() if record["status"] != "SUCCESS"]
    print(f"完成：{len(clips) - len(failures)}/{len(clips)} 成功", flush=True)
    if failures:
        print("失败：" + "、".join(failures), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
