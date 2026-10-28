# naruto-nx 0.1.3 (playable test build)

Nintendo Switch homebrew port of *Naruto: Rise of a Ninja* (Xbox 360). Fan project, not affiliated with Ubisoft, Bandai
Namco, Microsoft or Nintendo. **The game's files are not included: you need your own copy of the game.**

**Status: playable, and still a test build.** The story mode and fights play on a real console; further testing is
needed to find bugs, crashes and so on. Please report what you meet.

## Performance

With the console overclocked by hand (CPU 1785 MHz, GPU 768 MHz), handheld, render resolution 480p
(`sa2_render_height_handheld = 480` in `naruto.toml`):

- **Fights: 60 FPS** (the game's own rate in fights), with rare dips.
- **Story mode: about 30 FPS** (the game's own rate in the open world) with rare dips, in the part of Konoha played so far.

At stock clocks the 0.1.1 figures stand (about 20 FPS in Konoha, 32–47 FPS in fights at 720p, 46–58 FPS at 480p); they
were not measured again.

## What is new since 0.1.2

- **Profile-guided optimisation (PGO) and link-time optimisation (LTO).** The NRO is built with the profile of a console
  session (branch counters, no code or game data: `pgo/` in the repository) and the game code and the app are optimised as one
  program. At the same scene load the render thread uses about 21 % less CPU time a frame than in 0.1.2's plain build
  (3500 draws a frame), and the game's drawing thread about 17 %, the main thread about 7 %.
- **The NRO has the game's icon** (hbmenu, and the HOME Menu forwarder you make from it). The icon is also attached as
  `naruto-nx-icon.jpg`.
- Settings of 0.1.2 stay: the fourth CPU core with a HOME Menu forwarder, render resolution in `naruto.toml`, the game's
  anti-aliasing off by default, `naruto_deko3d_record_worker` experimental and off (measured slower).

## Installation

1. Open the installer page **https://malinkin-s.github.io/naruto-nx-installer/**, choose `default.xex` and `xeshader.sdb` of your
   own extracted disc, and extract the zip it makes to the root of the SD card. Copy your disc's files into
   `switch/naruto-nx/game/`.
2. Start `naruto.nro` from hbmenu (three cores), or make a HOME Menu forwarder (four cores, better sound and smoother play): in
   [Sphaira](https://github.com/ITotalJustice/sphaira) select `naruto.nro`, install a forwarder with **CPU cores = 4** and
   **address space = 39-bit**, start the game from the new icon. `switch/naruto-nx/logs/rex/rex_profile.log` then says
   `process cores 4 (mask 0xF)`. The fourth core is shared with the HOME Menu, overlays and background services; long sessions
   are not tested much.
3. For the figures above: overclock the console by hand (CPU 1785 MHz, GPU 768 MHz) and set `sa2_render_height_handheld = 480`
   in `switch/naruto-nx/naruto.toml` (written at the first start).

## Known issues

- Crashes when quitting are possible; the save thumbnail is black in Load Game; character DLC is not supported.
- Konoha at stock clocks is about 20 FPS; sound can stutter on three cores when the frame rate drops.
- The file range cache grows up to 1 GB with play; sessions of an hour or more have not been tested.

Files: `naruto.nro`, `naruto-nx-icon.jpg`, `SHA256SUMS.txt`. Source: https://github.com/malinkin-s/naruto-rise-of-a-ninja-nx (GPL-3.0).

---

# naruto-nx 0.1.3 (играбельная тестовая сборка)

Порт *Naruto: Rise of a Ninja* (Xbox 360) на Nintendo Switch. Фанатский проект, не связан с Ubisoft, Bandai Namco, Microsoft и
Nintendo. **Файлов игры в сборке нет: нужна своя копия игры.**

**Статус: играбельно, но это всё ещё тестовая сборка.** Сюжетный режим и бои играются на настоящей консоли; нужно дальнейшее
тестирование, чтобы выявить баги, вылеты и прочее. Пишите, с чем столкнётесь.

## Производительность

На консоли, разогнанной вручную (CPU 1785 МГц, GPU 768 МГц), в портативе, разрешение рендера 480p
(`sa2_render_height_handheld = 480` в `naruto.toml`):

- **Бои: 60 FPS** (родная частота боёв) с редкими просадками.
- **Сюжетный режим: около 30 FPS** (родная частота открытого мира) с редкими просадками, в той части Конохи, где играли.

На стандартных частотах остаются цифры 0.1.1 (около 20 FPS в Конохе, 32–47 FPS в боях в 720p, 46–58 FPS в 480p); заново они
не измерялись.

## Что нового по сравнению с 0.1.2

- **Оптимизация по профилю (PGO) и на этапе линковки (LTO).** NRO собран по профилю сеанса на консоли (счётчики ветвлений, без
  кода и данных игры: `pgo/` в репозитории), игровой код и приложение оптимизируются как одна программа. При той же нагрузке
  сцены render thread тратит примерно на 21% меньше процессорного времени на кадр, чем в обычной сборке 0.1.2 (3500 draw'ов на
  кадр), поток отправки draw'ов игры — на 17%, главный поток — на 7%.
- **У NRO есть иконка игры** (в hbmenu и у форвардера в HOME-меню, который вы из него делаете). Иконка приложена и отдельным
  файлом `naruto-nx-icon.jpg`.
- Остаются настройки 0.1.2: четвёртое ядро с форвардером в HOME-меню, разрешение рендера в `naruto.toml`, сглаживание игры по
  умолчанию выключено, `naruto_deko3d_record_worker` экспериментальный и выключен (измерен медленнее).

## Установка

1. Откройте страницу-установщик **https://malinkin-s.github.io/naruto-nx-installer/**, выберите `default.xex` и `xeshader.sdb`
   вашего распакованного диска и распакуйте полученный zip в корень SD-карты. Скопируйте файлы диска в `switch/naruto-nx/game/`.
2. Запустите `naruto.nro` из hbmenu (три ядра) или сделайте форвардер в HOME-меню (четыре ядра: звук чище, игра плавнее): в
   [Sphaira](https://github.com/ITotalJustice/sphaira) выберите `naruto.nro`, установите форвардер с **CPU cores = 4** и
   **address space = 39-bit**, запускайте игру новым значком. В `switch/naruto-nx/logs/rex/rex_profile.log` будет
   `process cores 4 (mask 0xF)`. Четвёртое ядро делится с HOME-меню, оверлеями и фоновыми службами; долгие сеансы проверены мало.
3. Для цифр выше: разгоните консоль вручную (CPU 1785 МГц, GPU 768 МГц) и поставьте `sa2_render_height_handheld = 480` в
   `switch/naruto-nx/naruto.toml` (файл создаётся при первом запуске).

## Известные проблемы

- Возможны вылеты при выходе; миниатюра сохранения чёрная в Load Game; DLC с персонажами не поддерживается.
- Коноха на стандартных частотах — около 20 FPS; на трёх ядрах звук может заикаться, когда падает частота кадров.
- Кэш диапазонов файлов растёт до 1 ГБ по ходу игры; сеансы в час и дольше не проверялись.

Файлы: `naruto.nro`, `naruto-nx-icon.jpg`, `SHA256SUMS.txt`. Исходники: https://github.com/malinkin-s/naruto-rise-of-a-ninja-nx (GPL-3.0).
