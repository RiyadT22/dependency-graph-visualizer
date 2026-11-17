"""Загрузка и проверка пользовательской конфигурации из CSV-файла.

Файл конфигурации состоит из строк вида ``ключ,значение``. Допускаются
строка-заголовок ``key,value``, пустые строки и комментарии, начинающиеся
с символа ``#``. Все найденные ошибки собираются вместе и сообщаются
пользователю одним исключением :class:`ConfigError`.
"""

import csv
import os
import re
from dataclasses import astuple, dataclass, fields
from urllib.parse import urlparse

CSV_COLUMNS = 2
HEADER = ("key", "value")
COMMENT_PREFIX = "#"
MIN_DEPTH = 1
MAX_DEPTH = 100
TRUE_VALUES = ("true", "yes", "1", "on")
FALSE_VALUES = ("false", "no", "0", "off")
IMAGE_EXTENSION = ".svg"
FORBIDDEN_FILE_CHARS = set('<>:"|?*')
URL_SCHEMES = ("http", "https")
APT_NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9+.\-]+")
TEST_NAME_PATTERN = re.compile(r"[A-Z]+")
COMPONENTS = ("main", "restricted", "universe", "multiverse")
OPTIONAL_DEFAULTS = {"component": "main", "reverse": "false"}


class ConfigError(Exception):
    """Ошибка конфигурации со списком всех обнаруженных проблем."""

    def __init__(self, problems):
        """Сохранить список проблем и сформировать текст исключения."""
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class Config:
    """Проверенные параметры, заданные пользователем."""

    package: str
    repository: str
    test_mode: bool
    output_image: str
    ascii_tree: bool
    max_depth: int
    filter_substring: str
    component: str = OPTIONAL_DEFAULTS["component"]
    reverse: bool = False

    def items(self):
        """Вернуть пары (ключ, значение) в порядке объявления полей."""
        names = [field.name for field in fields(self)]
        return list(zip(names, astuple(self)))


KNOWN_KEYS = tuple(field.name for field in fields(Config))


def parse_bool(text):
    """Преобразовать строку в логическое значение."""
    lowered = text.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    raise ValueError(f"ожидается true или false, получено «{text}»")


def parse_depth(text):
    """Преобразовать строку в максимальную глубину анализа."""
    try:
        depth = int(text)
    except ValueError:
        raise ValueError(
            f"ожидается целое число, получено «{text}»") from None
    if not MIN_DEPTH <= depth <= MAX_DEPTH:
        raise ValueError(
            f"глубина должна быть от {MIN_DEPTH} до {MAX_DEPTH}, "
            f"получено {depth}")
    return depth


def parse_image(text):
    """Проверить имя файла, в который будет сохранено изображение графа."""
    if not text:
        raise ValueError("имя файла не задано")
    name = os.path.basename(text)
    if FORBIDDEN_FILE_CHARS & set(name):
        raise ValueError(f"недопустимые символы в имени файла «{name}»")
    if not name.lower().endswith(IMAGE_EXTENSION) or \
            name.lower() == IMAGE_EXTENSION:
        raise ValueError(
            f"ожидается имя файла с расширением {IMAGE_EXTENSION}, "
            f"получено «{text}»")
    directory = os.path.dirname(text)
    if directory and not os.path.isdir(directory):
        raise ValueError(f"каталог «{directory}» не существует")
    return text


def parse_component(text):
    """Проверить имя компонента репозитория Ubuntu."""
    if text not in COMPONENTS:
        raise ValueError(
            f"ожидается одно из {', '.join(COMPONENTS)}, получено «{text}»")
    return text


def parse_filter(text):
    """Вернуть подстроку фильтрации; пустая строка отключает фильтр."""
    return text


def check_package(name, test_mode):
    """Проверить имя анализируемого пакета с учётом режима работы."""
    if not name:
        raise ValueError("имя пакета не задано")
    if test_mode:
        pattern = TEST_NAME_PATTERN
        hint = "в тестовом режиме допустимы только заглавные латинские буквы"
    else:
        pattern = APT_NAME_PATTERN
        hint = "допустимы символы a-z, 0-9, + - . (не менее двух)"
    if not pattern.fullmatch(name):
        raise ValueError(f"недопустимое имя «{name}»: {hint}")
    return name


def check_repository(source, test_mode):
    """Проверить URL репозитория или путь к файлу тестового репозитория."""
    if not source:
        raise ValueError("источник не задан")
    if test_mode:
        if not os.path.isfile(source):
            raise ValueError(f"файл тестового репозитория не найден: {source}")
        return source
    parsed = urlparse(source)
    if parsed.scheme not in URL_SCHEMES or not parsed.netloc:
        raise ValueError(
            f"ожидается URL вида http(s)://host/path, получено «{source}»")
    return source


VALUE_PARSERS = {
    "test_mode": parse_bool,
    "output_image": parse_image,
    "ascii_tree": parse_bool,
    "max_depth": parse_depth,
    "filter_substring": parse_filter,
    "component": parse_component,
    "reverse": parse_bool,
}

MODE_CHECKERS = {
    "package": check_package,
    "repository": check_repository,
}


def is_skipped(row):
    """Определить, нужно ли пропустить строку CSV (пустая, комментарий)."""
    cells = [cell.strip() for cell in row]
    if not any(cells):
        return True
    if cells[0].startswith(COMMENT_PREFIX):
        return True
    return tuple(cell.lower() for cell in cells) == HEADER


def collect_pairs(rows):
    """Собрать словарь ключ -> значение и список проблем из строк CSV."""
    pairs = {}
    problems = []
    for number, row in enumerate(rows, start=1):
        if is_skipped(row):
            continue
        if len(row) != CSV_COLUMNS:
            problems.append(
                f"строка {number}: ожидается {CSV_COLUMNS} столбца "
                f"(ключ,значение), получено {len(row)}")
            continue
        key, value = row[0].strip(), row[1].strip()
        if key not in KNOWN_KEYS:
            problems.append(f"строка {number}: неизвестный параметр «{key}»")
        elif key in pairs:
            problems.append(f"строка {number}: параметр «{key}» повторяется")
        else:
            pairs[key] = value
    for key in KNOWN_KEYS:
        if key in OPTIONAL_DEFAULTS:
            pairs.setdefault(key, OPTIONAL_DEFAULTS[key])
        elif key not in pairs:
            problems.append(f"не задан обязательный параметр «{key}»")
    return pairs, problems


def read_rows(path):
    """Прочитать все строки CSV-файла конфигурации."""
    if not os.path.isfile(path):
        raise ConfigError([f"файл конфигурации не найден: {path}"])
    try:
        with open(path, encoding="utf-8-sig", newline="") as stream:
            return list(csv.reader(stream))
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ConfigError(
            [f"не удалось прочитать файл конфигурации {path}: {exc}"]) from exc


def apply_parsers(parsers, pairs, extra_args=()):
    """Применить проверки к значениям; вернуть результаты и проблемы."""
    values = {}
    problems = []
    for key, parser in parsers.items():
        try:
            values[key] = parser(pairs[key], *extra_args)
        except ValueError as exc:
            problems.append(f"{key}: {exc}")
    return values, problems


def check_filter(values):
    """Проверить, что стартовый пакет не исключается фильтром."""
    substring = values.get("filter_substring")
    package = values.get("package")
    if substring and package and substring in package:
        return [f"filter_substring: подстрока «{substring}» исключает "
                f"сам анализируемый пакет «{package}»"]
    return []


def load_config(path):
    """Загрузить и проверить конфигурацию; вернуть объект :class:`Config`.

    При любой ошибке выбрасывается :class:`ConfigError` со списком всех
    найденных проблем.
    """
    pairs, problems = collect_pairs(read_rows(path))
    if problems:
        raise ConfigError(problems)
    values, problems = apply_parsers(VALUE_PARSERS, pairs)
    if "test_mode" in values:
        checked, mode_problems = apply_parsers(
            MODE_CHECKERS, pairs, (values["test_mode"],))
        values.update(checked)
        problems.extend(mode_problems)
    else:
        problems.append("package, repository: не проверены, так как "
                        "режим работы (test_mode) задан неверно")
    problems.extend(check_filter(values))
    if problems:
        raise ConfigError(problems)
    return Config(**values)
