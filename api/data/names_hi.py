"""Every seeded name and tag in Devanagari, as Sarvam's transliterate writes it.

The seed must rebuild identically with the wifi off, so the forms are fetched
once and committed in names_hi.json. `make names-hi` fetches any that are
missing (it needs SARVAM_API_KEY) and leaves the rest alone.

Transliterate reads a few Marathi surnames as English words (Jadhav as जड़, More
as मोर), and "Chawl" as चावल (rice). Those are corrected below, by hand, so the
file stays exactly what Sarvam returned and every correction is visible here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

FILE = Path(__file__).resolve().parent / "names_hi.json"

#: Checked by hand: what a Hindi speaker writes, where transliterate was wrong.
FIXES = {
    "Chavan": "चव्हाण",
    **{f"Chawl {n}": f"चॉल {n}" for n in range(1, 7)},
    "Jadhav": "जाधव",
    "Kamat": "कामत",
    "Mhatre": "म्हात्रे",
    "More": "मोरे",
    "Nikhil": "निखिल",
    "Rahul": "राहुल",
}


def fetched() -> dict[str, str]:
    """names_hi.json: what Sarvam's transliterate returned, untouched."""
    if not FILE.exists():
        return {}
    data = json.loads(FILE.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return {str(k): str(v) for k, v in data.items()}


def load() -> dict[str, str]:
    return fetched() | FIXES


def main() -> int:
    from bahi.voice import api_key, sarvam
    from data.generate import plan

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    key = api_key()
    if key is None:
        sys.exit("needs SARVAM_API_KEY in api/.env")
    rows = plan().customers
    names = sorted({c.display_name for c in rows} | {c.tag for c in rows if c.tag})
    known = fetched()
    for name in names:
        if name not in known:
            known[name] = sarvam.transliterate(name, key=key)
            print(f"{name:20} {known[name]}")
    body = json.dumps(dict(sorted(known.items())), ensure_ascii=False, indent=1)
    FILE.write_text(body + "\n", encoding="utf-8")
    print(f"{len(names)} names, {FILE.name} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
