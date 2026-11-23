#!/usr/bin/env bash
# Запуск из готовой сборки (Linux). Сборка не требуется.
cd "$(dirname "$0")"
export PYSCHOOL_LIB_DIR="$PWD/lib"
./bin/statusproxy_cpp 8081 &
PROXY=$!
python3 src/python/server.py 8080 &
SERVER=$!
echo "Сайт: http://$(hostname -I 2>/dev/null | awk '{print $1}'):8080/  (admin/admin, 123456/123456)"
echo "Статус-панель: http://localhost:8081/"
trap "kill $PROXY $SERVER 2>/dev/null" INT TERM
wait
