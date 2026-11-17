"""Чтение файла тестового репозитория.

Каждая значимая строка файла имеет вид ``ИМЯ: ЗАВИСИМОСТЬ ЗАВИСИМОСТЬ ...``,
где имена — заглавные латинские буквы. Пустые строки и строки,
начинающиеся с ``#``, пропускаются. Пакеты, упомянутые только как
зависимости, считаются пакетами без зависимостей.
"""

import re

from depgraph.errors import RepositoryError

NAME_PATTERN = re.compile(r"[A-Z]+")
COMMENT_PREFIX = "#"
NAME_SEPARATOR = ":"
PROBLEM_INDENT = "    "


def parse_line(line):
    """Разобрать строку описания пакета в пару (имя, зависимости)."""
    name, separator, rest = line.partition(NAME_SEPARATOR)
    name = name.strip()
    if not separator:
        raise ValueError("ожидается строка вида «ИМЯ: ЗАВИСИМОСТИ»")
    if not NAME_PATTERN.fullmatch(name):
        raise ValueError(f"недопустимое имя пакета «{name}»")
    dependencies = []
    for dependency in rest.split():
        if not NAME_PATTERN.fullmatch(dependency):
            raise ValueError(f"недопустимое имя зависимости «{dependency}»")
        if dependency not in dependencies:
            dependencies.append(dependency)
    return name, dependencies


def parse_test_repository(text):
    """Построить словарь «пакет -> список зависимостей» из текста файла."""
    index = {}
    problems = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(COMMENT_PREFIX):
            continue
        try:
            name, dependencies = parse_line(line)
        except ValueError as exc:
            problems.append(f"строка {number}: {exc}")
            continue
        if name in index:
            problems.append(f"строка {number}: пакет «{name}» описан повторно")
        index[name] = dependencies
    if problems:
        raise RepositoryError("\n".join(problems))
    for dependencies in list(index.values()):
        for dependency in dependencies:
            index.setdefault(dependency, [])
    return index


def load_test_repository(path):
    """Прочитать файл тестового репозитория и вернуть словарь зависимостей."""
    try:
        with open(path, encoding="utf-8-sig") as stream:
            text = stream.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise RepositoryError(
            f"не удалось прочитать тестовый репозиторий {path}: {exc}"
        ) from exc
    try:
        return parse_test_repository(text)
    except RepositoryError as exc:
        details = str(exc).replace("\n", "\n" + PROBLEM_INDENT)
        raise RepositoryError(
            f"ошибки в файле {path}:\n{PROBLEM_INDENT}{details}") from exc
