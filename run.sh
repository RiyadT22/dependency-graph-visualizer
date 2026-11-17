#!/bin/sh
# Запуск: ./run.sh [config.csv]   Тесты: ./run.sh test
cd "$(dirname "$0")" || exit 1
export PYTHONPATH="$PWD/src"
if [ "$1" = "test" ]; then
    exec python3 -m unittest discover -s tests -v
fi
exec python3 -m depgraph "$@"
