"""Tests for the SVG fishbone renderer."""

from rca_copilot.data.synthetic import load_dataset
from rca_copilot.fishbone import FISHBONE
from rca_copilot.scoring import score_fishbone
from rca_copilot.viz import fishbone_svg_html


def _html():
    return fishbone_svg_html(score_fishbone(load_dataset()), "Low harvest titer")


def test_renders_one_bone_per_category():
    html = _html()
    assert html.count('class="cat"') == len(FISHBONE)
    for cat in FISHBONE:
        assert cat in html


def test_top_candidate_sources_are_embedded():
    html = _html()
    # The headline media-lot evidence must be reachable in the diagram/panel.
    assert "CC-2025-014" in html
    assert "Cell culture media / feed lot" in html


def test_effect_label_and_self_contained():
    html = _html()
    assert "Low harvest titer" in html
    assert "<svg" in html and "</svg>" in html
    assert "function show" in html  # interactive panel script present
    assert "http" not in html.replace("http://www.w3.org/2000/svg", "")  # no external assets
