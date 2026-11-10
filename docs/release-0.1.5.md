# naruto-nx 0.1.5 (playable test build)

> [!NOTE]
> Historical release notes. For the current engineering state, verified baseline metrics and corrected claims (including the reversion of 135m modular culling due to sky plane flicker and stationary vs segment-mean FPS), refer to [STATE.md](../STATE.md) §Corrected claims.

Nintendo Switch homebrew port of *Naruto: Rise of a Ninja* (Ubisoft Montreal, 2007, Xbox 360). Fan project, not affiliated with Ubisoft, Bandai Namco, Microsoft or Nintendo. The game's files are not included: you need your own copy of the game.

**Status: playable test build.** Measured on a Nintendo Switch in handheld mode on stock clocks (CPU 1020 MHz, GPU 460 MHz, RAM 1600 MHz) at native 720p.

## Performance Status

- **Open-world Konoha (Leaf Village, Story mode): 30 FPS reached in stationary vista on stock clocks (1020/460 MHz)** at native 720p (up from 25–28 FPS in 0.1.4 and ~20 FPS in 0.1.1/0.1.3). Measured median frame interval in pilot spot p50 = **33.39 ms** (target 33.33 ms). Dynamic movement routes across the full village remain under test.
- **CPU Allocator Bottleneck Eliminated:** Memory allocation overhead in `sub_82180568` (`MmAllocatePhysicalMemoryEx` / `AllocRange`) collapsed from **31.5% down to 1.6% of running samples** (a 95% reduction in allocator CPU time). `BaseHeap::AllocRange` completely vanished from the top-30 CPU profile.
- **Draw Calls & GPU Margin:** Modular static world culling distance tuned to 135m (`naruto_max_view_distance`), reducing draw calls from ~1,955 to ~1,518 (-437 draws/frame, -22%). Freed ~5.0 ms of CPU render thread time and ~4.1 ms of GPU time, eliminating GPU fillrate saturation.

## What is new in 0.1.5

- **64-bit Free-Page Bitmap (`heap_free_bitmap`):** Replaced the 131,072-entry linear page table scan in `BaseHeap::AllocRange` with an L1-resident 16 KB 64-bit bitmap (`free_bits_`). Page range search now scans 64 physical pages per clock cycle using hardware `__builtin_ctzll`.
- **Kernel Physical Memory Pool (`kernel_physical_pool`):** Implemented an in-memory pool (up to 16 MB) for unconstrained physical allocations. Frame-cyclic physical allocations are reused instantly without acquiring heap locks, scanning page tables, or issuing Horizon OS memory mapping syscalls.
- **Modular World Culling Tuning (`sub_820FD5F8`):** Fine-tuned static geometry culling threshold to 135.0m via `naruto_max_view_distance`, cutting off distant unseen meshes while maintaining full scene aesthetics and skydome integrity.
- **In-Game Diagnostic Overlay & Measurement Hotkey:** Added instant profiling trigger via gamepad shortcut **`L + R + Minus`** (or F8 / `M` on keyboard). Added a lightweight HUD indicator (`[● REC]`) during active measurement windows.
- **Automated Console Diagnostic Pipeline:** Added `tools/switch/ftp_run_summary.py` for automated compact Markdown report generation directly from console FTP sessions without keeping full logs in repository context.

## Installation

1. Open the web installer: **https://malinkin-s.github.io/naruto-nx-installer/**
2. Select `default.xex` and `xeshader.sdb` from your extracted game disc, and extract the resulting zip to the root of your SD card.
3. Copy your game files to `switch/naruto-nx/game/` (so that `switch/naruto-nx/game/default.xex` exists).
4. **Recommended: Make a HOME Menu forwarder via Sphaira** (CPU cores = 4, address space = 39-bit) for best audio stability and performance.
   *Or start the Homebrew Menu by holding **R** while starting any game (title override: full memory, three cores).*

---

# naruto-nx 0.1.5 (играбельная тестовая сборка)

Порт Naruto: Rise of a Ninja (Ubisoft Montreal, 2007, Xbox 360) для Nintendo Switch. Фанатский проект, не связан с Ubisoft, Bandai Namco, Microsoft и Nintendo. Файлов игры в релизе нет: требуется ваша собственная копия игры.

**Состояние: играбельная тестовая сборка.** Замеры проводились на Nintendo Switch в портативном режиме на стандартных стоковых частотах (CPU 1020 МГц, GPU 460 МГц, RAM 1600 МГц) в нативном разрешении 720p.

## Статус производительности

- **Сюжетный режим (Коноха, открытый мир): Достигнуты 30 FPS в тестовом ракурсе деревни на стоковых частотах (1020/460 МГц)** в нативном разрешении 720p (рост с 25–28 FPS в 0.1.4 и ~20 FPS в 0.1.1/0.1.3). Зафиксированный медианный интервал кадров в пилотной точке p50 = **33.39 мс** (целевое значение: 33.33 мс). Поведение в динамике и на маршрутах движения по деревне находится в процессе тестирования.
- **Устранено узкое место аллокатора на CPU:** Время CPU в `sub_82180568` (`MmAllocatePhysicalMemoryEx` / `AllocRange`) сократилось с **31.5% до 1.6% сэмплов** (снижение накладных расходов аллокатора на 95%). `BaseHeap::AllocRange` полностью исчез из топ-30 профиля CPU.
- **Снижение Draw Calls и разгрузка GPU:** Дистанция отсечения модульной геометрии мира скорректирована до 135м (`naruto_max_view_distance`), что снизило количество вызовов отрисовки с ~1955 до ~1518 (-437 draws/кадр, -22%). Освобождено ~5.0 мс на рендер-потоке CPU и ~4.1 мс на GPU.

## Что нового в 0.1.5

- **64-битный Free-Page Bitmap (`heap_free_bitmap`):** Линейный перебор 131 072 записей таблицы страниц в `BaseHeap::AllocRange` заменен на 16 КБ 64-битный битовый массив (`free_bits_`), помещающийся в L1-кэш процессора. Поиск свободных страниц теперь проверяет по 64 страницы за инструкцию через `__builtin_ctzll`.
- **Пул физической памяти ядра (`kernel_physical_pool`):** Реализован быстрый кэш-пул (до 16 МБ) для неконстрейненных физических аллокаций. Циклические покадровые блоки памяти переиспользуются мгновенно без захвата глобальных блокировок кучи, сканирования страниц и системных вызовов маппинга памяти Horizon OS.
- **Тюнинг дистанционного куллинга геометрии (`sub_820FD5F8`):** Порог отсечения модульной статической геометрии выставлен в 135.0м через параметр `naruto_max_view_distance`.
- **Внутриигровой оверлей и хоткей замеров:** Добавлен запуск профилирования по комбинации кнопок геймпада **`L + R + Minus`** (или клавиши F8 / `M` на клавиатуре). Во время активного замера на экране отображается компактный индикатор `[● REC]`.
- **Автоматизация обработки логов консоли:** Добавлен скрипт `tools/switch/ftp_run_summary.py` для формирования компактных отчетов по прогонам напрямую с FTP консоли без засорения репозитория «сырыми» логами.

## Установка

1. Откройте онлайн-установщик: **https://malinkin-s.github.io/naruto-nx-installer/**
2. Выберите `default.xex` и `xeshader.sdb` от вашего распакованного диска и распакуйте сгенерированный zip в корень SD-карты.
3. Скопируйте файлы диска в `switch/naruto-nx/game/` (чтобы появился файл `switch/naruto-nx/game/default.xex`).
4. **Рекомендуется создать форвардер через Sphaira** (CPU cores = 4, address space = 39-bit) для наилучшей стабильности звука и производительности.
   *Или запустите Homebrew Menu, удерживая кнопку **R** при запуске любой игры.*
