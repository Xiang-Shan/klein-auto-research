"""Put the study dir on sys.path so tests can `import generator, estimators`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
