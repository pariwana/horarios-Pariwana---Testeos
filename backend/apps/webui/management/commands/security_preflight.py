import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Escanea el proyecto buscando secretos accidentales antes de commit/deploy."

    SKIP_DIRS = {".git", ".deps", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
    SKIP_SUFFIXES = {
        ".pyc",
        ".pyo",
        ".sqlite3",
        ".db",
        ".xlsx",
        ".xls",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".pdf",
        ".zip",
    }
    PATTERNS = [
        ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
        ("github_ghp", re.compile("ghp" + r"_[A-Za-z0-9]{20,}")),
        ("supabase_secret", re.compile("sb_secret" + r"_[A-Za-z0-9_-]{20,}")),
        ("supabase_publishable", re.compile("sb_publishable" + r"_[A-Za-z0-9_-]{20,}")),
        ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ]

    def add_arguments(self, parser):
        parser.add_argument("--path", default=None, help="Ruta a escanear. Por defecto, raiz del proyecto.")

    def _should_scan(self, path):
        if any(part in self.SKIP_DIRS for part in path.parts):
            return False
        if path.suffix.lower() in self.SKIP_SUFFIXES:
            return False
        return path.is_file()

    def handle(self, *args, **options):
        root = Path(options.get("path") or settings.BASE_DIR.parent)
        if not root.exists():
            raise CommandError(f"Ruta no encontrada: {root}")

        findings = []
        for path in root.rglob("*"):
            if not self._should_scan(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pattern_name, pattern in self.PATTERNS:
                for match in pattern.finditer(text):
                    line_no = text.count("\n", 0, match.start()) + 1
                    findings.append(f"{path}:{line_no}: {pattern_name}")

        if findings:
            self.stdout.write("\n".join(findings))
            raise CommandError(f"Security preflight failed: {len(findings)} posible(s) secreto(s) encontrado(s).")

        self.stdout.write(self.style.SUCCESS(f"Security preflight passed: {root}"))
