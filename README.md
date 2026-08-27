# yandexdownload

Небольшой CLI для скачивания **одного файла из выбранной папки** публичного
Яндекс.Диска. По умолчанию он берёт ссылку из задания, папку `/` и только
первый файл (лимит `--max-files 1`), поэтому случайно не скачивает весь архив.
OAuth-токен не нужен.

## Быстрый запуск

Нужен Python 3.10+:

```bash
# посмотреть первый файл в папке Albums, ничего не скачивая
python3 yandex_download.py --folder 'Albums' --list

# скачать минимальный набор (один файл) в downloads/
python3 yandex_download.py --folder 'Albums'

# скачать до трёх файлов, но не больше 250 MiB
python3 yandex_download.py --folder 'Singles & EPs' \
  --max-files 3 --max-bytes $((250 * 1024 * 1024))
```

Папка назначения создаётся автоматически. Файлы скачиваются потоково через
временный `.part` и атомарно переименовываются после завершения; уже целый
файл того же размера пропускается. Имена и пути проверяются, чтобы содержимое
публичной папки не могло записаться за пределы `--output`.

## Как это работает

1. `GET /v1/disk/public/resources` получает метаданные и `_embedded.items`.
2. Каталоги обходятся рекурсивно, пока не набраны лимиты.
3. Для каждого файла выполняется `GET /v1/disk/public/resources/download`.
4. Полученный временный `href` используется для потоковой загрузки.

Решение основано на документации API и проверенных примерах из GitHub и
русскоязычных форумов. Важно кодировать `public_key`, `path` и не извлекать
имя файла простым разбором строки URL: имя может быть UTF-8 и содержать `&`.

Полезные источники:

- [Официальная документация Yandex Disk API: public files and folders](https://yandex.com/dev/disk/api/reference/public.html)
- [Пример обхода `_embedded.items` на Infostart](https://infostart.ru/1c/tools/945965/)
- [Обсуждение API и параметра `path` на Stack Overflow](https://ru.stackoverflow.com/questions/1554669/python-%D0%9A%D0%B0%D0%BA-%D0%BF%D0%BE%D0%BB%D1%83%D1%87%D0%B8%D1%82%D1%8C-%D1%81%D0%BF%D0%B8%D1%81%D0%BE%D0%BA-%D1%84%D0%B0%D0%B9%D0%BB%D0%BE%D0%B2-%D0%B2-%D1%87%D1%83%D0%B6%D0%BE%D0%B9-%D0%BF%D0%B0%D0%BF%D0%BA%D0%B5-%D0%AF%D0%BD%D0%B4%D0%B5%D0%BA%D1%81-%D0%94%D0%Bиск)
- [Пример Python-загрузчика на GitHub Gist](https://gist.github.com/Yegorov/dc61c42aa4e89e139cd8248f59af6b3e)

Сами аудиофайлы не добавляются в Git: для локальных результатов используйте
каталог `downloads/`.
