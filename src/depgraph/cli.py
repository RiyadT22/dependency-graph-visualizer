"""Интерфейс командной строки инструмента визуализации зависимостей."""

import argparse
import sys

from depgraph.apt_repo import index_url, load_index
from depgraph.config import ConfigError, load_config
from depgraph.errors import RepositoryError
from depgraph.graph import build_graph
from depgraph.test_repo import load_test_repository

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


def load_repository(config):
    """Загрузить репозиторий и вернуть словарь «пакет -> зависимости»."""
    if config.test_mode:
        print(f"Тестовый репозиторий: {config.repository}", flush=True)
        return load_test_repository(config.repository)
    url = index_url(config.repository, config.component)
    print(f"Индекс пакетов: {url}", flush=True)
    index, cached = load_index(url)
    if cached:
        print(f"  (взят из кэша {cached})")
    return index


def describe_limits(config):
    """Описать ограничения анализа: глубину и фильтр."""
    text = f"максимальная глубина {config.max_depth}"
    if config.filter_substring:
        text += f", исключаются пакеты с «{config.filter_substring}»"
    return text


def print_graph(graph, config):
    """Вывести рёбра графа и итоговое число пакетов."""
    print(f"Граф зависимостей пакета {graph.root} "
          f"({describe_limits(config)}):")
    edges = graph.edge_list()
    for source, target in edges:
        print(f"  {source} -> {target}")
    if not edges:
        print("  (зависимостей нет)")
    print(f"Пакетов в графе: {len(graph.packages())}, рёбер: {len(edges)}")
    by_depth = sorted(graph.depths.items(), key=lambda item: item[1])
    depths = ", ".join(f"{name}={depth}" for name, depth in by_depth)
    print(f"Глубина (кратчайший путь от {graph.root}): {depths}")
    if graph.missing:
        print("Нет в репозитории (зависимости неизвестны): "
              + ", ".join(graph.missing))


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        report_error("Ошибка конфигурации", error.problems)
        return EXIT_CONFIG_ERROR
    try:
        index = load_repository(config)
        graph = build_graph(index, config.package, config.max_depth,
                            config.filter_substring)
    except RepositoryError as error:
        report_error("Ошибка репозитория", [str(error)])
        return EXIT_REPOSITORY_ERROR
    print_graph(graph, config)
    return EXIT_OK
