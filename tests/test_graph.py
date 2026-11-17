"""Тесты построения графа зависимостей (этап 3)."""

import unittest

from depgraph.errors import RepositoryError
from depgraph.graph import build_graph, is_excluded

CHAIN = {"A": ["B"], "B": ["C"], "C": ["D"], "D": ["E"], "E": []}
DIAMOND = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": ["E"], "E": []}
CYCLE = {"A": ["B"], "B": ["C"], "C": ["A", "D"], "D": []}
SELF_LOOP = {"A": ["A", "B"], "B": []}
SHORTCUT = {"A": ["B", "X"], "B": ["C"], "C": ["X"], "X": ["Y"],
            "Y": ["Z"], "Z": []}
LONG_PATH_FIRST = {"A": ["B", "X"], "B": ["X"], "X": ["Y"], "Y": []}
DEEP = 10


class BuildGraphTest(unittest.TestCase):
    """Обход в глубину без рекурсии."""

    def test_chain(self):
        """Транзитивные зависимости цепочки."""
        graph = build_graph(CHAIN, "A", DEEP)
        self.assertEqual(graph.edge_list(), [("A", "B"), ("B", "C"),
                                             ("C", "D"), ("D", "E")])
        self.assertEqual(graph.depths["E"], 4)

    def test_depth_limit(self):
        """Пакеты на максимальной глубине не разворачиваются."""
        graph = build_graph(CHAIN, "A", 2)
        self.assertEqual(graph.packages(), ["A", "B", "C"])
        self.assertEqual(graph.children("C"), [])

    def test_diamond(self):
        """Общая зависимость входит в граф один раз, оба ребра сохранены."""
        graph = build_graph(DIAMOND, "A", DEEP)
        self.assertEqual(sorted(graph.packages()), ["A", "B", "C", "D", "E"])
        self.assertIn(("B", "D"), graph.edge_list())
        self.assertIn(("C", "D"), graph.edge_list())

    def test_cycle(self):
        """Цикл A -> B -> C -> A: ребро сохраняется, обход завершается."""
        graph = build_graph(CYCLE, "A", DEEP)
        self.assertIn(("C", "A"), graph.edge_list())
        self.assertEqual(len(graph.packages()), 4)

    def test_self_loop(self):
        """Петля A -> A."""
        graph = build_graph(SELF_LOOP, "A", DEEP)
        self.assertEqual(graph.edge_list(), [("A", "A"), ("A", "B")])

    def test_shortest_depth_with_limit(self):
        """Пути длины 1 и 3, max_depth=2: пакет X развёрнут."""
        graph = build_graph(SHORTCUT, "A", 2)
        self.assertEqual(graph.depths["X"], 1)
        self.assertIn(("X", "Y"), graph.edge_list())
        self.assertNotIn("Z", graph.depths)

    def test_shorter_path_found_later(self):
        """Пакет сначала найден длинным путём, затем коротким."""
        graph = build_graph(LONG_PATH_FIRST, "A", 2)
        self.assertEqual(graph.depths["X"], 1)
        self.assertEqual(graph.children("X"), ["Y"])
        graph = build_graph(SHORTCUT, "A", 3)
        self.assertEqual(graph.depths, {"A": 0, "B": 1, "X": 1, "C": 2,
                                        "Y": 2, "Z": 3})

    def test_filter(self):
        """Отфильтрованный пакет и его зависимости не обходятся."""
        graph = build_graph(DIAMOND, "A", DEEP, "B")
        self.assertNotIn("B", graph.depths)
        self.assertEqual(graph.edge_list(), [("A", "C"), ("C", "D"),
                                             ("D", "E")])

    def test_filter_cuts_subgraph(self):
        """Зависимости, достижимые только через исключённый пакет."""
        graph = build_graph(CHAIN, "A", DEEP, "C")
        self.assertEqual(graph.packages(), ["A", "B"])

    def test_missing_packages(self):
        """Зависимости, отсутствующие в индексе, отмечаются."""
        graph = build_graph({"a": ["b", "c"], "b": []}, "a", DEEP)
        self.assertEqual(graph.missing, ["c"])

    def test_unknown_root(self):
        """Несуществующий стартовый пакет — ошибка."""
        self.assertRaises(RepositoryError, build_graph, CHAIN, "Q", DEEP)

    def test_is_excluded(self):
        """Пустая подстрока ничего не исключает."""
        self.assertFalse(is_excluded("A", ""))
        self.assertTrue(is_excluded("LIBDEV", "DEV"))


if __name__ == "__main__":
    unittest.main()
