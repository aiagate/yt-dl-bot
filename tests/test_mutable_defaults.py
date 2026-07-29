import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "src" / "yt_dl_bot"


class MutableDefaultsTest(unittest.TestCase):
    def test_source_functions_have_no_mutable_literal_defaults(self):
        violations = []
        for path in SOURCE_PATH.rglob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    continue
                defaults = [*node.args.defaults]
                defaults.extend(default for default in node.args.kw_defaults if default is not None)
                if any(isinstance(default, (ast.Dict, ast.List, ast.Set)) for default in defaults):
                    violations.append(f"{path.name}:{node.lineno}")

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
