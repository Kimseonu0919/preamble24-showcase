"""README 배지 생성기 — 외부 배지 서비스(shields.io 등) 없이 저장소 안에서 SVG 를 만든다.

원 저장소의 「외부 서비스 없음」 경계를 쇼케이스에서도 지킨다. 실행하면 assets/readme/badge-*.svg 를 다시 쓴다.

    python scripts/gen_badges.py
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "readme"

# (파일 이름, 라벨, 값)
BADGES: list[tuple[str, str, str]] = [
    ("runtime", "runtime", "NautilusTrader 2.0"),
    ("python", "python", "3.12+"),
    ("venue", "venue", "Binance Futures"),
    ("platform", "platform", "Windows · Linux"),
    ("boundary", "boundary", "private · no external services"),
    ("ruff", "lint", "ruff"),
    ("pyright", "types", "basedpyright"),
    ("radon", "complexity", "radon"),
    ("vulture", "dead code", "vulture"),
    ("hypothesis", "property tests", "Hypothesis"),
    ("coverage", "coverage", "pytest-cov"),
    ("importlinter", "layers", "Import Linter"),
    ("precommit", "hooks", "pre-commit"),
    ("uv", "dependencies", "uv lock"),
    ("ci", "CI", "GitHub Actions"),
    ("madr", "decisions", "MADR template"),
    ("adr", "ADR", "append-only"),
    ("pymarkdown", "markdown", "PyMarkdown"),
    ("mkdocs", "docs site", "MkDocs · local"),
    ("ratchet", "baselines", "ratchet · only tighten"),
]

FONT = "Verdana, 'DejaVu Sans', 'Segoe UI', Arial, sans-serif"
CHAR_W = 7.0  # Verdana 11px 평균 글자 폭 근사
PAD = 10
H = 24


def _w(text: str) -> int:
    return int(len(text) * CHAR_W + 2 * PAD)


def badge(label: str, value: str) -> str:
    lw, vw = _w(label), _w(value) + 4
    w = lw + vw
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{H}" viewBox="0 0 {w} {H}" '
        f'role="img" aria-label="{label}: {value}">\n'
        f'  <rect x="0.5" y="0.5" width="{w - 1}" height="{H - 1}" rx="3" fill="#1E2329" stroke="#B58A05"/>\n'
        f'  <rect x="{lw}" y="0.5" width="{vw - 0.5}" height="{H - 1}" rx="0" fill="#F0B90B"/>\n'
        f'  <text x="{lw / 2}" y="16" text-anchor="middle" font-family="{FONT}" font-size="11" fill="#EAECEF">{label}</text>\n'
        f'  <text x="{lw + vw / 2}" y="16" text-anchor="middle" font-family="{FONT}" font-size="11" '
        f'font-weight="700" fill="#0B0E11">{value}</text>\n'
        f"</svg>\n"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, label, value in BADGES:
        (OUT / f"badge-{name}.svg").write_text(badge(label, value), encoding="utf-8", newline="\n")
    print(f"{len(BADGES)} badges -> {OUT}")


if __name__ == "__main__":
    main()
