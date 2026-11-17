"""Интерфейс командной строки инструмента визуализации зависимостей."""

import argparse
import sys

from depgraph.apt_repo import (RepositoryError, direct_dependencies,
                               index_url, load_index)
from depgraph.config import ConfigError, load_config

DEFAULT_CONFIG = "config.csv"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_REPOSITORY_ERROR = 3


def build_parser():
    """Создать разборщик аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Визуализация графа зависимостей пакетов Ubuntu (apt).")
    parser.add_argument(
        "config", nargs="?", default=DEFAULT_CONFIG,
        help=f"путь к CSV-файлу конфигурации (по умолчанию {DEFAULT_CONFIG})")
    return parser


def report_error(title, problems):
    """Вывести заголовок и список проблем в поток ошибок."""
    print(f"{title}:", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)


def print_dependencies(package, dependencies):
    """Вывести список прямых зависимостей пакета."""
    if not dependencies:
        print(f"Пакет {package} не имеет прямых зависимостей.")
        return
    print(f"Прямые зависимости пакета {package}:")
    for name in dependencies:
        print(f"  {name}")
    print(f"Всего: {len(dependencies)}")


def fetch_dependencies(config):
    """Загрузить индекс репозитория и вернуть прямые зависимости пакета."""
    if config.test_mode:
        raise RepositoryError(
            "тестовый репозиторий пока не поддерживается, "
            "укажите test_mode=false и URL репозитория")
    print(f"Индекс пакетов: {index_url(config.repository)}", flush=True)
    index = load_index(config.repository)
    return direct_dependencies(index, config.package)


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        report_error("Ошибка конфигурации", error.problems)
        return EXIT_CONFIG_ERROR
    try:
        dependencies = fetch_dependencies(config)
    except RepositoryError as error:
        report_error("Ошибка репозитория", [str(error)])
        return EXIT_REPOSITORY_ERROR
    print_dependencies(config.package, dependencies)
    return EXIT_OK
