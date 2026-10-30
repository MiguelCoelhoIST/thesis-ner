import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from src.data import extract_role_candidates_v2 as extractor


class NERDeviceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.model_path = Path(self.directory.name)
        (self.model_path / "config.cfg").write_text("# synthetic model configuration\n", encoding="utf-8")
        self.nlp = SimpleNamespace(
            meta={}, pipe_names=["transformer", "ner"],
            get_pipe=lambda name: SimpleNamespace(labels=("PER", "ORG")),
        )
        self.spacy = SimpleNamespace(
            __version__="test", require_cpu=Mock(), require_gpu=Mock(),
            load=Mock(return_value=self.nlp),
        )
        self.torch = SimpleNamespace(
            set_num_threads=Mock(), get_num_threads=lambda: 4,
            get_num_interop_threads=lambda: 4,
        )
        self.calls = Mock()
        for name in ("require_cpu", "require_gpu", "load"):
            self.calls.attach_mock(getattr(self.spacy, name), name)

    def load(self, **kwargs):
        output = io.StringIO()
        with (
            patch.dict(sys.modules, {"spacy": self.spacy, "torch": self.torch}),
            contextlib.redirect_stdout(output),
        ):
            model = extractor.load_person_ner(self.model_path, **kwargs)
        self.assertIs(model, self.nlp)
        return output.getvalue()

    def test_default_selects_cpu_before_loading(self):
        self.assertIn("NER device: CPU", self.load())
        self.assertEqual(self.calls.mock_calls, [call.require_cpu(), call.load(self.model_path)])
        self.spacy.require_gpu.assert_not_called()

    def test_gpu_is_required_before_loading(self):
        self.assertIn("NER device: GPU 1", self.load(gpu_id=1))
        self.assertEqual(self.calls.mock_calls, [call.require_gpu(1), call.load(self.model_path)])
        self.spacy.require_cpu.assert_not_called()

    def test_unavailable_gpu_fails_without_loading_or_cpu_fallback(self):
        self.spacy.require_gpu.side_effect = ValueError("No CUDA device")
        with self.assertRaisesRegex(ValueError, "Requested GPU 0 is unavailable"):
            self.load(gpu_id=0)
        self.spacy.load.assert_not_called()
        self.spacy.require_cpu.assert_not_called()

    def test_cli_passes_optional_gpu_id_to_loader(self):
        for arguments, gpu_id in (([], None), (["--gpu-id", "0"], 0)):
            with (
                self.subTest(gpu_id=gpu_id),
                patch.object(sys, "argv", ["extractor", "--input-dir", str(self.model_path), "--audit-only", *arguments]),
                patch.object(extractor, "load_person_ner", side_effect=ValueError("stop after device dispatch")) as loader,
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    extractor.main()
                loader.assert_called_once_with(extractor.DEFAULT_NER_MODEL, cpu_threads=4, gpu_id=gpu_id)


if __name__ == "__main__":
    unittest.main()
