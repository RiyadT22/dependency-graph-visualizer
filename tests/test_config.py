"""Тесты загрузки и проверки конфигурации (этап 1)."""

import os
import tempfile
import unittest

from depgraph.config import (ConfigError, check_package, check_repository,
                             load_config, parse_bool, parse_component,
                             parse_depth, parse_image)

VALID_ROWS = {
    "package": "curl",
    "repository": "http://archive.ubuntu.com/ubuntu",
    "test_mode": "false",
    "output_image": "graph.svg",
    "ascii_tree": "true",
    "max_depth": "3",
    "filter_substring": "",
}


class ConfigFileTestCase(unittest.TestCase):
    """Базовый класс: запись временных CSV-файлов конфигурации."""

    def setUp(self):
        """Создать временный каталог для файлов теста."""
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, text):
        """Записать текст во временный CSV-файл и вернуть его путь."""
        path = os.path.join(self.tmp.name, "config.csv")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(text)
        return path

    def write_rows(self, **overrides):
        """Записать корректную конфигурацию с заменёнными значениями."""
        rows = dict(VALID_ROWS, **overrides)
        lines = ["key,value"] + [f"{k},{v}" for k, v in rows.items()]
        return self.write("\n".join(lines) + "\n")

    def problems(self, path):
        """Вернуть список проблем, найденных при загрузке файла."""
        with self.assertRaises(ConfigError) as caught:
            load_config(path)
        return caught.exception.problems


class LoadConfigTest(ConfigFileTestCase):
    """Проверки чтения CSV-файла целиком."""

    def test_valid_config(self):
        """Корректный файл загружается без ошибок."""
        config = load_config(self.write_rows())
        self.assertEqual(config.package, "curl")
        self.assertFalse(config.test_mode)
        self.assertTrue(config.ascii_tree)
        self.assertEqual(config.max_depth, 3)
        self.assertEqual(config.filter_substring, "")

    def test_items_order(self):
        """Параметры выводятся в фиксированном порядке."""
        keys = [key for key, _ in load_config(self.write_rows()).items()]
        self.assertEqual(keys[:len(VALID_ROWS)], list(VALID_ROWS))

    def test_optional_component(self):
        """Компонент необязателен и по умолчанию равен main."""
        self.assertEqual(load_config(self.write_rows()).component, "main")
        path = self.write_rows(component="universe")
        self.assertEqual(load_config(path).component, "universe")

    def test_filter_excludes_root(self):
        """Фильтр, исключающий сам анализируемый пакет, — ошибка."""
        path = self.write_rows(filter_substring="url")
        self.assertIn("исключает", self.problems(path)[0])

    def test_missing_file(self):
        """Отсутствующий файл конфигурации — ошибка."""
        missing = os.path.join(self.tmp.name, "nope.csv")
        self.assertIn("не найден", self.problems(missing)[0])

    def test_structure_errors(self):
        """Неизвестный, повторный, пропущенный ключ и лишний столбец."""
        path = self.write("package,curl\npackage,wget\ncolor,red\n"
                          "test_mode,false,extra\n")
        text = "\n".join(self.problems(path))
        self.assertIn("повторяется", text)
        self.assertIn("неизвестный параметр «color»", text)
        self.assertIn("столбца", text)
        self.assertIn("не задан обязательный параметр «max_depth»", text)

    def test_comments_and_blank_lines(self):
        """Комментарии и пустые строки пропускаются."""
        path = self.write_rows()
        with open(path, "a", encoding="utf-8") as stream:
            stream.write("\n# комментарий\n")
        self.assertEqual(load_config(path).package, "curl")

    def test_all_value_errors_reported(self):
        """Все ошибки значений сообщаются одновременно."""
        path = self.write_rows(output_image="g.png", ascii_tree="da",
                               max_depth="x")
        self.assertEqual(len(self.problems(path)), 3)

    def test_bad_mode_skips_dependent_checks(self):
        """При неверном test_mode пакет и источник не проверяются."""
        path = self.write_rows(test_mode="maybe")
        self.assertIn("не проверены", self.problems(path)[-1])

    def test_test_mode_with_file(self):
        """В тестовом режиме источник — существующий файл."""
        repo = os.path.join(self.tmp.name, "repo.txt")
        with open(repo, "w", encoding="utf-8") as stream:
            stream.write("A: B\n")
        config = load_config(self.write_rows(
            test_mode="true", package="A", repository=repo))
        self.assertTrue(config.test_mode)


class ValueParsersTest(unittest.TestCase):
    """Проверки отдельных параметров."""

    def test_parse_bool(self):
        """Логические значения в разных написаниях."""
        self.assertTrue(parse_bool("Yes"))
        self.assertFalse(parse_bool("0"))
        self.assertRaises(ValueError, parse_bool, "")

    def test_parse_component(self):
        """Допустимы только компоненты Ubuntu."""
        self.assertEqual(parse_component("restricted"), "restricted")
        for text in ("", "Main", "extra"):
            self.assertRaises(ValueError, parse_component, text)

    def test_parse_depth(self):
        """Глубина — целое число в допустимом диапазоне."""
        self.assertEqual(parse_depth("7"), 7)
        for text in ("0", "-1", "101", "2.5", ""):
            self.assertRaises(ValueError, parse_depth, text)

    def test_parse_image(self):
        """Имя файла изображения должно иметь расширение .svg."""
        self.assertEqual(parse_image("out.SVG"), "out.SVG")
        for text in ("", "out.png", ".svg", "a?.svg", "no_dir/x.svg"):
            self.assertRaises(ValueError, parse_image, text)

    def test_check_package(self):
        """Имя пакета проверяется по правилам выбранного режима."""
        self.assertEqual(check_package("libc6", False), "libc6")
        self.assertEqual(check_package("ABC", True), "ABC")
        for name, mode in (("", False), ("Curl", False), ("a", False),
                           ("curl", True), ("A1", True)):
            self.assertRaises(ValueError, check_package, name, mode)

    def test_check_repository(self):
        """URL должен использовать http или https и содержать хост."""
        url = "https://archive.ubuntu.com/ubuntu"
        self.assertEqual(check_repository(url, False), url)
        for source in ("", "ftp://host/x", "archive.ubuntu.com", "http://"):
            self.assertRaises(ValueError, check_repository, source, False)
        self.assertRaises(ValueError, check_repository, "nope.txt", True)


if __name__ == "__main__":
    unittest.main()
