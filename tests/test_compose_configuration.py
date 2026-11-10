import json
import re
import unittest
from pathlib import Path

import yaml

from yt_dl_bot.setting import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = REPOSITORY_ROOT / "compose.yaml"
ENV_EXAMPLE_PATH = REPOSITORY_ROOT / ".env.example"


def compose_environment() -> dict[str, str]:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    return compose["services"]["bot"]["environment"]


def interpolation_default(value: str) -> str:
    match = re.fullmatch(r"\$\{[A-Z_]+-(.*)\}", value)
    if match is None:
        raise AssertionError(f"Environment value has no default: {value!r}")
    return match.group(1)


class ComposeConfigurationTest(unittest.TestCase):
    def test_compose_manages_exactly_the_application_settings(self):
        self.assertEqual(set(compose_environment()), set(Settings.model_fields))

    def test_every_compose_setting_can_be_overridden_from_the_environment(self):
        for name, value in compose_environment().items():
            with self.subTest(setting=name):
                self.assertRegex(value, rf"^\$\{{{name}(?:-|:\?)")

    def test_required_compose_settings_fail_fast_when_missing(self):
        for name, field in Settings.model_fields.items():
            if not field.is_required():
                continue
            with self.subTest(setting=name):
                self.assertRegex(compose_environment()[name], rf"^\$\{{{name}:\?")

    def test_optional_settings_preserve_explicit_empty_values(self):
        for name, field in Settings.model_fields.items():
            if field.is_required():
                continue
            with self.subTest(setting=name):
                self.assertTrue(compose_environment()[name].startswith("${" + name + "-"))

    def test_compose_defaults_match_the_application_defaults(self):
        for name, field in Settings.model_fields.items():
            if field.is_required():
                continue
            with self.subTest(setting=name):
                actual = interpolation_default(compose_environment()[name])
                expected = field.get_default(call_default_factory=True)
                if name == "INITIAL_EXTENSIONS":
                    self.assertEqual(tuple(json.loads(actual)), expected)
                else:
                    self.assertEqual(Path(actual), expected)

    def test_env_example_documents_every_application_setting(self):
        env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
        for name in Settings.model_fields:
            with self.subTest(setting=name):
                self.assertIn(name, env_example)


if __name__ == "__main__":
    unittest.main()
