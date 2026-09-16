import ast
import random
import threading
import types
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "niko_video_studio_v2.py"


def load_functions(session):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted = {"_table_rows", "_supports_i2v", "generate_sequence"}
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted
    ]
    module = ast.Module(body=functions, type_ignores=[])

    class Error(Exception):
        pass

    class Progress:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            pass

    gr = types.SimpleNamespace(Error=Error, Progress=Progress)
    v1 = types.SimpleNamespace()
    v1._ACTIVE_JOB_LOCK = threading.Lock()
    v1._ACTIVE_JOB = {"job": None}
    v1.get_session = lambda: session
    v1._compose_prompt = lambda prompt, preset: f"{prompt} | {preset}"

    namespace = {
        "Any": Any,
        "gr": gr,
        "v1": v1,
        "random": random,
        "_BATCH_CANCEL": threading.Event(),
        "_extract_last_frame": lambda path, index: f"frame-{index}.png",
        "_assemble_videos": lambda paths, fps: "film.mp4",
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


class Result:
    cancelled = False
    success = True
    errors = []

    def __init__(self, path):
        self.generated_files = [path]


class Job:
    done = False

    def __init__(self, path):
        self.path = path

    def result(self):
        return Result(self.path)

    def cancel(self):
        self.done = True


class Session:
    def __init__(self, i2v=True):
        self.i2v = i2v
        self.settings = []

    def get_default_settings(self, model):
        return {}

    def get_model_schema(self, model):
        return {
            "capabilities": {"image_to_video": self.i2v},
            "inputs": ["image"] if self.i2v else ["text"],
        }

    def submit_task(self, settings, callbacks=None):
        self.settings.append(dict(settings))
        return Job(f"shot-{len(self.settings)}.mp4")


class ProgressRecorder:
    def __call__(self, *args, **kwargs):
        pass


class SequenceLogicTests(unittest.TestCase):
    def test_frame_continuity_and_seed_are_carried(self):
        session = Session(True)
        namespace = load_functions(session)
        result = namespace["generate_sequence"](
            {},
            [[1, "first", 4], [2, "second", 4]],
            "same hero",
            "model",
            "Cinéma",
            "reference.png",
            "Frame précédente → plan suivant",
            "1280x720",
            24,
            8,
            42,
            progress=ProgressRecorder(),
        )
        self.assertEqual(result[0], "film.mp4")
        self.assertEqual(session.settings[0]["image_start"], "reference.png")
        self.assertEqual(session.settings[1]["image_start"], "frame-1.png")
        self.assertEqual([settings["seed"] for settings in session.settings], [42, 42])
        self.assertIn("same hero", session.settings[0]["prompt"])
        self.assertIn("same hero", session.settings[1]["prompt"])

    def test_non_i2v_model_does_not_receive_image_start(self):
        session = Session(False)
        namespace = load_functions(session)
        namespace["generate_sequence"](
            {},
            [[1, "first", 4], [2, "second", 4]],
            "same hero",
            "model",
            "Cinéma",
            "reference.png",
            "Frame précédente → plan suivant",
            "1280x720",
            24,
            8,
            7,
            progress=ProgressRecorder(),
        )
        self.assertTrue(all("image_start" not in settings for settings in session.settings))
        self.assertEqual([settings["seed"] for settings in session.settings], [7, 7])


if __name__ == "__main__":
    unittest.main()
