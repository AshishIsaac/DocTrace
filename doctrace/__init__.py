"""Local RAG search over your own files."""
import os
import sys

if sys.version_info < (3, 10):  # noqa: UP036 - friendly message on old Pythons
    sys.exit("DocTrace needs Python 3.10 or newer (you have %d.%d)." % sys.version_info[:2])  # noqa: UP031

# Quiet the noisy-but-harmless warnings from the ML stack.
for _key, _value in {
    "TOKENIZERS_PARALLELISM": "false",
    "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_DISABLE_PROGRESS_BARS": "1",
    "TRANSFORMERS_VERBOSITY": "error",
    "TRANSFORMERS_NO_ADVISORY_WARNINGS": "1",
    "GRADIO_ANALYTICS_ENABLED": "False",
}.items():
    os.environ.setdefault(_key, _value)
