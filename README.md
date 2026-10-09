# Link45 — Documentation / Документация

---

## 📑 Table of Contents / Оглавление

1. [About Link45 / О проекте Link45](#1-about-link45--о-проекте-link45)
2. [What it does / Назначение](#2-what-it-does--назначение)
3. [Features / Возможности](#3-features--возможности)
4. [Installation / Установка](#4-installation--установка)
   - [Linux / macOS](#linux--macos)
   - [Windows](#windows)
5. [Usage / Использование](#5-usage--использование)
6. [Parameters / Параметры](#6-parameters--параметры)
7. [Known Limitations / Известные ограничения](#7-known-limitations--известные-ограничения)
8. [Testing / Тестирование](#8-testing--тестирование)
9. [License / Лицензия](#9-license--лицензия)

---

## 1. About Link45 / О проекте Link45

### English
**Link45** is an Inkscape 1.x extension for drawing **45° routed connections** between selected objects. Designed with PCB pad routing in mind, but works for any technical diagram that uses orthogonal + diagonal connections.

![screenshot placeholder](docs/screenshot.png)

### Русский
**Link45** — это расширение для Inkscape 1.x, предназначенное для рисования **соединений с углами 45°** между выбранными объектами. Разработано с учетом трассировки контактных площадок печатных плат (PCB), но подходит для любых технических диаграмм, использующих ортогональные и диагональные линии.

---

## 2. What it does / Назначение

### English
Link45 connects **centers** (or **facing edges**) of selected objects with paths built exclusively from:
- **Orthogonal** segments (0° / 90°)
- **Diagonal** segments (45° / 135°)

This is the standard style for PCB trace routing, and it's also handy for schematics, block diagrams, and any illustration where arbitrary angles would look sloppy.

### Русский
Link45 соединяет **центры** (или **обращенные друг к другу края**) выбранных объектов с помощью путей, состоящих исключительно из:
- **Ортогональных** отрезков (0° / 90°)
- **Диагональных** отрезков (45° / 135°)

Это стандартный стиль для трассировки дорожек печатных плат, который также удобен для схем, блок-диаграмм и любых иллюстраций, где произвольные углы выглядят неаккуратно.

---

## 3. Features / Возможности

### English
- **6 routing topologies**: D-O-D, D-O-D-O-D, O-D-O, O-D-O-D-O, D-O, O-D
- **Anchor point**: connect from object center, or from the edge facing the target
- **Edge inset**: shrink or extend the endpoint along the ray
- **Chain / Bus multi-object modes**: sequential connection or paired
- **Lane separation**: parallel routes for arrays of pads, no overlaps
- **Inverse routing**: hug the start point (cubic weight distribution)
- **S-shape**: hump-through-center variant for D-O-D
- **Color inheritance**: use fill or stroke color of the objects as trace color
- **Style string**: full control over stroke, width, dash, etc.

### Русский
- **6 топологий трассировки**: D-O-D, D-O-D-O-D, O-D-O, O-D-O-D-O, D-O, O-D *(D — диагональ, O — ортогональ)*
- **Точка привязки**: соединение от центра объекта или от края, обращенного к цели
- **Отступ от края (Edge inset)**: сокращение или удлинение конечной точки вдоль луча
- **Режимы для нескольких объектов (Chain / Bus)**: последовательное соединение или попарное
- **Разделение дорожек**: параллельные маршруты для массивов площадок без перекрытий
- **Инверсная трассировка**: прижатие к начальной точке (кубическое распределение весов)
- **S-образная форма**: вариант с изгибом через центр для топологии D-O-D
- **Наследование цвета**: использование цвета заливки или обводки объектов в качестве цвета дорожки
- **Строка стиля**: полный контроль над обводкой, шириной, пунктиром и т. д.

---

## 4. Installation / Установка

### Linux / macOS

```bash
git clone https://github.com/vasiliypavlov/inkscape-link45.git
cp -r link45 ~/.config/inkscape/extensions/
```

**English:** Then restart Inkscape. The extension will appear under `Extensions → Custom → Link45`.  
**Русский:** Затем перезапустите Inkscape. Расширение появится в меню `Расширения → Пользовательские → Link45`.

### Windows

```bash
powershell
git clone https://github.com/<you>/link45.git
xcopy link45 "%APPDATA%\inkscape\extensions\link45\" /E /I
```

**English:** Then restart Inkscape. The extension will appear under `Extensions → Custom → Link45`.  
**Русский:** Затем перезапустите Inkscape. Расширение появится в меню `Расширения → Пользовательские → Link45`.

---

## 5. Usage / Использование

### English
1. Select two or more objects.
2. Run `Extensions → Link45`.
3. Choose the route, shape, anchor, group mode, and other options.
4. Click **Apply**.

For multi-object selections, objects are grouped by their **fill** color. Each color group produces its own set of paths:
- **Chain** — sequential connections: 1↔2, 2↔3, 3↔4, …
- **Bus** — best-effort pairing into two clusters (left/right or top/bottom), then one-to-one connections by index. Requires ≥ 3 objects in a group.

### Русский
1. Выберите два или более объектов.
2. Запустите `Расширения → Link45`.
3. Выберите маршрут, форму, точку привязки, режим группировки и другие параметры.
4. Нажмите **Применить** (**Apply**).

При выборе нескольких объектов они группируются по цвету **заливки**. Каждая цветовая группа создает свой набор путей:
- **Chain (Цепь)** — последовательные соединения: 1↔2, 2↔3, 3↔4, …
- **Bus (Шина)** — оптимизированное разбиение на два кластера (левый/правый или верхний/нижний) и последующее попарное соединение один-к-одному по индексу. Требует ≥ 3 объектов в группе.

---

## 6. Parameters / Параметры

| English Parameter | Русский параметр | Description (English) | Описание (Русский) |
|---|---|---|---|
| **Route** | **Маршрут** | Topology: `D-O-D`, `D-O-D-O-D`, `O-D-O`, `O-D-O-D-O`, `D-O`, `O-D` | Топология: `D-O-D`, `D-O-D-O-D`, `O-D-O`, `O-D-O-D-O`, `D-O`, `O-D` |
| **Shape** | **Форма** | `Z` (standard) or `S` (hump). S works only with D-O-D. | `Z` (стандартная) или `S` (с изгибом). S работает только с D-O-D. |
| **Anchor point** | **Точка привязки** | `Center` or `Edge facing target` | `Центр` или `Край, обращенный к цели` |
| **Multi-object mode** | **Режим группы** | `Chain` or `Bus` | `Цепь` (Chain) или `Шина` (Bus) |
| **Color source** | **Источник цвета** | Use Style string, or inherit `fill`/`stroke` from objects | Использовать строку стиля или наследовать `заливку`/`обводку` от объектов |
| **Inverse route** | **Инверсный маршрут** | Hug the start point (cubic weight distribution) | Прижатие к начальной точке (кубическое распределение веса) |
| **Style** | **Стиль** | Full SVG style string (default `stroke:black;fill:none;stroke-width:0.25`) | Полная строка стиля SVG (по умолчанию `stroke:black;fill:none;stroke-width:0.25`) |
| **Stroke width** | **Ширина обводки** | Used when color inheritance is active (user units) | Используется при включенном наследовании цвета (в единицах пользователя) |
| **Lane step** | **Шаг дорожки** | Perpendicular shift between parallel lanes (can be negative) | Перпендикулярное смещение между параллельными дорожками (может быть отрицательным) |
| **Lane margin** | **Отступ дорожки** | Minimum clearance between diagonal segment and target | Минимальный зазор между диагональным отрезком и целью |
| **Edge inset** | **Отступ от края** | Shift endpoint along the ray: `+` = into pad, `−` = gap | Смещение конечной точки вдоль луча: `+` = внутрь площадки, `−` = зазор |

---

## 7. Known Limitations / Известные ограничения

### English
- **No obstacle avoidance.** Link45 does not know about other objects in the document. It only manages overlap **within** the selected group.
- **S-shape is D-O-D only.** For other routes the parameter is ignored (there is no single mid-orthogonal to displace).
- **Bus mode with diagonal pad rows** may produce small backward steps for some pairs — geometry does not allow a fully parallel bus at 45°.
- **Round pads** use the AABB, not the true circle. For rectangular pads (including rotated), the geometry is exact.

### Русский
- **Отсутствует обход препятствий.** Link45 не учитывает другие объекты в документе. Расширение предотвращает перекрытия только **внутри** выбранной группы.
- **S-образная форма доступна только для D-O-D.** Для других маршрутов этот параметр игнорируется (отсутствует единый средний ортогональный отрезок для смещения).
- **Режим «Шина» (Bus) с диагональными рядами площадок** может создавать небольшие обратные шаги для некоторых пар — геометрия не позволяет сделать полностью параллельную шину под 45°.
- **Круглые площадки** используют выровненный по осям ограничивающий прямоугольник (AABB), а не реальный круг. Для прямоугольных площадок (включая повернутые) геометрия точна.

---

## 8. Testing / Тестирование

### English
Tested on:
- Inkscape 1.3.2 on Windows 11
- Python 3.11 (bundled with Inkscape)

### Русский
Протестировано на:
- Inkscape 1.3.2 на Windows 11
- Python 3.11 (встроенный в Inkscape)

---

## 9. License / Лицензия

### English
MIT — see [LICENSE](LICENSE).

### Русский
MIT — см. [LICENSE](LICENSE).
