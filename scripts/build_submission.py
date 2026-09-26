from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARTICIPANT = "【姓名或团队名称待填写】"
BOARD_NAME = "板块二AI应用创新·数智天河"
WORK_NAME = "衡契"

ROOT_FILES = (
    ".env.example",
    ".env.local.example",
    ".gitignore",
    "双击启动衡契.cmd",
    "start-local.cmd",
    "stop-local.cmd",
    "README.md",
    "LEGAL_SOURCES.md",
    "THIRD_PARTY_NOTICES.md",
)
SOURCE_PATHS = (
    "backend/app",
    "backend/data/legal_bases.json",
    "backend/data/sample_contract.txt",
    "backend/requirements.txt",
    "backend/tests",
    "frontend/dist",
    "frontend/src",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/tsconfig.app.json",
    "frontend/tsconfig.json",
    "frontend/tsconfig.node.json",
    "frontend/vite.config.ts",
    "scripts/local_server.py",
)
EXCLUDED_NAMES = {"__pycache__", ".pytest_cache", "node_modules", ".runtime", ".git"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".log"}


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in EXCLUDED_NAMES or Path(name).suffix.lower() in EXCLUDED_SUFFIXES
    }


def _copy_source(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for relative in ROOT_FILES:
        source = PROJECT_ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(f"缺少提交文件：{source}")
        shutil.copy2(source, destination / relative)
    for relative in SOURCE_PATHS:
        source = PROJECT_ROOT / relative
        if not source.exists():
            raise FileNotFoundError(f"缺少提交文件：{source}")
        target = destination / relative
        if source.is_dir():
            shutil.copytree(source, target, ignore=_ignore)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _create_zip(source_dir: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(source_dir.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(source_dir.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="组装衡契参赛提交包")
    parser.add_argument("--participant", default=DEFAULT_PARTICIPANT)
    parser.add_argument("--description", type=Path, required=True)
    parser.add_argument("--commitment", type=Path)
    parser.add_argument("--presentation", type=Path)
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    description = args.description.resolve()
    if not description.is_file() or description.suffix.lower() != ".docx":
        raise ValueError("--description 必须指向已生成的DOCX作品说明。")

    package_name = f"{BOARD_NAME}+{args.participant}+{WORK_NAME}"
    package_dir = args.output_root.resolve() / package_name
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    _copy_source(package_dir / "作品原件-衡契")
    shutil.copy2(description, package_dir / "衡契-作品说明.docx")
    if args.commitment:
        commitment = args.commitment.resolve()
        if not commitment.is_file():
            raise FileNotFoundError(f"找不到原创承诺书：{commitment}")
        shutil.copy2(commitment, package_dir / commitment.name)
    if args.presentation:
        presentation = args.presentation.resolve()
        if not presentation.is_file() or presentation.suffix.lower() != ".pptx":
            raise ValueError("--presentation 必须指向PPTX演示文稿。")
        shutil.copy2(presentation, package_dir / presentation.name)
    if args.screenshots:
        screenshots = args.screenshots.resolve()
        if not screenshots.is_dir():
            raise ValueError("--screenshots 必须指向产品截图目录。")
        image_files = sorted(
            file for file in screenshots.iterdir()
            if file.is_file() and file.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
        if not image_files:
            raise ValueError("--screenshots 目录中没有可用的产品截图。")
        screenshot_target = package_dir / "产品截图"
        screenshot_target.mkdir()
        for image_file in image_files:
            shutil.copy2(image_file, screenshot_target / image_file.name)

    zip_path = package_dir.with_suffix(".zip")
    zip_path.unlink(missing_ok=True)
    _create_zip(package_dir, zip_path)
    print(package_dir)
    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
