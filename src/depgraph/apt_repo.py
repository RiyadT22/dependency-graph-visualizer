"""Получение сведений о зависимостях из репозитория Ubuntu (apt).

Индекс пакетов (файл ``Packages`` или ``Packages.gz``) загружается по HTTP
и разбирается вручную, без менеджеров пакетов и сторонних библиотек.
Загруженный файл сохраняется в каталоге кэша и при следующих запусках
берётся оттуда.
"""

import gzip
import os
import re
import zlib
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from depgraph.errors import RepositoryError

DISTRIBUTION = "noble"
DEFAULT_COMPONENT = "main"
ARCHITECTURE = "amd64"
INDEX_FILE = "Packages.gz"
INDEX_SUFFIXES = ("/Packages", "/Packages.gz")
CACHE_DIR = "cache"
CACHE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9.\-]+")
SCHEME_SEPARATOR = "://"
GZIP_MAGIC = b"\x1f\x8b"
DOWNLOAD_TIMEOUT = 60
PACKAGE_FIELD = "Package"
DEPENDS_FIELDS = ("Pre-Depends", "Depends")
PROVIDES_FIELD = "Provides"
CONTINUATION_PREFIXES = (" ", "\t")
ALTERNATIVE_SEPARATOR = "|"
ARCH_QUALIFIER_SEPARATOR = ":"
RESTRICTION_PATTERN = re.compile(r"\([^)]*\)|\[[^\]]*\]|<[^>]*>")


def index_url(repository, component=DEFAULT_COMPONENT):
    """Вернуть URL индекса пакетов для заданного адреса репозитория.

    Если адрес уже указывает на файл ``Packages`` или ``Packages.gz``,
    он используется как есть; иначе считается корнем зеркала Ubuntu.
    """
    if repository.endswith(INDEX_SUFFIXES):
        return repository
    return (f"{repository.rstrip('/')}/dists/{DISTRIBUTION}/{component}/"
            f"binary-{ARCHITECTURE}/{INDEX_FILE}")


def cache_path(url, cache_dir=CACHE_DIR):
    """Вернуть путь к файлу кэша для URL индекса."""
    name = url.split(SCHEME_SEPARATOR, 1)[-1]
    return os.path.join(cache_dir, CACHE_NAME_PATTERN.sub("_", name))


def describe_network_error(error):
    """Сформировать понятное описание сетевой ошибки."""
    if isinstance(error, HTTPError):
        return f"HTTP {error.code} {error.reason}"
    if isinstance(error, URLError):
        return str(error.reason)
    return str(error)


def decode_index(data, source):
    """Распаковать (при необходимости) и декодировать содержимое индекса."""
    if data.startswith(GZIP_MAGIC):
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError, zlib.error) as exc:
            raise RepositoryError(
                f"повреждённый gzip-архив {source}: {exc}") from exc
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RepositoryError(
            f"индекс {source} не является текстом UTF-8") from exc


def download(url):
    """Загрузить файл по URL и вернуть его содержимое в байтах."""
    try:
        with urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
            return response.read()
    except (URLError, OSError, ValueError) as exc:
        raise RepositoryError(
            f"не удалось загрузить {url}: "
            f"{describe_network_error(exc)}") from exc


def fetch_index_data(url, cache_dir=CACHE_DIR):
    """Вернуть содержимое индекса и признак того, что он взят из кэша.

    Если файл кэша существует, сеть не используется. Иначе индекс
    загружается и сохраняется в кэш; ошибка записи кэша не мешает работе.
    """
    path = cache_path(url, cache_dir)
    if os.path.isfile(path):
        try:
            with open(path, "rb") as stream:
                return stream.read(), path
        except OSError as exc:
            raise RepositoryError(
                f"не удалось прочитать кэш {path}: {exc}") from exc
    data = download(url)
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "wb") as stream:
            stream.write(data)
    except OSError:
        pass
    return data, None


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


def resolve_virtual(index, providers):
    """Заменить зависимости от виртуальных пакетов их поставщиками.

    Зависимость заменяется, только если такого реального пакета нет в
    индексе, но его объявляет в поле Provides другой пакет. При нескольких
    поставщиках выбирается первый по алфавиту.
    """
    for package, dependencies in index.items():
        resolved = []
        for dependency in dependencies:
            if dependency not in index and dependency in providers:
                dependency = min(providers[dependency])
            if dependency not in resolved:
                resolved.append(dependency)
        index[package] = resolved
    return index


def parse_index(text):
    """Построить словарь «пакет -> список прямых зависимостей».

    Зависимостями считаются пакеты из полей Pre-Depends и Depends.
    Из поля Provides собирается словарь «виртуальное имя -> поставщики»
    (версии отбрасываются), по которому разрешаются виртуальные пакеты.
    """
    index = {}
    providers = {}
    for stanza in iter_stanzas(text):
        name = stanza.get(PACKAGE_FIELD)
        if not name or name in index:
            continue
        fields = [stanza.get(field, "") for field in DEPENDS_FIELDS]
        index[name] = parse_depends(",".join(fields))
        for virtual in parse_depends(stanza.get(PROVIDES_FIELD, "")):
            providers.setdefault(virtual, []).append(name)
    if not index:
        raise RepositoryError("индекс пакетов пуст или имеет неверный формат")
    return resolve_virtual(index, providers)


def load_index(url, cache_dir=CACHE_DIR):
    """Загрузить и разобрать индекс пакетов.

    Возвращает пару: словарь зависимостей и путь к файлу кэша, если
    индекс был взят из кэша (иначе ``None``).
    """
    data, cached = fetch_index_data(url, cache_dir)
    return parse_index(decode_index(data, cached or url)), cached
