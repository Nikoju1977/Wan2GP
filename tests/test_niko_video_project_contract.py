import tempfile
import unittest
from pathlib import Path

from niko_video_project_contract import (
    SCHEMA,
    existing_video_paths,
    normalize_seed,
    validate_project,
    validate_timeline_rows,
)


def valid_project():
    return {
        "schema": SCHEMA,
        "sections": {"image": "[PROMPT: shot]"},
        "continuity": {"bible": "same hero"},
        "shots": [{"id": 1, "prompt": "cinematic shot", "duration": 4}],
    }


class ContractTests(unittest.TestCase):
    def test_valid_project(self):
        self.assertEqual(validate_project(valid_project()), [])

    def test_requires_exact_schema(self):
        project = valid_project()
        project.pop("schema")
        self.assertTrue(validate_project(project))
        project["schema"] = "other"
        self.assertTrue(validate_project(project))

    def test_rejects_empty_prompt_bad_duration_duplicate_id(self):
        project = valid_project()
        project["shots"] = [
            {"id": 1, "prompt": "", "duration": 4},
            {"id": 1, "prompt": "x", "duration": 120},
        ]
        errors = " | ".join(validate_project(project))
        self.assertIn("prompt vide", errors)
        self.assertIn("dupliqué", errors)
        self.assertIn("durée invalide", errors)

    def test_timeline_validation(self):
        self.assertEqual(
            validate_timeline_rows([[1, "shot", 4], [2, "shot 2", 3.5]]),
            [],
        )
        self.assertTrue(validate_timeline_rows([[1, "", 4]]))

    def test_seed(self):
        self.assertEqual(normalize_seed(-1), -1)
        self.assertEqual(normalize_seed(42), 42)
        for bad in (None, True, 1.2, float("nan"), -2, 2_147_483_648):
            with self.assertRaises(ValueError):
                normalize_seed(bad)

    def test_existing_video_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.mp4"
            video.write_bytes(b"x")
            text = Path(tmp) / "note.txt"
            text.write_text("x")
            missing = Path(tmp) / "missing.mp4"
            self.assertEqual(existing_video_paths([text, missing, video]), [str(video)])


if __name__ == "__main__":
    unittest.main()
