"""Получение сведений о зависимостях из репозитория Ubuntu (apt).

Индекс пакетов (файл ``Packages`` или ``Packages.gz``) загружается по HTTP
и разбирается вручную, без менеджеров пакетов и сторонних библиотек.
"""

import gzip
import re
import zlib
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

DISTRIBUTION = "noble"
COMPONENT = "main"
ARCHITECTURE = "amd64"
INDEX_PATH = (f"dists/{DISTRIBUTION}/{COMPONENT}/"
              f"binary-{ARCHITECTURE}/Packages.gz")
INDEX_SUFFIXES = ("/Packages", "/Packages.gz")
GZIP_MAGIC = b"\x1f\x8b"
DOWNLOAD_TIMEOUT = 60
PACKAGE_FIELD = "Package"
DEPENDS_FIELDS = ("Pre-Depends", "Depends")
CONTINUATION_PREFIXES = (" ", "\t")
ALTERNATIVE_SEPARATOR = "|"
ARCH_QUALIFIER_SEPARATOR = ":"
RESTRICTION_PATTERN = re.compile(r"\([^)]*\)|\[[^\]]*\]|<[^>]*>")


class RepositoryError(Exception):
    """Ошибка загрузки индекса пакетов или поиска пакета в нём."""


def index_url(repository):
    """Вернуть URL индекса пакетов для заданного адреса репозитория.

    Если адрес уже указывает на файл ``Packages`` или ``Packages.gz``,
    он используется как есть; иначе считается корнем зеркала Ubuntu.
    """
    if repository.endswith(INDEX_SUFFIXES):
        return repository
    return repository.rstrip("/") + "/" + INDEX_PATH


def describe_network_error(error):
    """Сформировать понятное описание сетевой ошибки."""
    if isinstance(error, HTTPError):
        return f"HTTP {error.code} {error.reason}"
    if isinstance(error, URLError):
        return str(error.reason)
    return str(error)


def decode_index(data, url):
    """Распаковать (при необходимости) и декодировать содержимое индекса."""
    if data.startswith(GZIP_MAGIC):
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError, zlib.error) as exc:
            raise RepositoryError(
                f"повреждённый gzip-архив {url}: {exc}") from exc
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RepositoryError(
            f"индекс {url} не является текстом UTF-8") from exc


def download_index(url):
    """Загрузить индекс пакетов по URL и вернуть его текст."""
    try:
        with urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
            data = response.read()
    except (URLError, OSError, ValueError) as exc:
        raise RepositoryError(
            f"не удалось загрузить {url}: "
            f"{describe_network_error(exc)}") from exc
    return decode_index(data, url)


def iter_stanzas(text):
    """Перебрать записи индекса как словари «поле -> значение».

    Записи разделяются пустыми строками; строки, начинающиеся с пробела
    или табуляции, продолжают значение предыдущего поля.
    """
    stanza = {}
    field = None
    for line in text.splitlines():
        if not line.strip():
            if stanza:
                yield stanza
            stanza, field = {}, None
        elif line.startswith(CONTINUATION_PREFIXES):
            if field:
                stanza[field] += " " + line.strip()
        else:
            name, separator, value = line.partition(":")
            if separator:
                field = name.strip()
                stanza[field] = value.strip()
    if stanza:
        yield stanza


def parse_depends(value):
    """Разобрать значение поля зависимостей в список имён пакетов.

    Ограничения версий, архитектур и профилей сборки отбрасываются,
    квалификатор ``:any`` удаляется, из альтернатив ``a | b`` берётся
    первая. Повторы исключаются с сохранением порядка.
    """
    names = []
    for group in value.split(","):
        first = group.split(ALTERNATIVE_SEPARATOR)[0]
        name = RESTRICTION_PATTERN.sub("", first).strip()
        name = name.split(ARCH_QUALIFIER_SEPARATOR)[0]
        if name and name not in names:
            names.append(name)
    return names


def parse_index(text):
    """Построить словарь «пакет -> список прямых зависимостей».

    Зависимостями считаются пакеты из полей Pre-Depends и Depends.
    """
    index = {}
    for stanza in iter_stanzas(text):
        name = stanza.get(PACKAGE_FIELD)
        if name and name not in index:
            fields = [stanza.get(field, "") for field in DEPENDS_FIELDS]
            index[name] = parse_depends(",".join(fields))
    if not index:
        raise RepositoryError("индекс пакетов пуст или имеет неверный формат")
    return index


def load_index(repository):
    """Загрузить и разобрать индекс пакетов репозитория."""
    return parse_index(download_index(index_url(repository)))


def direct_dependencies(index, package):
    """Вернуть прямые зависимости пакета из разобранного индекса."""
    if package not in index:
        raise RepositoryError(
            f"пакет «{package}» не найден в индексе "
            f"{DISTRIBUTION}/{COMPONENT}/{ARCHITECTURE}")
    return list(index[package])
