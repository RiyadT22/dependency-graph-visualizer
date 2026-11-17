"""Построение графа зависимостей обходом в глубину без рекурсии.

Источник данных — словарь «пакет -> список прямых зависимостей»; он
одинаков для реального и тестового репозиториев, поэтому алгоритм обхода
от источника не зависит.
"""

from dataclasses import dataclass, field

from depgraph.errors import RepositoryError

ROOT_DEPTH = 0
DEPTH_STEP = 1


@dataclass
class DependencyGraph:
    """Граф зависимостей, полученный обходом от корневого пакета.

    ``edges`` хранит рёбра только для развёрнутых пакетов; пакеты на
    максимальной глубине присутствуют в ``depths``, но не развёрнуты.
    ``depths`` — длина кратчайшего пути от корня до пакета.
    ``missing`` — пакеты, отсутствующие в репозитории.
    """

    root: str
    edges: dict = field(default_factory=dict)
    depths: dict = field(default_factory=dict)
    missing: list = field(default_factory=list)

    def packages(self):
        """Вернуть все пакеты графа в порядке обнаружения."""
        return list(self.depths)

    def children(self, package):
        """Вернуть прямые зависимости пакета внутри графа."""
        return self.edges.get(package, [])

    def edge_list(self):
        """Вернуть список рёбер (пакет, зависимость)."""
        return [(source, target)
                for source, targets in self.edges.items()
                for target in targets]


def is_excluded(name, substring):
    """Проверить, исключается ли пакет фильтром по подстроке."""
    return bool(substring) and substring in name


def reverse_index(index):
    """Развернуть все рёбра: «пакет -> пакеты, которые от него зависят».

    В результат входят все пакеты индекса и все упомянутые зависимости,
    в том числе отсутствующие в индексе.
    """
    reversed_index = {name: [] for name in index}
    for package, dependencies in index.items():
        for dependency in dependencies:
            dependents = reversed_index.setdefault(dependency, [])
            if package not in dependents:
                dependents.append(package)
    return reversed_index


def expand(graph, index, package, filter_substring):
    """Развернуть пакет: записать его рёбра и вернуть детей для обхода.

    Возвращаются только те зависимости, для которых найден более
    короткий путь, чем известный ранее; их глубина обновляется.
    """
    children = [child for child in index.get(package, [])
                if not is_excluded(child, filter_substring)]
    graph.edges[package] = children
    next_depth = graph.depths[package] + DEPTH_STEP
    improved = []
    for child in children:
        if next_depth < graph.depths.get(child, next_depth + DEPTH_STEP):
            graph.depths[child] = next_depth
            improved.append((child, next_depth))
    return improved


def build_graph(index, root, max_depth, filter_substring=""):
    """Построить граф зависимостей пакета ``root``.

    Обход в глубину выполняется с явным стеком пар (пакет, глубина).
    Для каждого пакета хранится минимальная найденная глубина; если пакет
    достигнут более коротким путём, он разворачивается заново. Пакеты на
    глубине ``max_depth`` не разворачиваются. Пакеты, имя которых содержит
    ``filter_substring``, в граф не попадают и не обходятся. Ребро на уже
    посещённый пакет сохраняется, поэтому циклы видны в графе, а обход
    не зацикливается.
    """
    if root not in index:
        raise RepositoryError(f"пакет «{root}» не найден в репозитории")
    graph = DependencyGraph(root, depths={root: ROOT_DEPTH})
    stack = [(root, ROOT_DEPTH)]
    while stack:
        package, depth = stack.pop()
        if depth > graph.depths[package] or depth >= max_depth:
            continue
        improved = expand(graph, index, package, filter_substring)
        stack.extend(reversed(improved))
    graph.missing = [name for name in graph.depths if name not in index]
    return graph
