"""Тесты интерфейса командной строки."""

import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from depgraph.apt_repo import RepositoryError
from depgraph.cli import (EXIT_CONFIG_ERROR, EXIT_OK, EXIT_REPOSITORY_ERROR,
                          main)

CONFIG_TEMPLATE = """\
key,value
package,{package}
repository,http://archive.ubuntu.com/ubuntu
test_mode,false
output_image,graph.svg
ascii_tree,false
max_depth,3
filter_substring,
"""

INDEX = ({"curl": ["libc6", "zlib1g"], "libc6": [], "zlib1g": ["libc6"]},
         None)


class MainTest(unittest.TestCase):
    """Запуск приложения целиком с подменой загрузки индекса."""

    def setUp(self):
        """Создать временный каталог для конфигурации."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_main(self, package):
        """Запустить main и вернуть код завершения, stdout и stderr."""
        path = os.path.join(self.tmp.name, "config.csv")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(CONFIG_TEMPLATE.format(package=package))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([path])
        return code, out.getvalue(), err.getvalue()

    @mock.patch("depgraph.cli.load_index", return_value=INDEX)
    def test_prints_graph(self, _):
        """Выводятся рёбра графа и число пакетов."""
        code, out, _ = self.run_main("curl")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("  curl -> libc6\n  curl -> zlib1g\n", out)
        self.assertIn("  zlib1g -> libc6\n", out)
        self.assertIn("Пакетов в графе: 3, рёбер: 3", out)

    @mock.patch("depgraph.cli.load_index", return_value=INDEX)
    def test_no_dependencies(self, _):
        """Пакет без зависимостей."""
        code, out, _ = self.run_main("libc6")
        self.assertEqual(code, EXIT_OK)
        self.assertIn("(зависимостей нет)", out)

    @mock.patch("depgraph.cli.load_index", return_value=INDEX)
    def test_unknown_package(self, _):
        """Отсутствующий в индексе пакет — ошибка репозитория."""
        code, _, err = self.run_main("vim")
        self.assertEqual(code, EXIT_REPOSITORY_ERROR)
        self.assertIn("не найден", err)

    @mock.patch("depgraph.cli.load_index",
                side_effect=RepositoryError("HTTP 404 Not Found"))
    def test_download_error(self, _):
        """Ошибка загрузки индекса выводится в поток ошибок."""
        code, _, err = self.run_main("curl")
        self.assertEqual(code, EXIT_REPOSITORY_ERROR)
        self.assertIn("404", err)

    def test_config_error(self):
        """Ошибка конфигурации — код 2."""
        code, _, err = self.run_main("Bad Name")
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("Ошибка конфигурации", err)


if __name__ == "__main__":
    unittest.main()
