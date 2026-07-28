import unittest

import ffmpeg


class DependencyCompatibilityTest(unittest.TestCase):
    def test_ffmpeg_python_api_is_available(self):
        self.assertTrue(callable(ffmpeg.input))
        self.assertTrue(callable(ffmpeg.output))
        self.assertTrue(callable(ffmpeg.probe))


if __name__ == "__main__":
    unittest.main()
