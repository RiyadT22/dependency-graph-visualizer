"""Тесты интерфейса командной строки."""

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from depgraph.cli import (EXIT_CONFIG_ERROR, EXIT_OK, EXIT_REPOSITORY_ERROR,
                          EXIT_VISUALIZATION_ERROR, main)
from depgraph.errors import RepositoryError, VisualizationError

CONFIG_TEMPLATE = """\
key,value
package,{package}
repository,http://archive.ubuntu.com/ubuntu
test_mode,false
output_image,graph.svg
ascii_tree,true
max_depth,3
filter_substring,
"""

INDEX = ({"curl": ["libc6", "zlib1g"], "libc6": [], "zlib1g": ["libc6"]},
         None)


@mock.patch("depgraph.cli.save_visualization")
@mock.patch("depgraph.cli.load_index", return_value=INDEX)
class MainTest(unittest.TestCase):
    """Запуск приложения целиком с подменой загрузки индекса и dot."""

    def setUp(self):
        """Создать временный каталог для конфигурации."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_main(self, package, extra=""):
        """Запустить main и вернуть код завершения, stdout и stderr."""
        path = os.path.join(self.tmp.name, "config.csv")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(CONFIG_TEMPLATE.format(package=package) + extra)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([path])
        return code, out.getvalue(), err.getvalue()

    def test_summary_and_tree(self, _, save):
        """Выводятся сводка, ASCII-дерево и пути к файлам."""
        code, out, _ = self.run_main("curl")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("пакетов 3, рёбер 3", out)
        self.assertIn("curl\n├── libc6\n└── zlib1g\n    └── libc6 (*)", out)
        self.assertIn("graph.dot", out)
        save.assert_called_once()

    def test_tree_disabled(self, _, save):
        """При ascii_tree=false дерево не выводится."""
        path = os.path.join(self.tmp.name, "config.csv")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(CONFIG_TEMPLATE.format(package="curl").replace(
                "ascii_tree,true", "ascii_tree,false"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main([path])
        self.assertNotIn("├──", out.getvalue())

    def test_reverse(self, _, save):
        """В обратном режиме строится граф зависящих пакетов."""
        code, out, _ = self.run_main("libc6", "reverse,true\n")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Обратные зависимости пакета libc6", out)
        self.assertIn("libc6\n├── curl\n└── zlib1g\n    └── curl (*)", out)
        self.assertTrue(save.call_args.args[2])

    def test_unknown_package(self, _, save):
        """Отсутствующий в индексе пакет — ошибка репозитория."""
        code, _, err = self.run_main("vim")
        self.assertEqual(code, EXIT_REPOSITORY_ERROR)
        self.assertIn("не найден", err)

    def test_download_error(self, load, save):
        """Ошибка загрузки индекса выводится в поток ошибок."""
        load.side_effect = RepositoryError("HTTP 404 Not Found")
        code, _, err = self.run_main("curl")
        self.assertEqual(code, EXIT_REPOSITORY_ERROR)
        self.assertIn("404", err)

    def test_visualization_error(self, _, save):
        """Отсутствие dot — ошибка визуализации, код 4."""
        save.side_effect = VisualizationError("dot не найден")
        code, out, err = self.run_main("curl")
        self.assertEqual(code, EXIT_VISUALIZATION_ERROR)
        self.assertIn("├── libc6", out)
        self.assertIn("dot не найден", err)

    def test_config_error(self, _, save):
        """Ошибка конфигурации — код 2."""
        code, _, err = self.run_main("Bad Name")
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("Ошибка конфигурации", err)


if __name__ == "__main__":
    unittest.main()
