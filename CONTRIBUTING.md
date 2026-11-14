# Contributing

Нужны Python 3.10+ и Blender 5+. Внешних Python-зависимостей нет.
Основной код аддона находится в `blocksmith/`, CLI — в `tools/`,
примеры спецификаций — в `examples/`, проверки — в `tests/`.

Из корня проекта:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q blocksmith tools tests
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/outline_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/outline_interaction_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/file_pause_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/free_placement_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/guard_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/guard_scope_check.py
blender -b -noaudio --factory-startup --python-exit-code 1 --python tests/blender_check.py
python3 tests/cli_guard_check.py
python3 tools/package.py
```

GitHub Actions запускает обычные Python-тесты, проверяет синтаксис и собирает ZIP.
Blender-проверки запускаются локально в отдельном процессе с пустой сценой;
проверки `*_viewport_check.py` требуют графического окружения.

`outline_viewport_check.py` проверяет настоящий GPU-предпросмотр, модальный цикл и
Undo/Redo в работающем Blender с включённым Blocksmith. События подаются через
реальную проекцию вьюпорта; нативный таймер завершает обработчик Window Manager.
Проверка временно включает глобальную историю, затем восстанавливает настройку.

Для изменения геометрии или ограничений добавьте небольшой сценарий,
проверяющий поведение, и запустите связанные Blender-проверки.
В pull request опишите изменение поведения и выполненные проверки.
Исходники распространяются под GPL-3.0-or-later; лицензии сторонних
ресурсов сохраняются рядом с ними.

ZIP создаётся в `dist/` и содержит manifest на верхнем уровне,
готовый для **Install from Disk** в Blender. В GitHub Release прикладывайте
этот ZIP. Архив исходников GitHub сам по себе не является установочным архивом.
Резервные копии, сборки, экспортированные сцены и локальные заметки
не включаются в Git; исходные примеры и ресурсы аддона включаются.
