from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_ROOT / "assets"

STROKE = "#1f2933"
ACCENT = "#64748b"

LINE = (
    f'stroke="{STROKE}" '
    'stroke-width="1.8" '
    'fill="none" '
    'stroke-linecap="round" '
    'stroke-linejoin="round"'
)

THIN = (
    f'stroke="{STROKE}" '
    'stroke-width="1.5" '
    'fill="none" '
    'stroke-linecap="round" '
    'stroke-linejoin="round"'
)

FILL_ACCENT = f'fill="{ACCENT}"'


def svg(inner: str) -> str:
    return f'''<svg width="32" height="32" viewBox="0 0 32 32"
    xmlns="http://www.w3.org/2000/svg">
{inner}
</svg>
'''


def document(inner: str = "") -> str:
    return f'''
  <path d="M9 4h10l5 5v19H9z" {LINE}/>
  <path d="M19 4v5h5" {LINE}/>
{inner}
'''


icons = {
    "folder": svg(f'''
  <path d="M4 10V8a3 3 0 0 1 3-3h6l3 4h9a3 3 0 0 1 3 3v13a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z" {LINE}/>
  <path d="M4 12h24" {LINE}/>
'''),

    "file": svg(document()),

    "pdf": svg(document(f'''
  <path d="M12 22c2.5-3.5 4.5-9.5 3-10.5-1.8-1.2-2 4.8 1.2 8.2 2.5 2.6 5.9 2.7 6.1.8.2-1.9-4.7-1.4-10.3 1.5z" {LINE}/>
''')),

    "doc": svg(document(f'''
  <path d="M13 14h7" {LINE}/>
  <path d="M13 18h7" {LINE}/>
  <path d="M13 22h5" {LINE}/>
''')),

    "sheet": svg(document(f'''
  <rect x="12" y="13" width="10" height="10" rx="1" {LINE}/>
  <path d="M12 16.3h10" {THIN}/>
  <path d="M12 19.6h10" {THIN}/>
  <path d="M15.3 13v10" {THIN}/>
  <path d="M18.6 13v10" {THIN}/>
''')),

    "slide": svg(document(f'''
  <rect x="12" y="13" width="9" height="6" rx="1" {LINE}/>
  <path d="M12 22h9" {LINE}/>
  <path d="M12 25h6" {LINE}/>
''')),

    "image": svg(f'''
  <rect x="6" y="7" width="20" height="18" rx="3" {LINE}/>
  <path d="M9 21l5-5 4 4 3-3 5 5" {LINE}/>
  <circle cx="22" cy="12" r="1.7" {LINE}/>
'''),

    "video": svg(f'''
  <rect x="7" y="8" width="18" height="16" rx="2" {LINE}/>
  <path d="M14 13l7 3-7 3z" {LINE}/>
  <path d="M7 12h3" {THIN}/>
  <path d="M7 16h3" {THIN}/>
  <path d="M7 20h3" {THIN}/>
  <path d="M22 12h3" {THIN}/>
  <path d="M22 16h3" {THIN}/>
  <path d="M22 20h3" {THIN}/>
'''),

    "audio": svg(f'''
  <path d="M6 19h4l6 5V8l-6 5H6z" {LINE}/>
  <path d="M20 13c1.2 1.6 1.2 4.4 0 6" {LINE}/>
  <path d="M23 10c2.6 3.6 2.6 8.4 0 12" {LINE}/>
'''),

    "archive": svg(f'''
  <path d="M7 9l3-4h12l3 4v16a3 3 0 0 1-3 3H10a3 3 0 0 1-3-3z" {LINE}/>
  <path d="M7 9h18" {LINE}/>
  <path d="M16 5v17" {THIN}/>
  <path d="M16 8h2" {THIN}/>
  <path d="M16 11h-2" {THIN}/>
  <path d="M16 14h2" {THIN}/>
  <path d="M16 17h-2" {THIN}/>
  <rect x="14" y="22" width="4" height="4" rx="1" {LINE}/>
'''),

    "code": svg(document(f'''
  <path d="M14 15l-3 3 3 3" {LINE}/>
  <path d="M18 15l3 3-3 3" {LINE}/>
  <path d="M17 14l-2 8" {LINE}/>
''')),

    "data": svg(f'''
  <path d="M7 25V15" {LINE}/>
  <path d="M13 25V11" {LINE}/>
  <path d="M19 25V17" {LINE}/>
  <path d="M25 25V8" {LINE}/>
  <path d="M7 14l6-4 6 5 6-8" {LINE}/>
  <circle cx="7" cy="14" r="1.5" {LINE}/>
  <circle cx="13" cy="10" r="1.5" {LINE}/>
  <circle cx="19" cy="15" r="1.5" {LINE}/>
  <circle cx="25" cy="7" r="1.5" {LINE}/>
'''),

    "design": svg(f'''
  <path d="M16 8c5 0 6-3 9-3" {LINE}/>
  <path d="M16 8c-5 0-6-3-9-3" {LINE}/>
  <circle cx="7" cy="5" r="1.5" {LINE}/>
  <circle cx="25" cy="5" r="1.5" {LINE}/>
  <rect x="14.5" y="6.5" width="3" height="3" rx="0.5" {LINE}/>
  <path d="M16 10l5 9-5 6-5-6z" {LINE}/>
  <path d="M16 10v9" {LINE}/>
  <circle cx="16" cy="19" r="1.2" {LINE}/>
  <path d="M12 27h8" {LINE}/>
'''),

    "db": svg(f'''
  <ellipse cx="16" cy="8" rx="9" ry="4" {LINE}/>
  <path d="M7 8v14c0 2.2 4 4 9 4s9-1.8 9-4V8" {LINE}/>
  <path d="M7 15c0 2.2 4 4 9 4s9-1.8 9-4" {LINE}/>
  <path d="M7 22c0 2.2 4 4 9 4s9-1.8 9-4" {LINE}/>
  <circle cx="22" cy="14" r="0.8" {FILL_ACCENT}/>
  <circle cx="22" cy="21" r="0.8" {FILL_ACCENT}/>
'''),

    "app": svg(f'''
  <rect x="6" y="6" width="20" height="20" rx="3" {LINE}/>
  <path d="M6 11h20" {LINE}/>
  <circle cx="10" cy="8.5" r="0.8" {FILL_ACCENT}/>
  <circle cx="13" cy="8.5" r="0.8" {FILL_ACCENT}/>
  <circle cx="16" cy="8.5" r="0.8" {FILL_ACCENT}/>
  <rect x="10" y="14" width="5" height="5" rx="1" {LINE}/>
  <rect x="18" y="14" width="5" height="5" rx="1" {LINE}/>
  <rect x="10" y="21" width="5" height="5" rx="1" {LINE}/>
  <rect x="18" y="21" width="5" height="5" rx="1" {LINE}/>
'''),

    "missing": svg(document(f'''
  <path d="M14 14a3 3 0 1 1 4.8 2.4c-1.5 1-2.2 1.8-2.2 3.1" {LINE}/>
  <path d="M16.6 24h.1" {LINE}/>
''')),

    "access_denied": svg(f'''
  <rect x="8" y="14" width="16" height="12" rx="2" {LINE}/>
  <path d="M11 14v-3a5 5 0 0 1 10 0v3" {LINE}/>
  <circle cx="22" cy="22" r="5" {LINE}/>
  <path d="M18.5 18.5l7 7" {LINE}/>
'''),
}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, content in icons.items():
        path = OUT_DIR / f"{name}.svg"
        path.write_text(content, encoding="utf-8")

    print(f"생성 완료: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
