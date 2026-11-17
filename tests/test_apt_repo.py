"""Тесты получения и разбора индекса пакетов apt (этап 2)."""

import gzip
import io
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

from depgraph.apt_repo import (RepositoryError, decode_index,
                               direct_dependencies, download_index,
                               index_url, iter_stanzas, load_index,
                               parse_depends, parse_index)

SAMPLE_INDEX = """\
Package: curl
Version: 8.5.0-2ubuntu10
Depends: libc6 (>= 2.34), libcurl4t64 (= 8.5.0-2ubuntu10), zlib1g (>= 1:1.1)
Description: command line tool
 continuation line: not a field

Package: tar
Pre-Depends: libc6 (>= 2.38)
Depends: libacl1 (>= 2.2.23)

Package: base-files
Version: 13ubuntu10
"""


def fake_response(data):
    """Создать объект, имитирующий ответ urlopen."""
    return mock.MagicMock(
        __enter__=mock.Mock(return_value=io.BytesIO(data)),
        __exit__=mock.Mock(return_value=False))


class ParseDependsTest(unittest.TestCase):
    """Разбор поля зависимостей."""

    def test_versions_removed(self):
        """Ограничения версий отбрасываются, в том числе с эпохой."""
        self.assertEqual(parse_depends("libc6 (>= 2.34), zlib1g (>= 1:1.1)"),
                         ["libc6", "zlib1g"])

    def test_first_alternative(self):
        """Из альтернатив выбирается первая."""
        self.assertEqual(parse_depends("base-passwd (>= 3.6) | adduser, a1"),
                         ["base-passwd", "a1"])

    def test_qualifiers_removed(self):
        """Квалификатор :any, архитектуры и профили удаляются."""
        self.assertEqual(
            parse_depends("python3:any, libfoo [amd64] <!nocheck>"),
            ["python3", "libfoo"])

    def test_duplicates_and_empty(self):
        """Повторы исключаются, пустое поле даёт пустой список."""
        self.assertEqual(parse_depends("git-man (>> 1), git-man (<< 2)"),
                         ["git-man"])
        self.assertEqual(parse_depends(""), [])


class ParseIndexTest(unittest.TestCase):
    """Разбор файла Packages."""

    def test_stanzas(self):
        """Записи разделяются пустыми строками, продолжения склеиваются."""
        stanzas = list(iter_stanzas(SAMPLE_INDEX))
        self.assertEqual([s["Package"] for s in stanzas],
                         ["curl", "tar", "base-files"])
        self.assertIn("continuation", stanzas[0]["Description"])

    def test_index(self):
        """Учитываются поля Pre-Depends и Depends."""
        index = parse_index(SAMPLE_INDEX)
        self.assertEqual(index["curl"], ["libc6", "libcurl4t64", "zlib1g"])
        self.assertEqual(index["tar"], ["libc6", "libacl1"])
        self.assertEqual(index["base-files"], [])

    def test_empty_index(self):
        """Пустой индекс — ошибка."""
        self.assertRaises(RepositoryError, parse_index, "\n\n")

    def test_direct_dependencies(self):
        """Поиск пакета в индексе."""
        index = parse_index(SAMPLE_INDEX)
        self.assertEqual(direct_dependencies(index, "tar"),
                         ["libc6", "libacl1"])
        self.assertRaises(RepositoryError, direct_dependencies, index, "vim")


class DownloadTest(unittest.TestCase):
    """Формирование URL, загрузка и распаковка индекса."""

    def test_index_url(self):
        """Корень зеркала дополняется путём к индексу noble/main/amd64."""
        self.assertEqual(
            index_url("http://host/ubuntu/"),
            "http://host/ubuntu/dists/noble/main/binary-amd64/Packages.gz")
        direct = "http://host/x/Packages"
        self.assertEqual(index_url(direct), direct)

    def test_decode_gzip_and_plain(self):
        """Поддерживаются сжатый и несжатый индекс."""
        data = SAMPLE_INDEX.encode("utf-8")
        self.assertEqual(decode_index(gzip.compress(data), "u"), SAMPLE_INDEX)
        self.assertEqual(decode_index(data, "u"), SAMPLE_INDEX)

    def test_decode_errors(self):
        """Повреждённый архив и не-UTF-8 данные — ошибки."""
        broken = gzip.compress(b"data")[:-4]
        self.assertRaises(RepositoryError, decode_index, broken, "u")
        self.assertRaises(RepositoryError, decode_index, b"\xff\xfe", "u")

    @mock.patch("depgraph.apt_repo.urlopen")
    def test_load_index(self, urlopen):
        """Индекс загружается по URL и разбирается."""
        urlopen.return_value = fake_response(
            gzip.compress(SAMPLE_INDEX.encode("utf-8")))
        index = load_index("http://host/ubuntu")
        self.assertIn("curl", index)

    @mock.patch("depgraph.apt_repo.urlopen")
    def test_network_errors(self, urlopen):
        """Сетевые ошибки и HTTP-ошибки превращаются в RepositoryError."""
        errors = (HTTPError("u", 404, "Not Found", None, None),
                  URLError("getaddrinfo failed"), TimeoutError("timed out"))
        for error in errors:
            urlopen.side_effect = error
            with self.assertRaises(RepositoryError):
                download_index("http://host/Packages.gz")


if __name__ == "__main__":
    unittest.main()
