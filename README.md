# anim2d: мінімалістичні 2D-анімації з коду

Інструмент для коротких 2D-роликів у «мотиваційному» мінімалістичному стилі: темна палітра,
простий персонаж, лічильник днів «DAY N», титри поверх кадру, монтаж «день за днем».

Що він уміє:

1. **Рендерити відео зі сценарію.** Ви описуєте сцени в YAML-файлі, а програма малює кадри і збирає MP4.
2. **Аналізувати готове відео.** Знаходить зміни сцен, ключові кадри, яскравість і палітру
   та збирає контактний аркуш. Зручно, щоб розкласти референс перед тим, як писати свій сценарій.

Головний герой — оригінальний персонаж **Піп**: голова-яйце з паростком і синє худі.

## Встановлення

Потрібні Python 3.10+ та [ffmpeg](https://ffmpeg.org/download.html).

```bash
git clone <url-цього-репозиторію> && cd You
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Швидкий старт

```bash
# повне відео (≈25 с, рендер ≈40 с)
python -m anim2d render examples/morning_run.yaml -o out/morning_run.mp4

# швидкий чорновик: пів роздільності, 12 fps
python -m anim2d render examples/morning_run.yaml -o out/draft.mp4 --draft

# один кадр, щоб швидко перевірити композицію
python -m anim2d preview examples/morning_run.yaml -t 18 -o out/frame.png

# розкадровка: по одному кадру з кожної сцени
python -m anim2d sheet examples/morning_run.yaml -o out/storyboard.png

# аналіз будь-якого відео
python -m anim2d analyze my_video.mp4 -o out/analysis
#   → out/analysis/contact_sheet.png  (кадри з мітками часу, ✂ = зміна сцени)
#   → out/analysis/report.json        (метадані, монтажні склейки, яскравість, палітра)

python -m anim2d scenes   # список типів сцен
```

## Формат сценарію

```yaml
video:
  width: 1280        # будь-яка роздільність; сцени масштабуються автоматично
  height: 720
  fps: 24
  supersample: 2     # згладжування країв (1 = швидше)
  audio: music.mp3   # необов'язково

scenes:
  - type: bedroom          # тип сцени
    duration: 4            # секунди
    day: 1                 # лічильник «DAY 1»
    day_style: big         # small | big
    clock: "5:30"
    ringing: true
    expression: determined
    fade_in: 0.5           # перехід із чорного
    captions:
      - {text: "Цього разу — по-справжньому.", start: 1, end: 3.8}

  - type: city_run
    duration: 7
    day: [4, 30]           # [від, до] — значення анімується протягом сцени
    light: [0.0, 0.55]     # ніч → світанок
```

Будь-який числовий параметр можна задати як `[від, до]`, і він плавно зміниться протягом сцени.

### Сцени

| Тип        | Параметри |
|------------|-----------|
| `title`    | `text`, `subtitle`, `size`, `bg`, `color` |
| `bedroom`  | `clock`, `ringing`, `action` (`stare`/`sleep`), `expression`, `light`, `tilt`, `look` |
| `mirror`   | `expression`, `critic_color` («внутрішній критик» у дзеркалі) |
| `city_run` | `light`, `speed`, `cadence`, `expression`, `x`, `seed` |

**Емоції персонажа:** `neutral`, `determined`, `tired`, `happy`, `sad`, `sleeping`.

**Титри** (`captions`): `text`, `start`, `end`, `pos` (`top`/`center`/`bottom`/число),
`size`, `color`, `fade`, `typewriter: true` (ефект друкарської машинки), `cps`.

**Спільні параметри сцени:** `duration`, `day`, `day_style`, `fade_in`, `fade_out`.

## Структура

```
anim2d/
  canvas.py     полотно: логічні координати 1280×N, суперсемплінг, текст, 7-сегментні цифри
  character.py  персонаж Піп: пози standing / running / head, емоції, кліпання
  scenes.py     бібліотека сцен (декоратор @scene)
  render.py     сценарій → кадри → титри/лічильник/переходи → ffmpeg
  analyze.py    аналіз відео: ffprobe, детекція склейок, статистика кадрів, контактний аркуш
  __main__.py   CLI
examples/       приклади сценаріїв
tests/          тести (python -m unittest discover -s tests)
```

## Як додати свою сцену

```python
# anim2d/scenes.py
@scene("gym")
def gym(ctx, t, u, sc):
    """Спортзал."""
    ctx.fill((20, 20, 24))
    ctx.rect(0, 600, ctx.W, ctx.H, fill=(30, 30, 36))
    draw_character(ctx, 640, 600, size=1.3, expression=sc.get("expression", "determined"))
```

- `t` — секунди від початку сцени, `u` — прогрес від 0 до 1, `sc` — параметри з YAML.
- `P(sc, "назва", за_замовчуванням, u)` читає параметр і підтримує анімацію `[від, до]`.
- Координати логічні: ширина кадру завжди 1280.

## Порада щодо аналізу

Для темної мінімалістичної анімації з плавними переходами поріг детекції склейок
`--threshold 0.15` (за замовчуванням) працює краще за звичні 0.3. Для живого відео пробуйте 0.3–0.4.

## Тести

```bash
python -m unittest discover -s tests -v
```
