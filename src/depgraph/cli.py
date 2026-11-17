"""Интерфейс командной строки инструмента визуализации зависимостей."""

import argparse
import sys

from depgraph.config import ConfigError, load_config

DEFAULT_CONFIG = "config.csv"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2


def build_parser():
    """Создать разборщик аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Визуализация графа зависимостей пакетов Ubuntu (apt).")
    parser.add_argument(
        "config", nargs="?", default=DEFAULT_CONFIG,
        help=f"путь к CSV-файлу конфигурации (по умолчанию {DEFAULT_CONFIG})")
    return parser


def format_value(value):
    """Представить значение параметра в текстовом виде для вывода."""
    if isinstance(value, bool):
        return str(value).lower()
    if value == "":
        return '""'
    return str(value)


def print_config(config):
    """Вывести все параметры конфигурации в формате ключ=значение."""
    print("Параметры конфигурации:")
    for key, value in config.items():
        print(f"{key}={format_value(value)}")


def report_error(error):
    """Вывести список ошибок конфигурации в поток ошибок."""
    print("Ошибка конфигурации:", file=sys.stderr)
    for problem in error.problems:
        print(f"  - {problem}", file=sys.stderr)


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        report_error(error)
        return EXIT_CONFIG_ERROR
    print_config(config)
    return EXIT_OK
