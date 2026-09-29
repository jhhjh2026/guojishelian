#!/usr/bin/env python3
"""
package_release.py - 交付打包脚本
功能：
  1. 排除敏感文件（.env、数据库、备份、日志）
  2. 生成干净的交付包（ZIP）
  3. 支持 --dry-run 仅列出文件不实际打包

用法：
  python scripts/package_release.py              # 打包到 dist/release-{version}.zip
  python scripts/package_release.py --dry-run    # 仅预览文件清单
  python scripts/package_release.py --output ./my-release.zip
"""

from __future__ import annotations

import os
import sys
import zipfile
import argparse
import fnmatch
from datetime import datetime
from pathlib import Path

# ------ 配置 ------
ALWAYS_EXCLUDE = [
    ".env",
    ".env.local",
    ".env.production",
    ".env.*.local",
    "data/issf.db",
    "logs/",
    "logs/*",
    "__pycache__/",
    "__pycache__/*",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/",
    ".pytest_cache/*",
    ".coverage",
    "htmlcov/",
    "htmlcov/*",
    ".venv/",
    ".venv/*",
    ".git/",
    ".git/*",
    ".gitignore",
    ".dockerignore",
    "node_modules/",
    "node_modules/*",
    "*.egg-info/",
    "*.egg-info/*",
    ".DS_Store",
    "Thumbs.db",
]

# 按文件名模式剔除数据库备份（.db.bak_* 及其它备份后缀）
DB_BACKUP_PATTERNS = [
    "*.db.bak_*",
    "*.db.backup",
    "*.db.old",
    "*.sqlite.bak*",
]

def should_exclude(rel_path: str) -> bool:
    """判断文件是否应被排除"""
    rel_path = rel_path.replace("\\", "/")

    for pattern in ALWAYS_EXCLUDE:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        parts = rel_path.split("/")
        for part in parts:
            if fnmatch.fnmatch(part, pattern.rstrip("/").rstrip("*")):
                return True

    basename = os.path.basename(rel_path)
    for pattern in DB_BACKUP_PATTERNS:
        if fnmatch.fnmatch(basename, pattern):
            return True

    return False

def collect_files(project_root: str) -> tuple[list[tuple[str, str]], list[str]]:
    """收集需要打包的文件列表，返回 [(绝对路径, 相对路径), ...] 和排除列表"""
    project_root = os.path.abspath(project_root)
    files: list[tuple[str, str]] = []
    excluded: list[str] = []

    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in (
            ".venv", ".git", "__pycache__",
            ".pytest_cache", "node_modules",
            "htmlcov", ".egg-info",
        )]

        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abs_path, project_root)

            if should_exclude(rel_path):
                excluded.append(rel_path)
                continue

            files.append((abs_path, rel_path))

    return files, excluded

def create_release_zip(project_root: str, output_path: str) -> tuple[int, int]:
    """创建发布 ZIP 包，返回 (打包文件数, 排除文件数)"""
    files, excluded = collect_files(project_root)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_path, rel_path in files:
            zf.write(abs_path, rel_path)

    return len(files), len(excluded)

def main():
    parser = argparse.ArgumentParser(description="ISSF RAG Assistant 交付打包工具")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际打包")
    parser.add_argument("--output", "-o", default=None, help="输出 ZIP 文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示排除列表")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    if args.dry_run:
        files, excluded = collect_files(project_root)
        print(f"\n{'='*60}")
        print(f"  交付打包预览 (--dry-run)")
        print(f"  项目根目录: {project_root}")
        print(f"  打包文件数: {len(files)}")
        print(f"  排除文件数: {len(excluded)}")
        print(f"{'='*60}\n")

        if args.verbose:
            print("--- 排除列表 ---")
            for name in sorted(excluded):
                print(f"  [EXCLUDED] {name}")
            print("\n--- 打包列表 ---")
            for _, rel_path in sorted(files, key=lambda x: x[1]):
                print(f"  [INCLUDED] {rel_path}")

        print("\n--- 敏感文件核验 ---")
        sensitive_checks = [".env", "data/issf.db"]
        for check in sensitive_checks:
            is_excluded = any(
                fnmatch.fnmatch(e.replace("\\", "/"), check) or check in e
                for e in excluded
            )
            status = "✅ 已排除" if is_excluded else "❌ 未排除！"
            print(f"  {check}: {status}")
    else:
        version = os.getenv("APP_VERSION", "0.1.0")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_output = os.path.join(
            project_root, "dist", f"issf-rag-assistant-v{version}-{timestamp}.zip"
        )
        output = args.output or default_output

        print(f"正在打包: {project_root} → {output}")
        file_count, excluded_count = create_release_zip(project_root, output)
        print(f"完成! 打包 {file_count} 个文件，排除 {excluded_count} 个文件")
        print(f"输出: {output}")

if __name__ == "__main__":
    main()