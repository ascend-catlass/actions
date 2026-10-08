import contextlib
import importlib.util
import io
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "select_device",
    Path(__file__).resolve().parents[1] / ".github/actions/prepare-ci-tests/select-device.py",
)
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)

MAPPING = """NPU ID  Chip ID  Chip Logic ID  Chip Name
4       0        1              Ascend 910B3
4       1        -              Mcu
7       0        2              Ascend 910B3
"""
INFO = """| NPU Chip | Process id | Process name | Process memory(MB) |
| 4 0 | 101 | python | 100 |
| 4 0 | 101 | python | 100 |
| No running processes found in NPU 7 |
"""


class SelectDeviceTest(unittest.TestCase):
    def select(self, mapping=MAPPING, info=INFO, visible=None):
        with contextlib.redirect_stderr(io.StringIO()):
            return selector.select_device(mapping, info, visible)

    def test_selects_idle_card_using_logical_not_physical_id(self):
        self.assertEqual(self.select(), 2)
        devices = selector.device_mapping(MAPPING)
        self.assertEqual(selector.process_counts(INFO, devices)[(4, 0)], 1)

    def test_950_missing_logic_id_and_tie(self):
        mapping = "NPU ID  Chip ID  Chip Name\n3 0 Ascend 950\n1 0 Ascend 950\n"
        info = "| NPU Chip | Process id | Process name |\n"
        info += "| No running processes found in NPU 3 |\n| No running processes found in NPU 1 |"
        self.assertEqual(self.select(mapping, info), 1)

    def test_visibility_renumbers_runtime_index_and_ignores_hidden_card(self):
        info = "| NPU Chip | Process id | Process name |\n| No running processes found in NPU 7 |"
        self.assertEqual(self.select(info=info, visible="2"), 0)

    def test_selects_fewest_processes_when_every_card_is_busy(self):
        info = "| NPU Chip | Process id | Process name |\n"
        info += "| 4 0 | 101 | python |\n| 7 0 | 201 | python |\n| 7 0 | 202 | python |"
        self.assertEqual(self.select(info=info), 1)

    def test_unknown_or_incomplete_output_fails(self):
        for info in ("driver error", "| NPU Chip | Process id | Process name |\n| 4 0 | 101 | python |"):
            with self.subTest(info=info), self.assertRaises(ValueError):
                self.select(info=info)
        with self.assertRaises(ValueError):
            self.select(mapping="NPU ID Chip ID Chip Name\n4 0 Ascend 910B3\n")


if __name__ == "__main__":
    unittest.main()
