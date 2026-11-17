"""Тесты визуализации: DOT, вызов dot и ASCII-дерево (этап 5)."""

import os
import subprocess
import tempfile
import unittest
from unittest import mock

from depgraph.errors import VisualizationError
from depgraph.graph import build_graph, reverse_index
from depgraph.visualize import (ascii_tree, dot_path, quote, render_svg,
                                save_visualization, to_dot)

DEEP = 10
DIAMOND = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
CYCLE = {"A": ["B"], "B": ["C"], "C": ["A", "D"], "D": []}
SELF_LOOP = {"A": ["A", "B"], "B": []}
SHORTCUT = {"A": ["B", "X"], "B": ["C"], "C": ["X"], "X": ["Y"],
            "Y": ["Z"], "Z": []}


class DotTest(unittest.TestCase):
    """Текстовое представление графа на языке DOT."""

    def test_edges_and_root(self):
        """Все рёбра присутствуют, корневой пакет выделен."""
        dot = to_dot(build_graph(DIAMOND, "A", DEEP))
        self.assertTrue(dot.startswith("digraph dependencies {"))
        self.assertIn('"A" [fillcolor="#ffd966", penwidth=2];', dot)
        for edge in ('"A" -> "B"', '"A" -> "C"', '"B" -> "D"', '"C" -> "D"'):
            self.assertIn(edge, dot)
        self.assertTrue(dot.rstrip().endswith("}"))

    def test_cycle_and_loop(self):
        """Обратное ребро цикла и петля входят в описание."""
        self.assertIn('"C" -> "A"', to_dot(build_graph(CYCLE, "A", DEEP)))
        self.assertIn('"A" -> "A"', to_dot(build_graph(SELF_LOOP, "A", DEEP)))

    def test_missing_dashed(self):
        """Отсутствующий в репозитории пакет рисуется пунктиром."""
        dot = to_dot(build_graph({"a": ["b"]}, "a", DEEP))
        self.assertIn('"b" [style="rounded,dashed"', dot)

    def test_reverse_direction(self):
        """В обратном графе стрелка ведёт от зависящего пакета."""
        graph = build_graph(reverse_index(DIAMOND), "D", DEEP)
        dot = to_dot(graph, reverse=True)
        self.assertIn('"B" -> "D"', dot)
        self.assertNotIn('"D" -> "B"', dot)
        self.assertIn("Обратные зависимости пакета D", dot)

    def test_quote(self):
        """Кавычки и обратная косая черта экранируются."""
        self.assertEqual(quote('a"b\\c'), '"a\\"b\\\\c"')

    def test_dot_path(self):
        """DOT-файл сохраняется рядом с изображением."""
        self.assertEqual(dot_path(os.path.join("out", "g.svg")),
                         os.path.join("out", "g.dot"))


class RenderTest(unittest.TestCase):
    """Вызов утилиты dot."""

    def setUp(self):
        """Создать временный каталог для файлов."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.image = os.path.join(self.tmp.name, "g.svg")

    @mock.patch("depgraph.visualize.shutil.which", return_value=None)
    def test_dot_not_found(self, _):
        """Без dot выдаётся подсказка, DOT-файл всё равно сохранён."""
        graph = build_graph(DIAMOND, "A", DEEP)
        with self.assertRaises(VisualizationError) as caught:
            save_visualization(graph, self.image)
        self.assertIn("Graphviz", str(caught.exception))
        self.assertTrue(os.path.isfile(dot_path(self.image)))

    @mock.patch("depgraph.visualize.subprocess.run")
    @mock.patch("depgraph.visualize.shutil.which", return_value="dot")
    def test_dot_called(self, _, run):
        """dot вызывается с выводом в SVG."""
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        render_svg("g.dot", "g.svg")
        self.assertEqual(run.call_args.args[0],
                         ["dot", "-Tsvg", "g.dot", "-o", "g.svg"])

    @mock.patch("depgraph.visualize.subprocess.run")
    @mock.patch("depgraph.visualize.shutil.which", return_value="dot")
    def test_dot_failed(self, _, run):
        """Ненулевой код возврата dot — ошибка с текстом stderr."""
        run.return_value = subprocess.CompletedProcess([], 1, "", "syntax")
        with self.assertRaises(VisualizationError) as caught:
            render_svg("g.dot", "g.svg")
        self.assertIn("syntax", str(caught.exception))


class AsciiTreeTest(unittest.TestCase):
    """ASCII-дерево зависимостей."""

    def tree(self, index, max_depth=DEEP):
        """Построить граф от A и вернуть дерево одной строкой."""
        return "\n".join(ascii_tree(build_graph(index, "A", max_depth)))

    def test_diamond(self):
        """Повторно встреченный пакет помечается (*) и не раскрывается."""
        self.assertEqual(self.tree(DIAMOND),
                         "A\n├── B\n│   └── D\n└── C\n    └── D (*)")

    def test_cycle(self):
        """Цикл не приводит к бесконечному выводу."""
        self.assertEqual(self.tree(CYCLE),
                         "A\n└── B\n    └── C\n        ├── A (*)\n"
                         "        └── D")

    def test_self_loop(self):
        """Петля A -> A."""
        self.assertEqual(self.tree(SELF_LOOP), "A\n├── A (*)\n└── B")

    def test_expanded_on_shortest_path(self):
        """Пакет раскрывается на кратчайшем пути, дерево не глубже графа."""
        self.assertEqual(self.tree(SHORTCUT, 3),
                         "A\n├── B\n│   └── C\n│       └── X (*)\n"
                         "└── X\n    └── Y\n        └── Z")

    def test_single_package(self):
        """Пакет без зависимостей — дерево из одной строки."""
        self.assertEqual(self.tree({"A": []}), "A")


if __name__ == "__main__":
    unittest.main()
