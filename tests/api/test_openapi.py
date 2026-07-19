import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("fastapi"), "FastAPI extra is not installed")
class OpenApiContractTests(unittest.TestCase):
    def test_expected_v1_paths_are_documented(self) -> None:
        from src.minidungeons.api import app

        self.assertIsNotNone(app)
        paths = set(app.openapi()["paths"])
        self.assertTrue(
            {
                "/health",
                "/api/v1/maps",
                "/api/v1/rules",
                "/api/v1/games",
                "/api/v1/games/{session_id}",
                "/api/v1/games/{session_id}/actions",
                "/api/v1/games/{session_id}/reset",
            }.issubset(paths)
        )


if __name__ == "__main__":
    unittest.main()
