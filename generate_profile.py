#!/usr/bin/env python3
"""
Generates an animated terminal-style GitHub profile card (dark.svg + light.svg).

Everything you'd normally want to tweak lives in CONFIG / INFO / THEMES below.
Stats (repos, stars, followers) are pulled live from the GitHub API when the
script runs in Actions; if the API is unreachable it silently falls back.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from pathlib import Path
from typing import Final, NamedTuple, TypedDict

LOGGER = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
USERNAME: Final = "notLeri"
PORTRAIT_FILE: Final = "portrait.txt"
GITHUB_API: Final = "https://api.github.com"
REQUEST_TIMEOUT_S: Final = 15
MAX_REPO_PAGES: Final = 5

# markers that select a special row layout instead of a plain key/value line
HEADER: Final = "__header__"
RULE: Final = "__rule__"
BLANK: Final = "__blank__"
SECTION: Final = "__section__"
STATS: Final = "__stats__"


class InfoRow(NamedTuple):
    label: str
    value: str = ""
    color_key: str = ""  # "" (default val colour) / accent / warn / muted


INFO: Final[list[InfoRow]] = [
    InfoRow(HEADER, "Stanislav Akimov"),
    InfoRow(RULE),
    InfoRow("Role", "Senior Backend Developer @ Oddin.gg"),
    InfoRow("Edu", "B.Tech IT, NSU  ·  Class of 2019"),
    InfoRow("Focus", "Backend Engineering  ·  Highload, Microservices", "accent"),
    InfoRow(BLANK),
    InfoRow(SECTION, "~/stack"),
    InfoRow("Lang", "Golang · Python · JavaScript · SQL"),
    InfoRow("Backend", "gRPC · GraphQL · REST · FastAPI · Flask · Node.js"),
    InfoRow("AI", "LLMs · RAG · LangChain · CrewAI · Vector DBs"),
    InfoRow("Infra", "AWS Lambda · GCP · Kubernetes · Kafka · Prometheus"),
    InfoRow("Data", "PostgreSQL · DynamoDB · MongoDB · Redis · BigQuery"),
    InfoRow(BLANK),
    InfoRow(SECTION, "~/projects"),
    InfoRow("Oddin.gg", "24/7 real-time esports betting platform", "warn"),
    InfoRow("", "LLM integration, Odds engine, Risk service", "muted"),
    InfoRow("Xiatech", "Event-driven data platform (Xfuze)", "warn"),
    InfoRow("", "AWS infra, Data pipelines, SQS/SNS queues, Analytics", "muted"),
    InfoRow("LHM.gg", "HUD for cybersport live stream", "warn"),
    InfoRow("", "Self managing project, Custom “turnkey” implementation", "muted"),
    InfoRow(BLANK),
    InfoRow(STATS),
    InfoRow(BLANK),
    InfoRow(SECTION, "~/reach"),
    InfoRow("In", "https://www.linkedin.com/in/stanislav-aki/", "accent"),
]


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    bg: str
    panel: str
    border: str
    text: str
    muted: str
    key: str
    accent: str
    warn: str
    art: str
    prompt: str
    dot1: str
    dot2: str
    dot3: str


THEMES: Final[tuple[Theme, ...]] = (
    Theme(
        name="dark",
        bg="#0d1117",
        panel="#161b22",
        border="#30363d",
        text="#c9d1d9",
        muted="#8b949e",
        key="#3fb950",
        accent="#58a6ff",
        warn="#d29922",
        art="#bc8cff",
        prompt="#3fb950",
        dot1="#ff5f56",
        dot2="#ffbd2e",
        dot3="#27c93f",
    ),
    Theme(
        name="light",
        bg="#ffffff",
        panel="#f6f8fa",
        border="#d0d7de",
        text="#1f2328",
        muted="#59636e",
        key="#1a7f37",
        accent="#0969da",
        warn="#9a6700",
        art="#8250df",
        prompt="#1a7f37",
        dot1="#ff5f56",
        dot2="#ffbd2e",
        dot3="#27c93f",
    ),
)

W, H = 980, 620
ART_X, ART_Y = 30, 86
ART_CW = 3.9  # forced char width (textLength keeps this exact in any font)
ART_LH = ART_CW * 1.72
INFO_X, INFO_Y, INFO_LH = 448, 92, 17.5
VAL_X = INFO_X + 92

_COLOR_CLASS: Final[dict[str, str]] = {"accent": "acc", "warn": "wrn", "muted": "mut"}


def load_portrait() -> list[str]:
    portrait_path = Path(__file__).parent / PORTRAIT_FILE
    if not portrait_path.exists():
        return ["[ portrait.txt missing ]"]
    return portrait_path.read_text(encoding="utf-8").rstrip("\n").split("\n")


# ----------------------------------------------------------------------------
# STATS
# ----------------------------------------------------------------------------
class Stats(TypedDict):
    repos: str
    stars: str
    followers: str


def _get_json(url: str, headers: dict[str, str]) -> object:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        return json.load(response)


def fetch_stats() -> Stats:
    """Pull public repo/star/follower counts from the GitHub API.

    Falls back to placeholder dashes when offline or rate-limited, so the
    card still renders in local/dev runs without a GITHUB_TOKEN.
    """
    stats: Stats = {"repos": "-", "stars": "-", "followers": "-"}
    headers = {"User-Agent": "profile-readme"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        user = _get_json(f"{GITHUB_API}/users/{USERNAME}", headers)
        assert isinstance(user, dict)
        stats["repos"] = str(user.get("public_repos", 0))
        stats["followers"] = str(user.get("followers", 0))

        stars = 0
        for page in range(1, MAX_REPO_PAGES + 1):
            repos = _get_json(
                f"{GITHUB_API}/users/{USERNAME}/repos?per_page=100&page={page}", headers
            )
            assert isinstance(repos, list)
            if not repos:
                break
            stars += sum(repo.get("stargazers_count", 0) for repo in repos)
        stats["stars"] = str(stars)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, AssertionError) as exc:
        LOGGER.warning("stats fetch failed, using placeholders: %s", exc)

    return stats


# ----------------------------------------------------------------------------
# RENDER
# ----------------------------------------------------------------------------
def _render_style(theme: Theme) -> str:
    return f"""<style>
    .art  {{ fill:{theme.art}; font-size:6.2px; white-space:pre; }}
    .key  {{ fill:{theme.key}; font-size:13px; font-weight:700; }}
    .val  {{ fill:{theme.text}; font-size:13px; }}
    .acc  {{ fill:{theme.accent}; font-size:13px; }}
    .wrn  {{ fill:{theme.warn}; font-size:13px; }}
    .mut  {{ fill:{theme.muted}; font-size:12px; }}
    .hdr  {{ fill:{theme.accent}; font-size:15px; font-weight:700; }}
    .sec  {{ fill:{theme.muted}; font-size:12px; letter-spacing:1px; }}
    .ttl  {{ fill:{theme.muted}; font-size:12px; }}
    .row  {{ opacity:1; animation: fade .35s ease backwards; }}
    @keyframes fade {{ from {{ opacity:0; transform:translateY(3px); }}
                       to   {{ opacity:1; transform:translateY(0); }} }}
    .cur  {{ fill:{theme.prompt}; animation: blink 1s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity:0; }} }}
    .artline {{ opacity:1; animation: fade .3s ease backwards; }}
    </style>"""


def _render_window_chrome(theme: Theme) -> list[str]:
    parts = [
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="12" '
        f'fill="{theme.bg}" stroke="{theme.border}" stroke-width="1.5"/>',
        f'<path d="M1 13 a12 12 0 0 1 12 -12 h{W - 26} a12 12 0 0 1 12 12 v25 h{-(W - 2)} z" '
        f'fill="{theme.panel}"/>',
        f'<line x1="1" y1="38" x2="{W - 1}" y2="38" stroke="{theme.border}"/>',
    ]
    for i, dot in enumerate((theme.dot1, theme.dot2, theme.dot3)):
        parts.append(f'<circle cx="{24 + i * 20}" cy="20" r="6" fill="{dot}"/>')
    parts.append(
        f'<text x="{W / 2}" y="24" class="ttl" text-anchor="middle">'
        f"{escape(USERNAME)} — zsh — 90×26</text>"
    )
    return parts


def _render_ascii_art() -> list[str]:
    parts = []
    for i, line in enumerate(load_portrait()):
        if not line.strip():
            continue
        y = ART_Y + i * ART_LH
        delay = 0.15 + i * 0.012
        text_length = len(line) * ART_CW
        parts.append(
            f'<text x="{ART_X}" y="{y:.1f}" class="art artline" xml:space="preserve" '
            f'textLength="{text_length:.1f}" lengthAdjust="spacingAndGlyphs" '
            f'style="animation-delay:{delay:.2f}s">{escape(line)}</text>'
        )
    return parts


def _render_info_block(theme: Theme, stats: Stats) -> tuple[list[str], float]:
    parts: list[str] = []
    y = float(INFO_Y)
    delay = 0.35

    for row in INFO:
        style = f'style="animation-delay:{delay:.2f}s"'
        if row.label == HEADER:
            parts.append(
                f'<text x="{INFO_X}" y="{y:.1f}" class="hdr row" {style}>{escape(row.value)}</text>'
            )
            y += INFO_LH
        elif row.label == RULE:
            parts.append(
                f'<line x1="{INFO_X}" y1="{y - 8:.1f}" x2="{W - 40}" y2="{y - 8:.1f}" '
                f'stroke="{theme.border}" class="row" {style}/>'
            )
            y += 8
        elif row.label == BLANK:
            y += 10
            continue
        elif row.label == SECTION:
            parts.append(
                f'<text x="{INFO_X}" y="{y:.1f}" class="sec row" {style}>{escape(row.value)}</text>'
            )
            y += INFO_LH
        elif row.label == STATS:
            stat_text = (
                f'repos {stats["repos"]}   ·   stars {stats["stars"]}'
                f'   ·   followers {stats["followers"]}'
            )
            parts.append(
                f'<text x="{INFO_X}" y="{y:.1f}" class="row" {style}>'
                f'<tspan class="key">⚡</tspan>'
                f'<tspan class="val" dx="8">{escape(stat_text)}</tspan></text>'
            )
            y += INFO_LH
        else:
            css_class = _COLOR_CLASS.get(row.color_key, "val")
            if row.label:
                parts.append(
                    f'<text x="{INFO_X}" y="{y:.1f}" class="key row" {style}>{escape(row.label)}</text>'
                )
            parts.append(
                f'<text x="{VAL_X}" y="{y:.1f}" class="{css_class} row" {style}>{escape(row.value)}</text>'
            )
            y += INFO_LH
        delay += 0.07

    return parts, delay


def _render_footer(delay: float, updated_at: str) -> list[str]:
    footer_y = H - 24
    return [
        f'<text x="{ART_X}" y="{footer_y}" class="row" style="animation-delay:{delay + 0.1:.2f}s">'
        f'<tspan class="key">➜</tspan>'
        f'<tspan class="acc" dx="8">~</tspan>'
        f'<tspan class="val" dx="8">open to Software Engineer / Fullstack Engineer roles</tspan>'
        f'<tspan class="cur" dx="8">█</tspan></text>',
        f'<text x="{W - 34}" y="{footer_y}" class="mut" text-anchor="end">'
        f"last updated {updated_at}</text>",
    ]


def render(theme: Theme, stats: Stats, updated_at: str) -> str:
    info_parts, delay_after_info = _render_info_block(theme, stats)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="ui-monospace, SFMono-Regular, '
        f"'JetBrains Mono', 'Cascadia Code', Menlo, Consolas, monospace\">",
        _render_style(theme),
        *_render_window_chrome(theme),
        f'<text x="{ART_X}" y="66" class="row" style="animation-delay:.05s">'
        f'<tspan class="key">➜</tspan>'
        f'<tspan class="acc" dx="8">~</tspan>'
        f'<tspan class="val" dx="8">neofetch --profile</tspan></text>',
        *_render_ascii_art(),
        *info_parts,
        *_render_footer(delay_after_info, updated_at),
        "</svg>",
    ]
    return "\n".join(parts)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    stats = fetch_stats()
    ist_now = datetime.now(UTC) + timedelta(hours=5, minutes=30)
    timestamp = ist_now.strftime("%d %b %Y, %H:%M IST")

    out_dir = Path(__file__).parent
    for theme in THEMES:
        svg_path = out_dir / f"{theme.name}.svg"
        svg_path.write_text(render(theme, stats, timestamp), encoding="utf-8")
        LOGGER.info("wrote %s", svg_path.name)


if __name__ == "__main__":
    main()
