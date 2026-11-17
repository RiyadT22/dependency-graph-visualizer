"""Визуализация графа зависимостей: Graphviz (DOT, SVG) и ASCII-дерево."""

import os
import shutil
import subprocess

from depgraph.errors import VisualizationError
from depgraph.graph import DEPTH_STEP

DOT_EXTENSION = ".dot"
DOT_PROGRAM = "dot"
DOT_TIMEOUT = 120
GRAPHVIZ_URL = "https://graphviz.org/download/"
INDENT = "    "
ROOT_STYLE = 'fillcolor="#ffd966", penwidth=2'
MISSING_STYLE = 'style="rounded,dashed", fontcolor="#666666"'
BRANCH = "├── "
LAST_BRANCH = "└── "
PIPE = "│   "
SPACE = "    "
REPEAT_MARK = " (*)"


def quote(name):
    """Заключить идентификатор в кавычки по правилам языка DOT."""
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def drawn_edges(graph, reverse):
    """Вернуть рёбра в направлении «пакет -> его зависимость».

    В обратном графе рёбра ведут от пакета к зависящим от него, поэтому
    для рисунка они разворачиваются обратно.
    """
    edges = graph.edge_list()
    if reverse:
        return [(target, source) for source, target in edges]
    return edges


def to_dot(graph, reverse=False):
    """Сформировать описание графа на языке Graphviz DOT."""
    kind = "Обратные зависимости" if reverse else "Зависимости"
    lines = [
        "digraph dependencies {",
        f"{INDENT}label={quote(f'{kind} пакета {graph.root}')};",
        f"{INDENT}labelloc=t;",
        f"{INDENT}rankdir=LR;",
        f'{INDENT}node [shape=box, style="rounded,filled", '
        f'fillcolor="#eef3fb", fontname="Helvetica"];',
        f"{INDENT}{quote(graph.root)} [{ROOT_STYLE}];",
    ]
    for name in graph.missing:
        lines.append(f"{INDENT}{quote(name)} [{MISSING_STYLE}];")
    for name in graph.packages():
        if name != graph.root and name not in graph.missing:
            lines.append(f"{INDENT}{quote(name)};")
    for source, target in drawn_edges(graph, reverse):
        lines.append(f"{INDENT}{quote(source)} -> {quote(target)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def dot_path(image_path):
    """Вернуть путь к DOT-файлу, сохраняемому рядом с изображением."""
    return os.path.splitext(image_path)[0] + DOT_EXTENSION


def write_dot(dot_text, path):
    """Сохранить описание графа в файл."""
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(dot_text)
    except OSError as exc:
        raise VisualizationError(f"не удалось записать {path}: {exc}") from exc


def render_svg(dot_file, image_path):
    """Получить SVG-изображение из DOT-файла утилитой dot (Graphviz)."""
    program = shutil.which(DOT_PROGRAM)
    if program is None:
        raise VisualizationError(
            f"утилита {DOT_PROGRAM} (Graphviz) не найдена в PATH. "
            f"Установите Graphviz ({GRAPHVIZ_URL}) и повторите запуск; "
            f"описание графа уже сохранено в {dot_file}")
    command = [program, "-Tsvg", dot_file, "-o", image_path]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=DOT_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VisualizationError(f"не удалось запустить dot: {exc}") from exc
    if result.returncode:
        raise VisualizationError(
            f"dot завершился с ошибкой: {result.stderr.strip()}")


def save_visualization(graph, image_path, reverse=False):
    """Сохранить DOT-описание и SVG-изображение; вернуть путь к DOT."""
    dot_file = dot_path(image_path)
    write_dot(to_dot(graph, reverse), dot_file)
    render_svg(dot_file, image_path)
    return dot_file


def ascii_tree(graph):
    """Построить ASCII-дерево зависимостей без рекурсии.

    Каждый пакет раскрывается один раз — в первой позиции, где его уровень
    в дереве равен глубине в графе (длине кратчайшего пути), поэтому
    дерево не глубже ``max_depth``. Остальные вхождения пакета помечаются
    ``(*)`` и не раскрываются; это же защищает от бесконечного вывода
    циклов.
    """
    lines = [graph.root]
    expanded = {graph.root}
    stack = child_entries(graph, graph.root, "", graph.depths[graph.root])
    while stack:
        name, prefix, last, level = stack.pop()
        line = prefix + (LAST_BRANCH if last else BRANCH) + name
        if name in expanded or level != graph.depths[name]:
            lines.append(line + REPEAT_MARK)
            continue
        lines.append(line)
        expanded.add(name)
        child_prefix = prefix + (SPACE if last else PIPE)
        stack.extend(child_entries(graph, name, child_prefix, level))
    return lines


def child_entries(graph, package, prefix, level):
    """Вернуть элементы стека для детей пакета в обратном порядке.

    Каждый элемент — (имя, префикс строки, признак последнего ребёнка,
    уровень ребёнка в дереве).
    """
    children = graph.children(package)
    child_level = level + DEPTH_STEP
    entries = [(child, prefix, False, child_level) for child in children]
    if entries:
        entries[-1] = (children[-1], prefix, True, child_level)
    return list(reversed(entries))
