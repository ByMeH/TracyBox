import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import main


def test_resource_path_runs_from_source():
    assert main.resource_path("assets/tracebox.svg") == (
        Path(main.__file__).resolve().parent / "assets" / "tracebox.svg"
    )


def test_resource_path_uses_meipass_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/kilo/bundle", raising=False)
    assert main.resource_path("assets/tracebox.svg") == (
        Path("/tmp/kilo/bundle") / "assets" / "tracebox.svg"
    )


def test_tracebox_svg_is_valid_svg():
    root = ElementTree.parse(main.resource_path("assets/tracebox.svg")).getroot()
    assert root.tag.endswith("svg")
