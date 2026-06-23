"""Interactive SVG fishbone (Ishikawa) renderer for the Streamlit UI.

Builds a self-contained HTML/SVG string (no external assets) suitable for
``streamlit.components.v1.html()``. The diagram is generated from the scored
fishbone table so it stays in sync with the evidence:

  * one bone per 6M category, heat-colored by its summed evidence score;
  * one twig per subcategory (from the canonical schema), highlighted when it
    has supporting evidence;
  * native hover tooltips and a click-to-inspect side panel that lists each
    candidate cause's score and **source record IDs**.

Interactivity lives entirely inside the sandboxed iframe (hover + JS panel);
nothing is posted back to Python.
"""

from __future__ import annotations

import json

import pandas as pd

from rca_copilot.fishbone import FISHBONE

# --- canvas geometry --------------------------------------------------------
_W, _H = 1180, 560
_SPINE_Y = 280
_SPINE_X0, _SPINE_X1 = 120, 900
_TOP_EX = [150, 380, 610]
_BOT_EX = [150, 380, 610]
_ATTACH = [310, 540, 770]
_EY_TOP, _EY_BOT = 80, 480
_BOX_W, _BOX_H = 168, 34
_TWIG_LEN = 64
_TWIG_T = [0.30, 0.50, 0.70, 0.86]


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    a = tuple(int(c1[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i : i + 2], 16) for i in (1, 3, 5))
    r = tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))
    return "#%02x%02x%02x" % r


def _cat_color(score: float, max_score: float) -> tuple[str, str]:
    """Return (fill, text) colors for a category box, heat-scaled by score."""
    if max_score <= 0 or score <= 0:
        return "#eef2f7", "#33414f"
    ratio = score / max_score
    fill = _lerp_hex("#fce8e6", "#c0392b", ratio)
    text = "#ffffff" if ratio > 0.55 else "#33414f"
    return fill, text


def _build_data(fb_scores: pd.DataFrame) -> list[dict]:
    """Per-category structure with subcategory evidence, in schema order."""
    lookup: dict[tuple[str, str], dict] = {}
    for r in fb_scores.itertuples():
        lookup[(r.category, r.subcategory)] = {
            "score": float(r.score),
            "count": int(r.evidence_count),
            "sources": r.source_ids,
            "priority": r.priority,
        }

    cats: list[dict] = []
    for cat, subs in FISHBONE.items():
        sub_rows = []
        for sub in subs:
            hit = lookup.get((cat, sub))
            sub_rows.append(
                {
                    "name": sub,
                    "score": round(hit["score"], 2) if hit else 0.0,
                    "count": hit["count"] if hit else 0,
                    "sources": hit["sources"] if hit else "",
                    "priority": hit["priority"] if hit else "—",
                }
            )
        cats.append(
            {
                "name": cat,
                "score": round(sum(s["score"] for s in sub_rows), 2),
                "count": sum(s["count"] for s in sub_rows),
                "subs": sub_rows,
            }
        )
    return cats


def _esc(s: str) -> str:
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def fishbone_svg_html(fb_scores: pd.DataFrame, effect_label: str) -> str:
    """Render the interactive fishbone as an HTML string."""
    cats = _build_data(fb_scores)
    max_score = max((c["score"] for c in cats), default=0.0)

    # Assign the 6 categories to bone slots: 3 above the spine, 3 below.
    slots = []
    for i, cat in enumerate(cats[:6]):
        top = i < 3
        col = i % 3
        attach = _ATTACH[col]
        ex = (_TOP_EX if top else _BOT_EX)[col]
        ey = _EY_TOP if top else _EY_BOT
        slots.append((cat, attach, ex, ey, top))

    el: list[str] = []
    # spine + arrow + effect (head) box
    el.append(
        f'<line x1="{_SPINE_X0}" y1="{_SPINE_Y}" x2="{_SPINE_X1}" y2="{_SPINE_Y}" '
        f'stroke="#34495e" stroke-width="4"/>'
    )
    el.append(
        f'<polygon points="{_SPINE_X1},{_SPINE_Y-9} {_SPINE_X1+18},{_SPINE_Y} '
        f'{_SPINE_X1},{_SPINE_Y+9}" fill="#34495e"/>'
    )
    el.append(
        f'<rect x="905" y="232" width="245" height="96" rx="8" fill="#2c3e50"/>'
    )
    el.append(
        f'<text x="1027" y="268" text-anchor="middle" fill="#9fb3c8" '
        f'font-size="12">Effect (signal)</text>'
    )
    el.append(
        f'<text x="1027" y="292" text-anchor="middle" fill="#ffffff" '
        f'font-size="13" font-weight="600">{_esc(effect_label)}</text>'
    )

    for idx, (cat, attach, ex, ey, top) in enumerate(slots):
        fill, tcolor = _cat_color(cat["score"], max_score)
        g = [f'<g class="cat" id="cat{idx}" onclick="show({idx})">']
        # bone
        g.append(
            f'<line x1="{attach}" y1="{_SPINE_Y}" x2="{ex}" y2="{ey}" '
            f'stroke="#5b6b7a" stroke-width="3"/>'
        )
        # subcategory twigs
        for j, sub in enumerate(cat["subs"][:4]):
            t = _TWIG_T[j]
            px = attach + t * (ex - attach)
            py = _SPINE_Y + t * (ey - _SPINE_Y)
            tx = px - _TWIG_LEN
            has_ev = sub["score"] > 0
            line_color = "#c0392b" if has_ev else "#9aa7b4"
            txt_color = "#b03a2e" if has_ev else "#7a8896"
            weight = "600" if has_ev else "400"
            tip = (
                f'{sub["name"]} — score {sub["score"]:.2f}, {sub["count"]} record(s)'
                + (f' [{sub["sources"]}]' if sub["sources"] else " — no evidence")
            )
            g.append(
                f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{tx:.1f}" y2="{py:.1f}" '
                f'stroke="{line_color}" stroke-width="2"/>'
            )
            g.append(
                f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.2" fill="{line_color}"/>'
            )
            g.append(
                f'<text x="{tx-5:.1f}" y="{py+3.5:.1f}" text-anchor="end" '
                f'font-size="10.5" fill="{txt_color}" font-weight="{weight}">'
                f'{_esc(sub["name"])}<title>{_esc(tip)}</title></text>'
            )
        # category label box
        g.append(
            f'<rect class="box" x="{ex-_BOX_W/2:.0f}" y="{ey-_BOX_H/2:.0f}" '
            f'width="{_BOX_W}" height="{_BOX_H}" rx="6" fill="{fill}" '
            f'stroke="#2c3e50" stroke-width="1.5"/>'
        )
        g.append(
            f'<text x="{ex}" y="{ey+4:.0f}" text-anchor="middle" font-size="11.5" '
            f'font-weight="600" fill="{tcolor}">{_esc(cat["name"])}'
            f'<title>{_esc(cat["name"])} — total score {cat["score"]:.2f}, '
            f'{cat["count"]} record(s). Click to inspect.</title></text>'
        )
        g.append("</g>")
        el.append("".join(g))

    svg = (
        f'<svg viewBox="0 0 {_W} {_H}" width="100%" '
        f'style="max-height:520px" xmlns="http://www.w3.org/2000/svg">'
        + "".join(el)
        + "</svg>"
    )

    data_json = json.dumps(cats)
    # default panel = highest-scoring category
    default_idx = max(range(len(cats)), key=lambda i: cats[i]["score"]) if cats else 0

    style = """
    <style>
      .fb-wrap{font-family:-apple-system,Segoe UI,Roboto,sans-serif;display:flex;
        gap:16px;align-items:flex-start;color:#33414f}
      .fb-diagram{flex:3;min-width:0}
      .fb-panel{flex:1;min-width:230px;max-width:320px;background:#f7f9fc;
        border:1px solid #e0e6ee;border-radius:10px;padding:14px 16px;font-size:13px}
      .fb-panel h4{margin:0 0 4px;font-size:15px}
      .fb-panel .meta{color:#6b7a89;font-size:12px;margin-bottom:10px}
      .fb-sub{padding:8px 0;border-top:1px solid #e8edf3}
      .fb-sub .n{font-weight:600}
      .fb-sub .s{color:#b03a2e;font-weight:600}
      .fb-sub .src{color:#5b6b7a;font-size:11.5px;word-break:break-word}
      .fb-sub.none .n{color:#9aa7b4;font-weight:400}
      g.cat{cursor:pointer}
      g.cat:hover .box{stroke-width:3}
      g.cat.sel .box{stroke:#c0392b;stroke-width:3.5}
      .fb-hint{color:#8a97a5;font-size:11.5px;margin-top:6px}
    </style>
    """

    script = """
    <script>
      const DATA = __DATA__;
      function show(i){
        const d = DATA[i];
        document.querySelectorAll('g.cat').forEach(g=>g.classList.remove('sel'));
        const sel = document.getElementById('cat'+i); if(sel) sel.classList.add('sel');
        const subs = d.subs.slice().sort((a,b)=>b.score-a.score);
        let html = '<h4>'+d.name+'</h4>'
          + '<div class="meta">Priority score '+d.score.toFixed(2)+' · '+d.count+' record(s)</div>';
        subs.forEach(s=>{
          if(s.score>0){
            html += '<div class="fb-sub"><div><span class="n">'+s.name+'</span>'
              + ' <span class="s">'+s.score.toFixed(2)+'</span> ('+s.priority+')</div>'
              + '<div class="src">Sources: '+s.sources+'</div></div>';
          } else {
            html += '<div class="fb-sub none"><span class="n">'+s.name+'</span>'
              + ' <span style="color:#9aa7b4">no evidence</span></div>';
          }
        });
        document.getElementById('fb-panel').innerHTML = html;
      }
      show(__DEFAULT__);
    </script>
    """

    body = (
        '<div class="fb-wrap">'
        f'<div class="fb-diagram">{svg}'
        '<div class="fb-hint">Hover a twig for source IDs · click a category to inspect.</div>'
        "</div>"
        '<div id="fb-panel" class="fb-panel"></div>'
        "</div>"
    )

    return (
        style
        + body
        + script.replace("__DATA__", data_json).replace("__DEFAULT__", str(default_idx))
    )
