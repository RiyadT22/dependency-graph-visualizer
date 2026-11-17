"""Интерфейс командной строки инструмента визуализации зависимостей."""

import argparse
import sys

from depgraph.apt_repo import index_url, load_index
from depgraph.config import ConfigError, load_config
from depgraph.errors import RepositoryError, VisualizationError
from depgraph.graph import build_graph, reverse_index
from depgraph.test_repo import load_test_repository
from depgraph.visualize import ascii_tree, dot_path, save_visualization

DEFAULT_CONFIG = "config.csv"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_REPOSITORY_ERROR = 3
EXIT_VISUALIZATION_ERROR = 4


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


def print_summary(graph, config):
    """Вывести сводку о графе: число пакетов, рёбер и отсутствующие."""
    kind = "Обратные зависимости" if config.reverse else "Зависимости"
    print(f"{kind} пакета {graph.root} ({describe_limits(config)}): "
          f"пакетов {len(graph.packages())}, "
          f"рёбер {len(graph.edge_list())}")
    if graph.missing:
        print("Нет в репозитории (зависимости неизвестны): "
              + ", ".join(graph.missing))


def analyze(index, config):
    """Построить граф прямых или обратных зависимостей пакета."""
    source = reverse_index(index) if config.reverse else index
    return build_graph(source, config.package, config.max_depth,
                       config.filter_substring)


def visualize(graph, config):
    """Вывести ASCII-дерево (если задано) и сохранить DOT и SVG."""
    if config.ascii_tree:
        print()
        print("\n".join(ascii_tree(graph)))
        print()
    print(f"Описание графа (Graphviz DOT): {dot_path(config.output_image)}",
          flush=True)
    save_visualization(graph, config.output_image, config.reverse)
    print(f"Изображение графа (SVG): {config.output_image}")


def main(argv=None):
    """Запустить приложение и вернуть код завершения."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        report_error("Ошибка конфигурации", error.problems)
        return EXIT_CONFIG_ERROR
    try:
        graph = analyze(load_repository(config), config)
    except RepositoryError as error:
        report_error("Ошибка репозитория", [str(error)])
        return EXIT_REPOSITORY_ERROR
    print_summary(graph, config)
    try:
        visualize(graph, config)
    except VisualizationError as error:
        report_error("Ошибка визуализации", [str(error)])
        return EXIT_VISUALIZATION_ERROR
    return EXIT_OK
