import argparse
import os
import sys
from typing import Optional, Tuple


FALLBACK_ENCODINGS = [
    "utf-8-sig",
    "utf-8",
    "cp949",  # Windows Korean (EUC-KR superset)
    "euc-kr",
    "iso2022_kr",
    "cp1252",
    "latin-1",
]


def detect_encoding(data: bytes) -> Tuple[str, str]:
    """Detect encoding best-effort. Returns (encoding, note)."""
    # Try chardet if available
    try:
        import chardet  # type: ignore

        guess = chardet.detect(data)
        enc = (guess.get("encoding") or "").lower()
        conf = guess.get("confidence") or 0.0
        if enc:
            # Normalize common names
            if enc in {"euc-kr", "euckr", "ks_c_5601-1987", "iso-2022-kr", "cp949"}:
                # Prefer cp949 which can decode most legacy Korean text on Windows
                return "cp949", f"chardet:{enc}:{conf:.2f}"
            if enc.startswith("utf"):
                return "utf-8", f"chardet:{enc}:{conf:.2f}"
            return enc, f"chardet:{enc}:{conf:.2f}"
    except Exception:
        pass

    # Manual fallbacks
    for enc in FALLBACK_ENCODINGS:
        try:
            data.decode(enc, errors="strict")
            return enc, "fallback"
        except Exception:
            continue

    # Last resort: latin-1 with replacement
    return "latin-1", "last-resort"


def convert_file(src_path: str, dst_path: str, add_bom: bool = False) -> Optional[str]:
    try:
        with open(src_path, "rb") as f:
            raw = f.read()
    except Exception as e:
        return f"READ_FAIL:{e}"

    enc, note = detect_encoding(raw)
    try:
        text = raw.decode(enc, errors="strict")
    except Exception:
        # Try cp949 tolerant decode as a final attempt for Korean text
        try:
            text = raw.decode("cp949", errors="ignore")
            note += "+cp949-ignore"
        except Exception as e:
            return f"DECODE_FAIL:{enc}:{e}"

    # Ensure destination directory
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    try:
        if add_bom:
            with open(dst_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(text)
        else:
            with open(dst_path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
    except Exception as e:
        return f"WRITE_FAIL:{e}"

    return f"OK:{enc}:{note}"


def should_process(file_name: str) -> bool:
    # Only .txt files
    return file_name.lower().endswith(".txt")


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert text files to UTF-8 (best-effort Korean safe)")
    parser.add_argument("--src", required=True, help="Source directory")
    parser.add_argument("--dst", required=True, help="Destination directory")
    parser.add_argument("--bom", action="store_true", help="Write UTF-8 with BOM")
    args = parser.parse_args()

    src_root = os.path.abspath(args.src)
    dst_root = os.path.abspath(args.dst)

    if not os.path.exists(src_root):
        print(f"ERROR: Source not found: {src_root}", file=sys.stderr)
        return 1

    processed = 0
    failures = 0

    for dirpath, _, filenames in os.walk(src_root):
        for name in filenames:
            if not should_process(name):
                continue
            src_path = os.path.join(dirpath, name)
            rel = os.path.relpath(src_path, src_root)
            dst_path = os.path.join(dst_root, rel)
            result = convert_file(src_path, dst_path, add_bom=args.bom)
            processed += 1
            if result is None or not result.startswith("OK:"):
                failures += 1
                print(f"FAIL\t{rel}\t{result}")
            else:
                print(f"OK\t{rel}\t{result}")

    print(f"SUMMARY\tprocessed={processed}\tfailures={failures}\tdst={dst_root}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())


