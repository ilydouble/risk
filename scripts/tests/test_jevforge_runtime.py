"""Decision adapter reloads must retain nonpersistent numerical buffer values and dtype."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import torch

SPEC = importlib.util.spec_from_file_location(
    "jevforge_runtime", Path(__file__).parents[1] / "jevforge_runtime.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class BufferedModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.ones(2, dtype=torch.bfloat16))
        self.register_buffer("frequencies", torch.tensor([0.123456, 0.987654]), persistent=False)


class RuntimeContracts(unittest.TestCase):
    def test_adapter_roundtrip_preserves_nonpersistent_buffer_precision(self):
        trained = BufferedModel().bfloat16()
        self.assertNotIn("frequencies", trained.state_dict())
        fresh = BufferedModel()
        self.assertFalse(torch.equal(trained.frequencies.float(), fresh.frequencies))
        with tempfile.TemporaryDirectory() as directory:
            module.save_runtime_buffers(trained, directory)
            module.restore_runtime_buffers(fresh, directory)
        self.assertEqual(fresh.frequencies.dtype, torch.bfloat16)
        torch.testing.assert_close(fresh.frequencies, trained.frequencies, rtol=0, atol=0)

    def test_precision_probe_can_restore_original_buffer_dtype_and_values(self):
        model = BufferedModel()
        original = {name: value.clone() for name, value in model.named_buffers()}
        model.bfloat16()
        module.restore_buffers(model, original)
        self.assertEqual(model.frequencies.dtype, torch.float32)
        torch.testing.assert_close(model.frequencies, original["frequencies"], rtol=0, atol=0)

    def test_incomplete_buffer_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / module.RUNTIME_FILE).write_text('{"version":1,"buffers":{}}')
            with self.assertRaisesRegex(ValueError, "every model buffer"):
                module.restore_runtime_buffers(BufferedModel(), directory)


if __name__ == "__main__":
    unittest.main()
