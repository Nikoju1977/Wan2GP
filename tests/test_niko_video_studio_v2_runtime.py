import importlib.util
import inspect
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_runtime():
    for name in ("gradio", "niko_video_studio", "niko_video_studio_v2", "niko_video_studio_v2_runtime"):
        sys.modules.pop(name, None)

    gradio = types.ModuleType("gradio")

    class Error(Exception):
        pass

    gradio.Error = Error
    sys.modules["gradio"] = gradio

    v1 = types.ModuleType("niko_video_studio")
    v1._ACTIVE_JOB_LOCK = threading.Lock()
    v1._ACTIVE_JOB = {"job": None}

    def generate_video(*args, **kwargs):
        return ("single-ok", args, kwargs)

    v1.generate_video = generate_video
    sys.modules["niko_video_studio"] = v1

    v2 = types.ModuleType("niko_video_studio_v2")

    def _load_json_source(project_file, project_json):
        if project_file:
            return json.loads(Path(project_file).read_text())
        return json.loads(project_json)

    v2._load_json_source = _load_json_source
    v2.import_ia_studio_project = lambda project_file, project_json: (
        "import-ok",
        _load_json_source(project_file, project_json),
    )
    v2._table_rows = lambda table: table
    v2.generate_sequence = lambda *args, **kwargs: ("sequence-ok", args, kwargs)

    def assemble(paths, fps):
        output = Path(paths[0]).with_name("assembled.mp4")
        output.write_bytes(b"video")
        return str(output)

    v2._assemble_videos = assemble
    v2.main = lambda: "main-ok"
    sys.modules["niko_video_studio_v2"] = v2

    spec = importlib.util.spec_from_file_location(
        "niko_video_studio_v2_runtime", ROOT / "niko_video_studio_v2_runtime.py"
    )
    runtime = importlib.util.module_from_spec(spec)
    sys.modules["niko_video_studio_v2_runtime"] = runtime
    spec.loader.exec_module(runtime)
    return runtime, v1, v2, gradio


VALID = {
    "schema": "niko-video-project/v1",
    "sections": {},
    "continuity": {},
    "shots": [{"id": 1, "prompt": "shot", "duration": 4}],
}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.rt, self.v1, self.v2, self.gr = load_runtime()
        self.rt.install_runtime_guards()

    def test_validated_import(self):
        self.assertEqual(
            self.v2.import_ia_studio_project(None, json.dumps(VALID))[0],
            "import-ok",
        )
        bad = dict(VALID)
        bad["shots"] = []
        with self.assertRaises(self.gr.Error):
            self.v2.import_ia_studio_project(None, json.dumps(bad))

    def test_sequence_validation(self):
        args = (
            VALID,
            [[1, "shot", 4]],
            "continuity",
            "model",
            "Cinéma",
            None,
            "Prompt seulement",
            "1280x720",
            24,
            8,
            -1,
        )
        self.assertEqual(self.v2.generate_sequence(*args)[0], "sequence-ok")
        bad = list(args)
        bad[1] = [[1, "", 4]]
        with self.assertRaises(self.gr.Error):
            self.v2.generate_sequence(*bad)

    def test_gpu_lock(self):
        self.assertTrue(self.rt._GPU_LOCK.acquire(False))
        args = (
            "model",
            "Texte → Vidéo",
            "prompt",
            "",
            None,
            "Cinéma",
            "1280x720",
            4,
            24,
            8,
            -1,
        )
        with self.assertRaises(self.gr.Error):
            self.v1.generate_video(*args)
        self.rt._GPU_LOCK.release()

    def test_signature_preserved(self):
        self.assertEqual(
            inspect.signature(self.v1.generate_video),
            inspect.signature(self.rt._validated_single),
        )

    def test_assemble_requires_real_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "a.mp4"
            video.write_bytes(b"video")
            output = self.v2._assemble_videos([str(video)], 24)
            self.assertTrue(Path(output).is_file())
            with self.assertRaises(RuntimeError):
                self.v2._assemble_videos([str(Path(tmp) / "missing.mp4")], 24)


if __name__ == "__main__":
    unittest.main()
