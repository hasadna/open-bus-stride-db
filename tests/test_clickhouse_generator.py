import runpy
import unittest
from contextlib import contextmanager
from unittest.mock import patch

generator = runpy.run_path("bin/generate_clickhouse_models.py")


class GeneratorNameTests(unittest.TestCase):
    def test_missing_existing_objects_prevent_write(self):
        row = {"table": "present", "name": "id", "type": "String", "is_in_primary_key": 1}

        class Result:
            def mappings(self):
                return self

            def all(self):
                return [row]

        class Session:
            def execute(self, *args):
                return Result()

        @contextmanager
        def session():
            yield Session()

        existing = "class Old(Base):\n    __tablename__ = 'old'\nview = Table('view', Base.metadata)\n"
        generate = generator["generate"]
        with patch.dict(generate.__globals__, {"get_session": session}):
            with patch("pathlib.Path.exists", return_value=True), patch(
                "pathlib.Path.read_text", return_value=existing
            ), patch("pathlib.Path.write_text") as write:
                with self.assertRaisesRegex(ValueError, "old, view"):
                    generate()
                write.assert_not_called()

    def test_invalid_names_are_rejected_before_writing(self):
        for table, column in [
            ("from", "id"),
            ("example", "class"),
            ("example", "metadata"),
        ]:
            with self.subTest(table=table, column=column):
                row = {
                    "table": table,
                    "name": column,
                    "type": "String",
                    "is_in_primary_key": 1,
                }

                class Result:
                    def mappings(self):
                        return self

                    def all(self):
                        return [row]

                class Session:
                    def execute(self, *args):
                        return Result()

                @contextmanager
                def session():
                    yield Session()

                generate = generator["generate"]
                with patch.dict(generate.__globals__, {"get_session": session}):
                    with patch("pathlib.Path.write_text") as write:
                        with self.assertRaisesRegex(ValueError, "Unsupported"):
                            generate()
                        write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
