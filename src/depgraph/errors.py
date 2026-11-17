"""Исключения, общие для модулей приложения."""


class RepositoryError(Exception):
    """Ошибка загрузки репозитория или поиска пакета в нём."""


class VisualizationError(Exception):
    """Ошибка построения изображения графа."""
