# naruto-nx 0.1.2 (test build)

Nintendo Switch homebrew port of *Naruto: Rise of a Ninja* (Xbox 360). Fan project, not affiliated with Ubisoft, Bandai
Namco, Microsoft or Nintendo. **The game's files are not included: you need your own copy of the game.**

## What is new

- **Fourth CPU core (optional).** Started from a HOME Menu forwarder with 4 CPU cores the port uses the fourth core for the
  audio mixer, the XMA decoder and the game's thread pool. On the console: no audio lag in Konoha, smoother play, +0.5–1.2 FPS
  at the heaviest spot of the village. Started from hbmenu it runs on three cores, as in 0.1.1.
- **Open-world performance work** (the game's draw queue without allocations, cheaper constants and binds, fewer
  empty draws, codegen: more registers as locals, native memcpy/memset/memmove, atomics without barriers). With the console
  overclocked (CPU 1785 / GPU 768 MHz) Konoha runs 27–30 FPS, its heaviest spot 27–28 FPS, and **fights run at 60 FPS**. The
  0.1.1 stock-clock figures (about 20 FPS in Konoha, 32–47 FPS in fights) were not measured again for this version.
- **Audio streaming** reads from a RAM cache (up to 1 GB, `sa2_io_ranges_mb`), a deeper output queue (14 frames).
- **The game's own anti-aliasing (4× MSAA) is off by default** (GPU −10–15 %, fewer dips). Set `naruto_guest_msaa_max = 0` in
  `naruto.toml` to turn it back on.
- **Experimental, off by default: `naruto_deko3d_record_worker = true`** moves the recording of the renderer's commands to a
  worker on another core. Written for the render thread, which is the limit in the open world; **not run on a console yet**.
  Try it only if you want to help test; report what you see.

## Installation

1. Open the installer page **https://malinkin-s.github.io/naruto-nx-installer/**, choose `default.xex` and `xeshader.sdb` of your
   own extracted disc, and extract the zip it makes to the root of the SD card. Copy your disc's files into
   `switch/naruto-nx/game/`.
2. Start `naruto.nro` from hbmenu (three cores), or make a HOME Menu forwarder (four cores): in [Sphaira](https://github.com/ITotalJustice/sphaira)
   select `naruto.nro`, install a forwarder with **CPU cores = 4** and **address space = 39-bit**, start the game from the new icon.
   `switch/naruto-nx/logs/rex/rex_profile.log` then says `process cores 4 (mask 0xF)`. The fourth core is shared with the HOME
   Menu, overlays and background services; long sessions are not tested much.

## Known issues

- Crashes when quitting are possible; the "Saved Game Warning" scroll border differs from the Xbox 360; the save thumbnail is
  black in Load Game; character DLC is not supported.
- Konoha at stock clocks is about 20 FPS; sound can stutter on three cores when the frame rate drops.
- The file range cache grows up to 1 GB with play; sessions of an hour or more have not been tested.

`naruto.nro` SHA-256: see `SHA256SUMS.txt`. Source: https://github.com/malinkin-s/naruto-rise-of-a-ninja-nx (GPL-3.0).

---

# naruto-nx 0.1.2 (тестовая сборка)

Порт *Naruto: Rise of a Ninja* (Xbox 360) на Nintendo Switch. Фанатский проект, не связан с Ubisoft, Bandai Namco, Microsoft и
Nintendo. **Файлов игры в сборке нет: нужна своя копия игры.**

## Что нового

- **Четвёртое ядро CPU (по желанию).** Если запустить из форвардера в HOME-меню с 4 ядрами, порт использует четвёртое ядро для
  звукового микшера, декодера XMA и пула потоков игры. На консоли: нет лага звука в Конохе, игра плавнее, +0.5–1.2 FPS в самом
  тяжёлом месте деревни. Из hbmenu порт работает на трёх ядрах, как 0.1.1.
- **Работа над производительностью открытого мира** (очередь draw'ов без аллокаций, дешевле константы и биндинги, меньше
  пустых draw'ов, кодогенерация: больше регистров в локальных переменных, нативные memcpy/memset/memmove, атомики без
  барьеров). На разогнанной консоли (CPU 1785 / GPU 768 МГц) Коноха идёт на 27–30 FPS, самое тяжёлое место — 27–28 FPS, а **бои — на 60 FPS**.
  Цифры 0.1.1 на стандартных частотах (около 20 FPS в Конохе, 32–47 FPS в боях) для этой версии заново не измерялись.
- **Стриминг звука** читается из кэша в RAM (до 1 ГБ, `sa2_io_ranges_mb`), очередь вывода глубже (14 кадров).
- **Сглаживание самой игры (4× MSAA) по умолчанию выключено** (GPU −10–15%, меньше просадок). Чтобы вернуть, поставьте
  `naruto_guest_msaa_max = 0` в `naruto.toml`.
- **Экспериментально, по умолчанию выключено: `naruto_deko3d_record_worker = true`** переносит запись команд рендерера на
  рабочий поток на другом ядре. Сделано для render thread, который в открытом мире является пределом; **на консоли ещё не
  запускалось**. Включайте, только если хотите помочь с проверкой, и напишите, что увидели.

## Установка

1. Откройте страницу-установщик **https://malinkin-s.github.io/naruto-nx-installer/**, выберите `default.xex` и `xeshader.sdb`
   вашего распакованного диска и распакуйте полученный zip в корень SD-карты. Скопируйте файлы диска в `switch/naruto-nx/game/`.
2. Запустите `naruto.nro` из hbmenu (три ядра) или сделайте форвардер в HOME-меню (четыре ядра): в [Sphaira](https://github.com/ITotalJustice/sphaira)
   выберите `naruto.nro`, установите форвардер с **CPU cores = 4** и **address space = 39-bit**, запускайте игру новым значком.
   В `switch/naruto-nx/logs/rex/rex_profile.log` будет `process cores 4 (mask 0xF)`. Четвёртое ядро делится с HOME-меню,
   оверлеями и фоновыми службами; долгие сеансы проверены мало.

## Известные проблемы

- Возможны вылеты при выходе; рамка свитка «Saved Game Warning» отличается от Xbox 360; миниатюра сохранения чёрная в Load
  Game; DLC с персонажами не поддерживается.
- Коноха на стандартных частотах — около 20 FPS; на трёх ядрах звук может заикаться, когда падает частота кадров.
- Кэш диапазонов файлов растёт до 1 ГБ по ходу игры; сеансы в час и дольше не проверялись.

SHA-256 `naruto.nro` — в `SHA256SUMS.txt`. Исходники: https://github.com/malinkin-s/naruto-rise-of-a-ninja-nx (GPL-3.0).
