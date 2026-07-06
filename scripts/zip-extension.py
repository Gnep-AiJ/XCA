from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dist" / "extension"
TARGET = ROOT / "dist" / "xca-extension.zip"
ASSET = ROOT / "worker" / "src" / "extension-zip.js"


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit("dist/extension does not exist. Run package:extension first.")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        TARGET.unlink()
    with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SOURCE.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(SOURCE).as_posix())
    ASSET.write_text(
        "export const EXTENSION_ZIP_HEX = "
        + repr(TARGET.read_bytes().hex())
        + ";\n",
        encoding="utf-8",
    )
    print(f"Extension zip ready: {TARGET}")


if __name__ == "__main__":
    main()
