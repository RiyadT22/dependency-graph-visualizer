"""Тесты чтения файла тестового репозитория."""

import os
import tempfile
import unittest

from depgraph.errors import RepositoryError
from depgraph.test_repo import (load_test_repository, parse_line,
                                parse_test_repository)

EXAMPLES = os.path.join(os.path.dirname(__file__), os.pardir,
                        "examples", "repos")


class ParseTestRepositoryTest(unittest.TestCase):
    """Разбор формата «ИМЯ: ЗАВИСИМОСТИ»."""

    def test_parse_line(self):
        """Строка с зависимостями и без них."""
        self.assertEqual(parse_line("A: B C B"), ("A", ["B", "C"]))
        self.assertEqual(parse_line("D:"), ("D", []))

    def test_bad_lines(self):
        """Нет двоеточия, строчные буквы, цифры."""
        for line in ("A B", "a: B", "A: b", "A1: B", ": B"):
            self.assertRaises(ValueError, parse_line, line)

    def test_comments_and_implicit_packages(self):
        """Комментарии пропускаются, упомянутые пакеты добавляются."""
        index = parse_test_repository("# комментарий\n\nA: B\n")
        self.assertEqual(index, {"A": ["B"], "B": []})

    def test_errors_collected(self):
        """Все ошибки файла сообщаются вместе, включая повторы."""
        with self.assertRaises(RepositoryError) as caught:
            parse_test_repository("A: B\nA: C\nx: Y\n")
        self.assertIn("строка 2", str(caught.exception))
        self.assertIn("строка 3", str(caught.exception))

    def test_load_examples(self):
        """Примеры из examples/repos читаются без ошибок."""
        for name in ("chain", "diamond", "cycle", "self_loop", "shortcut",
                     "filter"):
            path = os.path.join(EXAMPLES, f"{name}.txt")
            self.assertTrue(load_test_repository(path))

    def test_missing_file(self):
        """Отсутствующий файл — ошибка репозитория."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertRaises(RepositoryError, load_test_repository,
                              os.path.join(tmp, "none.txt"))


if __name__ == "__main__":
    unittest.main()
