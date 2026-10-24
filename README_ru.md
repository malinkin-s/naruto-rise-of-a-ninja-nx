<p align="center">
  <img src="docs/media/banner_ru.svg" alt="Naruto: Rise of a Ninja — порт на Nintendo Switch" width="100%">
</p>

<p align="center">
  <a href="README.md">English</a> · <b>Русский</b>
</p>

<p align="center">
  <img alt="состояние" src="docs/media/badge_status_ru.svg" height="32">&nbsp;
  <img alt="платформа" src="docs/media/badge_platform_ru.svg" height="32">&nbsp;
  <img alt="рендерер" src="docs/media/badge_renderer_ru.svg" height="32">&nbsp;
  <img alt="лицензия" src="docs/media/badge_licence_ru.svg" height="32">
</p>

Порт **Naruto: Rise of a Ninja** (Ubisoft Montreal, 2007, эксклюзив Xbox 360) на Nintendo Switch в виде homebrew NRO.
PowerPC-код игры статически перекомпилирован с [ReXGlue](https://github.com/rexglue/rexglue-sdk). GPU Xbox 360 не эмулируется:
вызовы Direct3D рисует Renut, рендерер уровня Direct3D, на deko3d — родном графическом API Switch.

> [!IMPORTANT]
> Порт в разработке. Игра запускается на консоли и доходит до боя, но работает медленно, играть пока рано. Релизов
> ещё нет. В репозитории нет игровых данных и кода, полученного из них: нужна своя копия игры.

## Состояние

**Этап 6 (Switch), на 2026-10-24.** NRO работает на настоящей консоли: логотипы, меню, загрузка сохранения и целый
бой с правильной картинкой. Следующая цель — частота кадров.

| Что | Switch | Подробности |
|---|---|---|
| Запуск, логотипы Scaleform, меню | **Работает** | 24–29 FPS в меню |
| Сохранения на SD-карте | **Работают** | Создаются, видны в списке, загружаются (`sdmc:/switch/naruto-nx/`) |
| Бои | **Работают, медленно** | Картинка верная, артефактов не замечено; 15–25 FPS (бои в игре идут на 60) |
| Открытый мир (первая сцена сюжета) | **Рисуется, медленно** | ~7 FPS; один раз замечены артефакты, разбираемся |
| Видео Bink (ролики) | Проверено частично | Вступление играет; сюжетные ролики ещё проверить |
| Геймпад | Проверен записанным вводом | Автотесты нажимают кнопки; долгая игра руками впереди |
| Звук | Не проверен | |
| DLC с персонажами (3 доп. движка) | Пока нет | За опцией CMake, после замеров памяти |
| Оптимизация | Не начата | Нет LTO/PGO, нет готового кэша шейдеров, включены отладочные логи |

На PC (Linux, тот же код с Renut на Vulkan) работают вступление, меню, Коноха с жителями, диалоги, обучение, бой и
сохранения (пишутся и загружаются обратно), 30 FPS.

### Что пришлось решить

- **Direct3D старше, чем в любом прежнем порте на Renut** (XDK 2.0.6274, LTCG): приватная раскладка устройства,
  функции и смещения найдены по рендереру PC-рекомпиляции ([docs/d3d-census.md](docs/d3d-census.md),
  [docs/renut-retarget.md](docs/renut-retarget.md)).
- **3 322 шейдера игры** из `xeshader.sdb` переведены цепочкой XenosRecomp → DXC → SPIRV-Cross → uam для deko3d.
- **Тайловый рендеринг**: 3D-сцена рисуется тремя тайлами 1280×256 с 4× MSAA (EDRAM Xbox 360); цели Renut теперь
  покрывают все тайлы.
- **Движок игры `ai2c.dll`** влинкован в NRO статическим модулем.
- **Автотесты на консоли через nxlink** (`tools/switch/nxtest.sh`): игра работает заданное время, шлёт на PC лог и
  кадры рендерера и сама выходит.

Полная история с доказательствами каждого шага — в [docs/port-journal.md](docs/port-journal.md) (на английском).

## Скриншоты

Сняты с рендерера на Nintendo Switch (половинный размер, 640×360) в автоматическом прогоне 2026-10-24.

<table>
  <tr>
    <td><img src="docs/media/switch_menu.jpg" alt="Меню одиночной игры"></td>
    <td><img src="docs/media/switch_jutsu_select.jpg" alt="Список техник"></td>
  </tr>
  <tr>
    <td align="center"><sub>Меню одиночной игры</sub></td>
    <td align="center"><sub>Список техник перед боем</sub></td>
  </tr>
  <tr>
    <td><img src="docs/media/switch_versus.jpg" alt="Наруто против Саске"></td>
    <td><img src="docs/media/switch_fight.jpg" alt="Арена"></td>
  </tr>
  <tr>
    <td align="center"><sub>Заставка матча</sub></td>
    <td align="center"><sub>Лесная арена</sub></td>
  </tr>
  <tr>
    <td><img src="docs/media/switch_fight_close.jpg" alt="Бой крупно"></td>
    <td><img src="docs/media/switch_fight_jutsu.jpg" alt="Техника в бою"></td>
  </tr>
  <tr>
    <td align="center"><sub>Наруто и Саске</sub></td>
    <td align="center"><sub>Подсказка техники</sub></td>
  </tr>
  <tr>
    <td><img src="docs/media/switch_rasengan.jpg" alt="Вставка техники"></td>
    <td><img src="docs/media/switch_scaleform.jpg" alt="Логотип Scaleform"></td>
  </tr>
  <tr>
    <td align="center"><sub>Вставка техники</sub></td>
    <td align="center"><sub>Логотипы при запуске</sub></td>
  </tr>
</table>

## Из чего собран

| Часть | Откуда |
|---|---|
| Перекомпилированный код | ReXGlue SDK, форк [sa2-nx](https://github.com/ChanseyIsTheBest/sa2-nx) (слой Horizon, статические гостевые модули) |
| PC-основа и справочник | [jorjbarbosa/naruto-rise-recomp](https://github.com/jorjbarbosa/naruto-rise-recomp): seeds, хуки, карта Direct3D |
| Рендерер | Renut (masterspike52) на deko3d-бэкенде plume, из sa2-nx, перенацелен на Direct3D Naruto |
| Тулчейн | devkitA64 (GCC 16.1) в Docker, libnx, deko3d |

### Сборка (в общих чертах)

Нужны свои файлы игры в `game/` (распакованный диск, `default.xex` в корне).

```bash
python3 tools/fetch_thirdparty.py           # сторонние исходники SDK
tools/fetch_renut_deps.sh                   # plume, XenosRecomp, uam, imgui (из sa2-nx)
# собрать хостовый rexglue (sdk/, cmake --preset linux-amd64), затем:
rexglue codegen app/naruto_manifest.toml    # перекомпилированный код в app/generated/ (не коммитится)
tools/deko3d_build_tools.sh                 # SPIRV-Cross и uam для цепочки шейдеров
tools/switch/host_shaders.sh                # служебные шейдеры Renut для deko3d
tools/switch/build.sh                       # out/nx/naruto.nro
tools/switch/package.sh                     # out/nx/sdcard/ -> скопировать на SD-карту
```

На консоли запустите hbmenu в режиме title override (удерживая R при запуске игры — для полной памяти) и выберите
Naruto: Rise of a Ninja.

## Благодарности

- [jorjbarbosa/naruto-rise-recomp](https://github.com/jorjbarbosa/naruto-rise-recomp) — PC-рекомпиляция, на которой
  стоит порт.
- [sa2-nx](https://github.com/ChanseyIsTheBest/sa2-nx) — шаблон для Switch, форк SDK и Renut на deko3d.
- Renut (masterspike52); plume; XenosRecomp; uam; deko3d и libnx от команд devkitPro и switchbrew.
- [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk).

## Лицензия и оговорка

GPL-3.0, см. [LICENSE](LICENSE). Фанатский проект, не связан с Ubisoft, Bandai Namco, Shueisha, Microsoft и Nintendo
и не одобрен ими. *Naruto* и материалы игры принадлежат их владельцам. Файлы игры здесь не распространяются: соберите
порт из своей копии игры.
