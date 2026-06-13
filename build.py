from pathlib import Path
import shutil
import subprocess


REPO_ROOT = Path(__file__).resolve().parent
APP_DIR = REPO_ROOT / "app"
BUILD_DIR = REPO_ROOT / "build"

COMPILED_SOURCES = (
    Path("microdot/microdot.py"),
    Path("display.py"),
    Path("splitflap_module.py"),
)


def should_copy(source: Path) -> bool:
    relative_path = source.relative_to(APP_DIR)
    parts = relative_path.parts

    return (
        parts[0] not in {"scratch", "__pycache__"}
        and relative_path not in COMPILED_SOURCES
        and source.suffix != ".mpy"
    )


def copy_app_files() -> None:
    for source in APP_DIR.rglob("*"):
        if not source.is_file() or not should_copy(source):
            continue

        destination = BUILD_DIR / source.relative_to(APP_DIR)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def compile_sources() -> None:
    for relative_source in COMPILED_SOURCES:
        source = APP_DIR / relative_source
        destination = (BUILD_DIR / relative_source).with_suffix(".mpy")

        if not source.is_file():
            raise FileNotFoundError(f"Compiled source not found: {source}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "mpy-cross",
                "-march=rv32imc",
                "-o",
                str(destination),
                str(source),
            ],
            check=True,
        )


def main() -> None:
    if not APP_DIR.is_dir():
        raise FileNotFoundError(f"App directory not found: {APP_DIR}")

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)

    BUILD_DIR.mkdir()
    copy_app_files()
    compile_sources()
    print(f"Built MicroPython app in {BUILD_DIR}")


if __name__ == "__main__":
    main()
