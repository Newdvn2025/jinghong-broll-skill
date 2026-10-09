import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "autodl_broll.py"
SPEC = importlib.util.spec_from_file_location("autodl_broll", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ManifestValidationTests(unittest.TestCase):
    def test_multi_image_12s_requires_first_reference(self):
        manifest = {
            "workflow_id": MODULE.MULTI_IMAGE_12S_WORKFLOW,
            "clips": [{"id": "01", "title": "测试", "prompt": "多图一致性镜头"}],
        }
        with self.assertRaisesRegex(ValueError, "必须提供 ref_image_0"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_multi_image_12s_forwards_ninth_image_and_defaults_horizontal(self):
        manifest = {
            "workflow_id": MODULE.MULTI_IMAGE_12S_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "duration": 12,
                "prompt": "多图一致性镜头",
                "ref_image_0": "https://example.com/character.png",
                "ref_image_8": "https://example.com/style.webp", "seed": 999999999999999,
            }],
        }
        workflow, clips = MODULE.validate_manifest(manifest, Path.cwd())
        body = MODULE.request_body(clips[0])
        self.assertEqual(workflow, MODULE.MULTI_IMAGE_12S_WORKFLOW)
        self.assertEqual(body["resolution"], "736p横")
        self.assertEqual(body["ref_image_8"], "https://example.com/style.webp")

    def test_multi_image_12s_rejects_duration_above_twelve(self):
        manifest = {
            "workflow_id": MODULE.MULTI_IMAGE_12S_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "duration": 13,
                "prompt": "多图一致性镜头",
                "ref_image_0": "https://example.com/character.png",
            }],
        }
        with self.assertRaisesRegex(ValueError, "duration 必须在 1–12"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_multi_image_12s_rejects_unknown_resolution(self):
        manifest = {
            "workflow_id": MODULE.MULTI_IMAGE_12S_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "prompt": "多图一致性镜头",
                "resolution": "768p横", "ref_image_0": "https://example.com/character.png",
            }],
        }
        with self.assertRaisesRegex(ValueError, "resolution 必须是"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_six_image_workflow_rejects_seventh_reference(self):
        manifest = {
            "workflow_id": MODULE.IMAGE_TO_VIDEO_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "prompt": "多图一致性镜头",
                "ref_image_0": "https://example.com/character.png",
                "ref_image_6": "https://example.com/extra.png",
            }],
        }
        with self.assertRaisesRegex(ValueError, "不支持 ref_image_6"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_indextts2_requires_reference_audio_and_control_method(self):
        manifest = {
            "workflow_id": MODULE.INDEXTTS2_WORKFLOW,
            "clips": [{"id": "01", "title": "旁白", "prompt_text": "你好"}],
        }
        with self.assertRaisesRegex(ValueError, "必须提供 prompt_simple"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_indextts2_normalizes_audio_and_forwards_emotions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "voice.wav").write_bytes(b"RIFF-test-wave")
            manifest = {
                "workflow_id": MODULE.INDEXTTS2_WORKFLOW,
                "clips": [{
                    "id": "01", "title": "旁白", "prompt_text": "你好，世界。",
                    "prompt_simple": "voice.wav",
                    "emo_control_method": "使用情感向量控制",
                    "emo_calm": 1.2, "emo_happy": 0.2,
                    "emo_random": False, "emo_surprised": "low",
                }],
            }
            workflow, clips = MODULE.validate_manifest(manifest, root)
            body = MODULE.request_body(clips[0])
        self.assertEqual(workflow, MODULE.INDEXTTS2_WORKFLOW)
        self.assertTrue(body["prompt_simple"].startswith("data:audio/wav;base64,"))
        self.assertEqual(body["prompt_text"], "你好，世界。")
        self.assertEqual(body["emo_calm"], 1.2)
        self.assertEqual(body["emo_surprised"], "low")
        self.assertNotIn("duration", body)

    def test_indextts2_rejects_out_of_range_emotion(self):
        manifest = {
            "workflow_id": MODULE.INDEXTTS2_WORKFLOW,
            "clips": [{
                "id": "01", "title": "旁白", "prompt_text": "你好",
                "prompt_simple": "https://example.com/voice.mp3",
                "emo_control_method": "与音色参考音频相同", "emo_angry": 1.5,
            }],
        }
        with self.assertRaisesRegex(ValueError, "emo_angry 必须在 0–1.4"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_result_urls_accepts_audio_url(self):
        result = {"results": [{"audio_url": "https://example.com/result.wav"}]}
        self.assertEqual(MODULE.result_urls(result), ["https://example.com/result.wav"])

    def test_image_audio_workflow_requires_first_image_and_audio(self):
        manifest = {
            "workflow_id": MODULE.IMAGE_AUDIO_TO_VIDEO_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "prompt": "高质量音画融合",
                "ref_image_0": "https://example.com/reference.png",
            }],
        }
        with self.assertRaisesRegex(ValueError, "必须提供 ref_audio_0"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_image_audio_workflow_normalizes_local_audio_and_forwards_all_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "voice.wav").write_bytes(b"RIFF-test-wave")
            manifest = {
                "workflow_id": MODULE.IMAGE_AUDIO_TO_VIDEO_WORKFLOW,
                "clips": [{
                    "id": "01", "title": "测试", "duration": 15,
                    "prompt": "高质量音画融合",
                    "ref_image_0": "https://example.com/reference.png",
                    "ref_image_5": "https://example.com/style.webp",
                    "ref_audio_0": "voice.wav",
                    "ref_audio_2": "https://example.com/ambience.flac",
                }],
            }
            workflow, clips = MODULE.validate_manifest(manifest, root)
            body = MODULE.request_body(clips[0])
        self.assertEqual(workflow, MODULE.IMAGE_AUDIO_TO_VIDEO_WORKFLOW)
        self.assertEqual(body["resolution"], "768p横(1376*768)")
        self.assertTrue(body["ref_audio_0"].startswith("data:audio/wav;base64,"))
        self.assertEqual(body["ref_image_5"], "https://example.com/style.webp")
        self.assertEqual(body["ref_audio_2"], "https://example.com/ambience.flac")

    def test_image_audio_workflow_rejects_unknown_resolution(self):
        manifest = {
            "workflow_id": MODULE.IMAGE_AUDIO_TO_VIDEO_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "prompt": "高质量音画融合",
                "resolution": "768p横", "ref_image_0": "https://example.com/reference.png",
                "ref_audio_0": "https://example.com/voice.mp3",
            }],
        }
        with self.assertRaisesRegex(ValueError, "resolution 必须是"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_text_to_video_remains_compatible(self):
        manifest = {
            "workflow_id": "minimax_h3_lightx2v_no_pic",
            "clips": [{"id": "01", "title": "测试", "duration": 4, "prompt": "一个稳定镜头"}],
        }
        workflow, clips = MODULE.validate_manifest(manifest, Path.cwd())
        self.assertEqual(workflow, "minimax_h3_lightx2v_no_pic")
        self.assertNotIn("ref_image_0", MODULE.request_body(clips[0]))

    def test_image_to_video_requires_first_reference(self):
        manifest = {
            "workflow_id": "minimax_h3_z0902",
            "clips": [{"id": "01", "title": "测试", "duration": 8, "prompt": "保持人物一致"}],
        }
        with self.assertRaisesRegex(ValueError, "必须提供 ref_image_0"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_local_image_is_converted_and_optional_fields_are_forwarded(self):
        one_pixel_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reference.png").write_bytes(one_pixel_png)
            manifest = {
                "workflow_id": "minimax_h3_z0902",
                "clips": [{
                    "id": "01", "title": "测试", "duration": 8, "resolution": "768p竖(768*1376)",
                    "prompt": "保持人物一致", "ref_image_0": "reference.png",
                    "ref_image_1": "https://example.com/style.webp", "seed": 999999999999999,
                }],
            }
            workflow, clips = MODULE.validate_manifest(manifest, root)
            body = MODULE.request_body(clips[0])
        self.assertEqual(workflow, "minimax_h3_z0902")
        self.assertEqual(body["resolution"], "768p竖(768*1376)")
        self.assertTrue(body["ref_image_0"].startswith("data:image/png;base64,"))
        self.assertEqual(body["ref_image_1"], "https://example.com/style.webp")
        self.assertEqual(body["seed"], 999999999999999)

    def test_invalid_seed_is_rejected(self):
        manifest = {
            "workflow_id": "minimax_h3_z0902",
            "clips": [{
                "id": "01", "title": "测试", "duration": 8, "prompt": "保持人物一致",
                "ref_image_0": "https://example.com/reference.png", "seed": 0,
            }],
        }
        with self.assertRaisesRegex(ValueError, "seed 必须在"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_image_to_video_uses_workflow_specific_default_resolution(self):
        manifest = {
            "workflow_id": "minimax_h3_z0902",
            "clips": [{
                "id": "01", "title": "测试", "duration": 8, "prompt": "保持人物一致",
                "ref_image_0": "https://example.com/reference.png",
            }],
        }
        _, clips = MODULE.validate_manifest(manifest, Path.cwd())
        self.assertEqual(MODULE.request_body(clips[0])["resolution"], "768p横(1376*768)")

    def test_image_to_video_rejects_short_text_workflow_resolution(self):
        manifest = {
            "workflow_id": MODULE.IMAGE_TO_VIDEO_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "duration": 8, "prompt": "保持多图一致",
                "resolution": "768p横", "ref_image_0": "https://example.com/reference.png",
            }],
        }
        with self.assertRaisesRegex(ValueError, "resolution 必须是"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_large_raw_base64_is_not_treated_as_a_file_path(self):
        raw_base64 = base64.b64encode(b"x" * 4096).decode("ascii")
        manifest = {
            "workflow_id": "minimax_h3_z0902",
            "clips": [{
                "id": "01", "title": "测试", "duration": 8, "prompt": "保持人物一致",
                "ref_image_0": raw_base64,
            }],
        }
        _, clips = MODULE.validate_manifest(manifest, Path.cwd())
        self.assertEqual(clips[0]["ref_image_0"], raw_base64)

    def test_prompt_limit_is_enforced(self):
        manifest = {
            "workflow_id": "minimax_h3_lightx2v_no_pic",
            "clips": [{"id": "01", "title": "测试", "duration": 4, "prompt": "x" * 10001}],
        }
        with self.assertRaisesRegex(ValueError, "prompt 长度"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_text_to_video_keeps_default_resolution(self):
        manifest = {
            "workflow_id": "minimax_h3_lightx2v_no_pic",
            "clips": [{"id": "01", "title": "测试", "duration": 4, "prompt": "稳定镜头"}],
        }
        _, clips = MODULE.validate_manifest(manifest, Path.cwd())
        self.assertEqual(MODULE.request_body(clips[0])["resolution"], "768p横")

    def test_first_last_workflow_requires_both_endpoint_frames(self):
        manifest = {
            "workflow_id": MODULE.FIRST_LAST_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "duration": 6,
                "prompt": "在两个端点画面之间平滑运动。",
                "first_frame": "https://example.com/first.png",
            }],
        }
        with self.assertRaisesRegex(ValueError, "必须提供 last_frame"):
            MODULE.validate_manifest(manifest, Path.cwd())

    def test_first_last_workflow_normalizes_local_frames_and_defaults_horizontal(self):
        one_pixel_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "first.png").write_bytes(one_pixel_png)
            (root / "last.png").write_bytes(one_pixel_png)
            manifest = {
                "workflow_id": MODULE.FIRST_LAST_WORKFLOW,
                "clips": [{
                    "id": "01", "title": "测试", "duration": 8,
                    "prompt": "前景擦过镜头，将第一个场景自然转换成第二个场景。",
                    "first_frame": "first.png", "last_frame": "last.png", "seed": 123456,
                }],
            }
            workflow, clips = MODULE.validate_manifest(manifest, root)
            body = MODULE.request_body(clips[0])
        self.assertEqual(workflow, MODULE.FIRST_LAST_WORKFLOW)
        self.assertEqual(body["resolution"], "736p横")
        self.assertTrue(body["first_frame"].startswith("data:image/png;base64,"))
        self.assertTrue(body["last_frame"].startswith("data:image/png;base64,"))
        self.assertEqual(body["seed"], 123456)

    def test_first_last_workflow_rejects_unknown_resolution(self):
        manifest = {
            "workflow_id": MODULE.FIRST_LAST_WORKFLOW,
            "clips": [{
                "id": "01", "title": "测试", "duration": 6,
                "resolution": "768p横", "prompt": "平滑转场。",
                "first_frame": "https://example.com/first.png",
                "last_frame": "https://example.com/last.png",
            }],
        }
        with self.assertRaisesRegex(ValueError, "resolution 必须是"):
            MODULE.validate_manifest(manifest, Path.cwd())


if __name__ == "__main__":
    unittest.main()
