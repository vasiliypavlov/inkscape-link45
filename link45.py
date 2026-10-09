#!/usr/bin/env python
# coding: utf-8

"""Link45 — Inkscape extension for 45° PCB-style routing.

Connects centers (or facing edges) of selected objects with paths
built only from orthogonal and 45° segments. Supports chain and bus
modes, lane separation, inverse routing, and S-shape.

Русский: расширение Inkscape 1.x для соединения центров (или граней)
выделенных объектов «змейкой» из ортогональных и 45° сегментов.
Поддерживает режимы chain/bus, lane separation, инверсию и S-форму.
"""

import inkex
from inkex import PathElement

__version__ = "1.0.0"
__license__ = "MIT"


class Link45(inkex.EffectExtension):
    """Inkscape 1.x extension for 45° routing between selected objects."""

    # ------------------------------------------------------------------
    # CLI / GUI arguments
    # ------------------------------------------------------------------
    def add_arguments(self, pars):
        pars.add_argument("--edge_inset", type=float, default=0.3)
        pars.add_argument("--lane_step", type=float, default=1.0)
        pars.add_argument("--lane_margin", type=float, default=0.5)
        pars.add_argument("--stroke_width", type=float, default=0.25)
        pars.add_argument("--color_source", type=str, default="none")
        pars.add_argument("--mode", type=str, default="dod")
        pars.add_argument("--shape", type=str, default="z")
        pars.add_argument("--anchor", type=str, default="center")
        pars.add_argument("--group", type=str, default="chain")
        pars.add_argument("--inverse", type=inkex.Boolean, default=False)
        pars.add_argument("--style", type=str,
                          default="stroke:black;fill:none;stroke-width:0.25")

    # ------------------------------------------------------------------
    # Segment weights
    # ------------------------------------------------------------------
    def _split(self, n):
        """Weights for n same-type segments, sum = 1.
        Non-inverse: equal. Inverse: cubic growth.
        Веса n сегментов, сумма = 1. Не-инверс: равные. Инверс: куб."""
        if not self.options.inverse or n <= 1:
            return [1.0 / n] * n
        raw = [(i + 1) ** 3 for i in range(n)]
        t = float(sum(raw))
        return [r / t for r in raw]

    def _split_inc(self, n):
        """Reversed weights (orthogonals in O-D-O, O-D-O-D-O).
        Обратные веса (ортогонали в O-D-O, O-D-O-D-O)."""
        return list(reversed(self._split(n)))

    # ------------------------------------------------------------------
    # Matrix helpers
    # ------------------------------------------------------------------
    def _invert_transform(self, mat):
        """Inverse of inkex.Transform. Native method first, manual fallback.
        Обратная матрица inkex.Transform. Родной метод, потом вручную."""
        if mat is None:
            return None
        try:
            inv = mat.inverse()
            if inv is not None:
                return inv
        except Exception:
            pass  # expected in some builds / ожидаемо в некоторых сборках
        try:
            a = float(mat.a); b = float(mat.b); c = float(mat.c)
            d = float(mat.d); e = float(mat.e); f = float(mat.f)
            det = a * d - b * c
            if abs(det) < 1e-12:
                inkex.errormsg("_invert_transform: singular matrix")
                return None
            ia = d / det
            ib = -b / det
            ic = -c / det
            id_ = a / det
            ie = (c * f - d * e) / det
            if_ = (b * e - a * f) / det
            return inkex.Transform(f"matrix({ia},{ib},{ic},{id_},{ie},{if_})")
        except Exception as e:
            inkex.errormsg(f"_invert_transform: failed: {e!r}")
            return None

    def _root_transform(self, elem):
        """Matrix from elem's PARENT coords to SVG root (elem's own
        transform excluded, bbox() already accounts for it).
        Матрица от родителя elem до корня SVG (без собственного
        transform — bbox() уже его учитывает)."""
        matrices = []
        node = elem.getparent()
        root = self.svg
        while node is not None and node is not root:
            t = node.get('transform')
            if t:
                try:
                    matrices.append(inkex.Transform(t))
                except Exception as e:
                    inkex.errormsg(f"_root_transform: bad transform: {e!r}")
            node = node.getparent()
        result = inkex.Transform()
        for m in matrices:
            result = m @ result
        return result

    def _root_bbox(self, elem):
        """Bbox of elem in SVG root coords: (x0, y0, x1, y1, cx, cy).
        Bbox элемента в системе корня: (x0, y0, x1, y1, cx, cy)."""
        bbox = elem.bounding_box()
        mat = self._root_transform(elem)
        corners = [
            (bbox.left,  bbox.top),
            (bbox.right, bbox.top),
            (bbox.right, bbox.bottom),
            (bbox.left,  bbox.bottom),
        ]
        xs, ys = [], []
        for px, py in corners:
            try:
                rx, ry = mat.apply_to_point((px, py))
            except Exception as e:
                inkex.errormsg(f"_root_bbox: apply failed: {e!r}")
                rx, ry = px, py
            xs.append(float(rx))
            ys.append(float(ry))
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        return (x0, y0, x1, y1, (x0 + x1) / 2.0, (y0 + y1) / 2.0)

    def _center(self, elem):
        """Center of elem's bbox in root coords.
        Центр bbox в корневых координатах."""
        _, _, _, _, cx, cy = self._root_bbox(elem)
        return (cx, cy)

    # ------------------------------------------------------------------
    # Anchor
    # ------------------------------------------------------------------
    def _anchor_point(self, elem, target_center):
        """Center of elem, or the point where the ray center→target
        crosses the facing edge (for 'rect' — exact geometry, for
        others — AABB). Edge inset shifts along the ray (+ = into pad).
        Центр или точка на грани в направлении цели. Edge inset
        сдвигает вдоль луча (+ = внутрь пада)."""
        bbox = elem.bounding_box()

        try:
            parent_to_root = self._root_transform(elem)
            own_t = elem.get('transform')
            own_mat = inkex.Transform(own_t) if own_t else inkex.Transform()
            full_mat = parent_to_root @ own_mat
            inv_mat = self._invert_transform(full_mat)
        except Exception as e:
            inkex.errormsg(f"_anchor_point: matrix setup failed: {e!r}")
            full_mat = None
            inv_mat = None

        try:
            if full_mat is not None:
                cx_r, cy_r = parent_to_root.apply_to_point(bbox.center)
            else:
                cx_r, cy_r = bbox.center
            cx_r, cy_r = float(cx_r), float(cy_r)
        except Exception as e:
            inkex.errormsg(f"_anchor_point: center calc failed: {e!r}")
            return (float(bbox.center[0]), float(bbox.center[1]))

        if self.options.anchor != "edge" or target_center is None:
            return (cx_r, cy_r)
        if inv_mat is None:
            return (cx_r, cy_r)

        try:
            tx_l, ty_l = inv_mat.apply_to_point(target_center)
            tx_l, ty_l = float(tx_l), float(ty_l)
        except Exception as e:
            inkex.errormsg(f"_anchor_point: target transform failed: {e!r}")
            return (cx_r, cy_r)

        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag == 'rect':
            try:
                x0 = float(elem.get('x', 0) or 0)
                y0 = float(elem.get('y', 0) or 0)
                x1 = x0 + float(elem.get('width', 0) or 0)
                y1 = y0 + float(elem.get('height', 0) or 0)
            except Exception as e:
                inkex.errormsg(f"_anchor_point: rect attrs failed: {e!r}")
                return (cx_r, cy_r)
        else:
            try:
                x0 = float(bbox.left)
                y0 = float(bbox.top)
                x1 = float(bbox.right)
                y1 = float(bbox.bottom)
            except Exception as e:
                inkex.errormsg(f"_anchor_point: bbox parse failed: {e!r}")
                return (cx_r, cy_r)

        if (x1 - x0) < 1e-9 or (y1 - y0) < 1e-9:
            return (cx_r, cy_r)

        cx_l = (x0 + x1) / 2.0
        cy_l = (y0 + y1) / 2.0
        dx = tx_l - cx_l
        dy = ty_l - cy_l

        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return (cx_r, cy_r)

        hw = (x1 - x0) / 2.0
        hh = (y1 - y0) / 2.0
        ts = []
        if abs(dx) > 1e-9:
            ts.append(hw / abs(dx))
        if abs(dy) > 1e-9:
            ts.append(hh / abs(dy))
        if not ts:
            return (cx_r, cy_r)
        t = min(ts)

        # Edge inset: + = into pad (shrink t), – = outward
        # Edge inset: + = внутрь пада (уменьшаем t), – = наружу
        try:
            inset = float(self.options.edge_inset or 0)
        except Exception:
            inset = 0.0
        ray_len = (dx * dx + dy * dy) ** 0.5
        if ray_len > 1e-9 and abs(inset) > 1e-9:
            t -= inset / ray_len
            if t < 0:
                t = 0.0

        ax_l = cx_l + t * dx
        ay_l = cy_l + t * dy

        try:
            ax_r, ay_r = full_mat.apply_to_point((ax_l, ay_l))
            return (float(ax_r), float(ay_r))
        except Exception as e:
            inkex.errormsg(f"_anchor_point: final apply failed: {e!r}")
            return (cx_r, cy_r)

    # ------------------------------------------------------------------
    # Pair construction
    # ------------------------------------------------------------------
    def _split_axis(self, centers):
        """Axis with the largest gap between sorted coordinates.
        Ось с наибольшим разрывом между отсортированными координатами."""
        n = len(centers)
        if n < 2:
            return "x"
        xs = sorted(c[0] for c in centers)
        ys = sorted(c[1] for c in centers)
        gap_x = max(xs[i + 1] - xs[i] for i in range(n - 1))
        gap_y = max(ys[i + 1] - ys[i] for i in range(n - 1))
        return "x" if gap_x >= gap_y else "y"

    def _bus_pairs(self, elems):
        """Split elems into two clusters, pair one-to-one by index.
        Разбивает elems на два кластера и пары один-к-одному."""
        n = len(elems)
        centers = [self._center(e) for e in elems]
        axis = self._split_axis(centers)
        if axis == "x":
            order = sorted(range(n), key=lambda i: centers[i][0])
            best_k, best_gap = 0, -1.0
            for k in range(n - 1):
                g = centers[order[k + 1]][0] - centers[order[k]][0]
                if g > best_gap:
                    best_gap, best_k = g, k
            g1 = order[:best_k + 1]
            g2 = order[best_k + 1:]
            g1.sort(key=lambda i: centers[i][1])
            g2.sort(key=lambda i: centers[i][1])
        else:
            order = sorted(range(n), key=lambda i: centers[i][1])
            best_k, best_gap = 0, -1.0
            for k in range(n - 1):
                g = centers[order[k + 1]][1] - centers[order[k]][1]
                if g > best_gap:
                    best_gap, best_k = g, k
            g1 = order[:best_k + 1]
            g2 = order[best_k + 1:]
            g1.sort(key=lambda i: centers[i][0])
            g2.sort(key=lambda i: centers[i][0])
        m = min(len(g1), len(g2))
        return [(elems[g1[i]], elems[g2[i]]) for i in range(m)]

    def _chain_pairs(self, elems):
        """Sequential pairs: 0-1, 1-2, ... / Цепочка: 0-1, 1-2, ..."""
        centers = [self._center(e) for e in elems]
        order = sorted(range(len(elems)), key=lambda i: centers[i])
        return [(elems[order[i]], elems[order[i + 1]])
                for i in range(len(order) - 1)]

    # ------------------------------------------------------------------
    # Lane separation
    # ------------------------------------------------------------------
    def _apply_lane_separation(self, pairs):
        """Distribute pairs into parallel lanes. Monotonic shifts so
        that all 45° stubs point the same way. Returns (deltas, horiz).
        Раскладывает пары по параллельным полосам. Монотонные сдвиги,
        все 45° заглушки смотрят в одну сторону."""
        n = len(pairs)
        if n <= 1:
            return {}, None

        # Axis voting / Голосование за ось
        hor_votes = 0
        for e1, e2 in pairs:
            c1 = self._center(e1)
            c2 = self._center(e2)
            if abs(c2[0] - c1[0]) >= abs(c2[1] - c1[1]):
                hor_votes += 1
        if 0.2 * n < hor_votes < 0.8 * n:
            return {}, None
        horizontal = hor_votes * 2 >= n

        perp = []
        for e1, e2 in pairs:
            c1 = self._center(e1)
            c2 = self._center(e2)
            if horizontal:
                perp.append((c1[1] + c2[1]) / 2.0)
            else:
                perp.append((c1[0] + c2[0]) / 2.0)
        order = sorted(range(n), key=lambda i: perp[i])

        try:
            step = float(self.options.lane_step)
        except Exception:
            step = 1.0
        try:
            margin = float(self.options.lane_margin)
        except Exception:
            margin = 0.5

        # Monotonic shifts / Монотонные сдвиги
        base_deltas = [rank * step for rank in range(n)]

        # Global scale-down / Общий множитель
        scale = 1.0
        for rank, idx in enumerate(order):
            d = base_deltas[rank]
            if abs(d) < 1e-9:
                continue
            e1, e2 = pairs[idx]
            c1 = self._center(e1)
            c2 = self._center(e2)
            if horizontal:
                main = abs(c2[0] - c1[0])
            else:
                main = abs(c2[1] - c1[1])
            target = main - margin
            max_allowed = target / 2.0 if target > 0 else 0.0
            if max_allowed < abs(d):
                ratio = max_allowed / abs(d)
                if ratio < scale:
                    scale = ratio

        result = {}
        for rank, idx in enumerate(order):
            result[idx] = base_deltas[rank] * scale
        return result, horizontal

    # ------------------------------------------------------------------
    # Axis selection
    # ------------------------------------------------------------------
    def _pick_bus_axis(self, pairs):
        """Single orthogonal axis for the whole bus.
        Единая ось ортогоналей для всей шины."""
        best_axis, best_penalty = 'x', float('inf')
        for axis in ('x', 'y'):
            worst = 0.0
            for e1, e2 in pairs:
                c1 = self._center(e1)
                c2 = self._center(e2)
                dx = c2[0] - c1[0]
                dy = c2[1] - c1[1]
                free = (abs(dx) - abs(dy)) if axis == 'x' \
                    else (abs(dy) - abs(dx))
                if free < 0:
                    worst = max(worst, -free)
            if worst < best_penalty:
                best_penalty = worst
                best_axis = axis
        return best_axis

    def _use_horizontal(self, dx, dy):
        """Unified axis decision / Единый выбор оси."""
        g = getattr(self, '_global_axis', None)
        if g == 'x':
            return True
        if g == 'y':
            return False
        forced = getattr(self, '_forced_axis', None)
        if forced == 'x':
            return True
        if forced == 'y':
            return False
        return abs(dx) >= abs(dy)

    # ------------------------------------------------------------------
    # Style per pair
    # ------------------------------------------------------------------
    def _pair_style(self, e1, e2):
        """Compose style for one path. If color_source is 'fill' or
        'stroke' and BOTH objects share the same plain-color value,
        use it as stroke. Otherwise fall back to self.options.style.
        Стиль для одного пути. Если color_source = 'fill'/'stroke' и
        у ОБОИХ объектов совпадает простой цвет, берём его как обводку.
        Иначе — self.options.style."""
        src = (self.options.color_source or "none").lower()
        if src in ("fill", "stroke"):
            try:
                v1 = str(e1.specified_style().get(src, 'none')).lower().strip()
                v2 = str(e2.specified_style().get(src, 'none')).lower().strip()
            except Exception:
                v1 = v2 = 'none'
            if (v1 == v2
                    and v1 not in ('', 'none', 'transparent')
                    and not v1.startswith('url(')):
                try:
                    sw = float(self.options.stroke_width)
                except Exception:
                    sw = 0.25
                return (f"stroke:{v1};fill:none;stroke-width:{sw};"
                        f"stroke-opacity:1;fill-opacity:0")
        return self.options.style

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------
    def effect(self):
        selected = self.svg.selected
        if len(selected) < 2:
            inkex.errormsg("Выделите минимум два объекта. / "
                           "Select at least two objects.")
            return

        mode = (self.options.mode or "dod").lower()

        # Inverse for 2-segment modes swaps D-O ↔ O-D
        # Инверс для 2-сегментных меняет D-O ↔ O-D
        if self.options.inverse:
            if mode == "do":
                mode = "od"
            elif mode == "od":
                mode = "do"

        if mode == "dod" and self.options.shape == "s":
            builder = self.gen_dod_s
        else:
            builders = {
                "dod":   self.gen_dod,
                "do":    self.gen_do,
                "od":    self.gen_od,
                "odo":   self.gen_odo,
                "dodod": self.gen_dodod,
                "ododo": self.gen_ododo,
            }
            builder = builders.get(mode)
            if builder is None:
                inkex.errormsg(f"Неизвестный режим: {mode}")
                return

        # Collect pairs / Собираем пары
        flat_pairs = []
        if len(selected) == 2:
            elems = list(selected.values())
            flat_pairs.append((elems[0], elems[1]))
        else:
            groups = {}
            for elem in selected.values():
                try:
                    fill = str(elem.specified_style().get('fill', 'none')
                              ).lower().strip()
                except Exception:
                    fill = 'none'
                groups.setdefault(fill, []).append(elem)
            for fill, elems in groups.items():
                if len(elems) < 2:
                    continue
                if self.options.group == "bus" and len(elems) >= 3:
                    flat_pairs.extend(self._bus_pairs(elems))
                else:
                    flat_pairs.extend(self._chain_pairs(elems))

        # Lane separation / Разделение по полосам
        deltas, horizontal = {}, None
        if len(flat_pairs) > 1:
            deltas, horizontal = self._apply_lane_separation(flat_pairs)

        self._global_axis = None
        if horizontal is not None:
            self._global_axis = 'x' if horizontal else 'y'

        target = self.svg
        created = 0

        for idx, (e1, e2) in enumerate(flat_pairs):
            c1 = self._center(e1)
            c2 = self._center(e2)
            p1 = self._anchor_point(e1, c2)
            p2 = self._anchor_point(e2, c1)

            self._lane_delta = deltas.get(idx, 0.0)
            points = builder(p1[0], p1[1], p2[0], p2[1])

            path = PathElement()
            path.style = self._pair_style(e1, e2)
            d = f"M {points[0][0]},{points[0][1]}"
            for p in points[1:]:
                d += f" L {p[0]},{p[1]}"
            path.set('d', d)
            target.append(path)
            created += 1

        # Reset state / Сброс состояния
        self._lane_delta = 0.0
        self._global_axis = None
        self._forced_axis = None

        if created == 0:
            inkex.errormsg(
                "Не найдено двух или более выделенных объектов "
                "с одинаковой заливкой. / "
                "No two or more selected objects share the same fill."
            )

    # ------------------------------------------------------------------
    # Path generators
    # ------------------------------------------------------------------
    def gen_do(self, x1, y1, x2, y2):
        """2 segments: D-O. / 2 сегмента: D-O."""
        dx, dy = x2 - x1, y2 - y1
        if self._use_horizontal(dx, dy):
            sx = 1 if dx >= 0 else -1
            mid = (x1 + sx * abs(dy), y1 + dy)
        else:
            sy = 1 if dy >= 0 else -1
            mid = (x1 + dx, y1 + sy * abs(dx))
        return [(x1, y1), mid, (x2, y2)]

    def gen_od(self, x1, y1, x2, y2):
        """2 segments: O-D. / 2 сегмента: O-D."""
        dx, dy = x2 - x1, y2 - y1
        if self._use_horizontal(dx, dy):
            sx = 1 if dx >= 0 else -1
            mid = (x1 + dx - sx * abs(dy), y1)
        else:
            sy = 1 if dy >= 0 else -1
            mid = (x1, y1 + dy - sy * abs(dx))
        return [(x1, y1), mid, (x2, y2)]

    def gen_dod(self, x1, y1, x2, y2):
        """D-O-D with lane delta. / D-O-D с lane delta."""
        delta = getattr(self, '_lane_delta', 0.0)
        dx, dy = x2 - x1, y2 - y1
        pts = [(x1, y1)]
        if self._use_horizontal(dx, dy):
            sx = 1 if dx >= 0 else -1
            w = self._split(2)
            y_offset = dy * w[0] + delta
            s1 = abs(y_offset)
            s2 = abs(dy - y_offset)
            x_mid1 = x1 + sx * s1
            x_mid2 = x2 - sx * s2
            y_mid = y1 + y_offset
            pts.append((x_mid1, y_mid))
            pts.append((x_mid2, y_mid))
            pts.append((x2, y2))
        else:
            sy = 1 if dy >= 0 else -1
            w = self._split(2)
            x_offset = dx * w[0] + delta
            s1 = abs(x_offset)
            s2 = abs(dx - x_offset)
            x_mid = x1 + x_offset
            y_mid1 = y1 + sy * s1
            y_mid2 = y2 - sy * s2
            pts.append((x_mid, y_mid1))
            pts.append((x_mid, y_mid2))
            pts.append((x2, y2))
        return pts

    def gen_dod_s(self, x1, y1, x2, y2):
        """3 segments: S-shape hump. Middle segment is pushed away from
        the AB line, giving a 'hump through center' look. Respects lane
        separation delta by prepending a 45° stub at the start.

        3 сегмента: S-образный горб. Средний сегмент выносится
        в сторону от линии AB. Учитывает сдвиг lane separation
        через 45° заглушку в начале."""
        delta = getattr(self, '_lane_delta', 0.0)
        dx, dy = x2 - x1, y2 - y1
        pts = [(x1, y1)]

        if self._use_horizontal(dx, dy):
            sx = 1 if dx >= 0 else -1
            dy_sign = 1 if dy >= 0 else -1

            # 45° stub for lane separation / 45° заглушка для lane separation
            x1_eff, y1_eff = x1, y1
            if abs(delta) > 1e-9:
                x1_eff = x1 + sx * abs(delta)
                y1_eff = y1 + delta
                pts.append((x1_eff, y1_eff))

            dx_eff = x2 - x1_eff
            dy_eff = y2 - y1_eff
            h = (abs(dx_eff) - abs(dy_eff)) / 4.0
            if h < 0.1 and abs(delta) > 1e-9:
                # No room for stub — drop it / Нет места под заглушку — откат
                pts = [(x1, y1)]
                x1_eff, y1_eff = x1, y1
                dx_eff, dy_eff = dx, dy
                h = (abs(dx_eff) - abs(dy_eff)) / 4.0

            x = x1_eff + sx * h
            y = y1_eff - dy_sign * h
            pts.append((x, y))
            h_len = abs(dx_eff) - abs(dy_eff) - 2 * h
            pts.append((x + sx * h_len, y))
            pts.append((x2, y2))
        else:
            sy = 1 if dy >= 0 else -1
            dx_sign = 1 if dx >= 0 else -1

            # 45° stub for lane separation / 45° заглушка
            x1_eff, y1_eff = x1, y1
            if abs(delta) > 1e-9:
                x1_eff = x1 + delta
                y1_eff = y1 + sy * abs(delta)
                pts.append((x1_eff, y1_eff))

            dx_eff = x2 - x1_eff
            dy_eff = y2 - y1_eff
            h = (abs(dy_eff) - abs(dx_eff)) / 4.0
            if h < 0.1 and abs(delta) > 1e-9:
                pts = [(x1, y1)]
                x1_eff, y1_eff = x1, y1
                dx_eff, dy_eff = dx, dy
                h = (abs(dy_eff) - abs(dx_eff)) / 4.0

            x = x1_eff - dx_sign * h
            y = y1_eff + sy * h
            pts.append((x, y))
            v_len = abs(dy_eff) - abs(dx_eff) - 2 * h
            pts.append((x, y + sy * v_len))
            pts.append((x2, y2))
        return pts

    def gen_odo(self, x1, y1, x2, y2):
        """O-D-O. With lane delta, prepend a 45° stub to shift the
        diagonal sideways (topology becomes D-O-D-O for shifted pairs).
        O-D-O. При lane delta добавляем 45° заглушку (D-O-D-O)."""
        delta = getattr(self, '_lane_delta', 0.0)
        dx, dy = x2 - x1, y2 - y1
        pts = [(x1, y1)]
        if self._use_horizontal(dx, dy):
            sx = 1 if dx >= 0 else -1
            x1_eff, y1_eff = x1, y1
            if abs(delta) > 1e-9:
                x1_eff = x1 + sx * abs(delta)
                y1_eff = y1 + delta
                pts.append((x1_eff, y1_eff))
            dx_eff = x2 - x1_eff
            dy_eff = y2 - y1_eff
            diag_x = sx * abs(dy_eff)
            diag_y = dy_eff
            h_total = dx_eff - diag_x
            if h_total < 0 and abs(delta) > 1e-9:
                pts = [(x1, y1)]
                x1_eff, y1_eff = x1, y1
                dx_eff, dy_eff = dx, dy
                diag_x = sx * abs(dy_eff)
                diag_y = dy_eff
                h_total = dx_eff - diag_x
            w = self._split_inc(2)
            h1, h2 = h_total * w[0], h_total * w[1]
            x, y = x1_eff, y1_eff
            x += h1;                    pts.append((x, y))
            x += diag_x; y += diag_y;   pts.append((x, y))
            x += h2;                    pts.append((x, y))
        else:
            sy = 1 if dy >= 0 else -1
            x1_eff, y1_eff = x1, y1
            if abs(delta) > 1e-9:
                x1_eff = x1 + delta
                y1_eff = y1 + sy * abs(delta)
                pts.append((x1_eff, y1_eff))
            dx_eff = x2 - x1_eff
            dy_eff = y2 - y1_eff
            diag_x = dx_eff
            diag_y = sy * abs(diag_x)
            v_total = dy_eff - diag_y
            if v_total < 0 and abs(delta) > 1e-9:
                pts = [(x1, y1)]
                x1_eff, y1_eff = x1, y1
                dx_eff, dy_eff = dx, dy
                diag_x = dx_eff
                diag_y = sy * abs(diag_x)
                v_total = dy_eff - diag_y
            w = self._split_inc(2)
            v1, v2 = v_total * w[0], v_total * w[1]
            x, y = x1_eff, y1_eff
            y += v1;                    pts.append((x, y))
            x += diag_x; y += diag_y;   pts.append((x, y))
            y += v2;                    pts.append((x, y))
        return pts

    def gen_dodod(self, x1, y1, x2, y2):
        """D-O-D-O-D with lane delta. / D-O-D-O-D с lane delta."""
        delta = getattr(self, '_lane_delta', 0.0)
        dx, dy = x2 - x1, y2 - y1
        pts = [(x1, y1)]
        if self._use_horizontal(dx, dy):
            sx = 1 if dx >= 0 else -1
            wd = self._split(3)
            y_o1 = y1 + dy * wd[0] + delta
            y_o2 = y1 + dy * (wd[0] + wd[1]) + delta
            s1 = abs(y_o1 - y1)
            s2 = abs(y_o2 - y_o1)
            s3 = abs(y2 - y_o2)
            total_diag = s1 + s2 + s3
            total_h = abs(dx) - total_diag
            if total_h < 0.5:
                y_o1 = y1 + dy * wd[0]
                y_o2 = y1 + dy * (wd[0] + wd[1])
                s1 = abs(y_o1 - y1)
                s2 = abs(y_o2 - y_o1)
                s3 = abs(y2 - y_o2)
                total_diag = s1 + s2 + s3
                total_h = abs(dx) - total_diag
            h1 = total_h / 2.0
            h2 = total_h / 2.0
            x = x1
            x += sx * s1; pts.append((x, y_o1))
            x += sx * h1; pts.append((x, y_o1))
            x += sx * s2; pts.append((x, y_o2))
            x += sx * h2; pts.append((x, y_o2))
            x += sx * s3; pts.append((x2, y2))
        else:
            sy = 1 if dy >= 0 else -1
            wd = self._split(3)
            x_o1 = x1 + dx * wd[0] + delta
            x_o2 = x1 + dx * (wd[0] + wd[1]) + delta
            s1 = abs(x_o1 - x1)
            s2 = abs(x_o2 - x_o1)
            s3 = abs(x2 - x_o2)
            total_diag = s1 + s2 + s3
            total_v = abs(dy) - total_diag
            if total_v < 0.5:
                x_o1 = x1 + dx * wd[0]
                x_o2 = x1 + dx * (wd[0] + wd[1])
                s1 = abs(x_o1 - x1)
                s2 = abs(x_o2 - x_o1)
                s3 = abs(x2 - x_o2)
                total_diag = s1 + s2 + s3
                total_v = abs(dy) - total_diag
            v1 = total_v / 2.0
            v2 = total_v / 2.0
            y = y1
            y += sy * s1; pts.append((x_o1, y))
            y += sy * v1; pts.append((x_o1, y))
            y += sy * s2; pts.append((x_o2, y))
            y += sy * v2; pts.append((x_o2, y))
            y += sy * s3; pts.append((x2, y2))
        return pts

    def gen_ododo(self, x1, y1, x2, y2):
        """O-D-O-D-O. With lane delta, prepend a 45° stub.
        O-D-O-D-O. При lane delta добавляем 45° заглушку."""
        delta = getattr(self, '_lane_delta', 0.0)
        dx, dy = x2 - x1, y2 - y1
        pts = [(x1, y1)]
        if self._use_horizontal(dx, dy):
            sx = 1 if dx >= 0 else -1
            x1_eff, y1_eff = x1, y1
            if abs(delta) > 1e-9:
                x1_eff = x1 + sx * abs(delta)
                y1_eff = y1 + delta
                pts.append((x1_eff, y1_eff))
            dx_eff = x2 - x1_eff
            dy_eff = y2 - y1_eff
            wd = self._split(2)
            wh = self._split_inc(3)
            d = [dy_eff * w for w in wd]
            h_total = dx_eff - sx * abs(dy_eff)
            if h_total < 0 and abs(delta) > 1e-9:
                pts = [(x1, y1)]
                x1_eff, y1_eff = x1, y1
                dx_eff, dy_eff = dx, dy
                d = [dy_eff * w for w in wd]
                h_total = dx_eff - sx * abs(dy_eff)
            h = [h_total * w for w in wh]
            x, y = x1_eff, y1_eff
            x += h[0];                      pts.append((x, y))
            x += sx * abs(d[0]); y += d[0]; pts.append((x, y))
            x += h[1];                      pts.append((x, y))
            x += sx * abs(d[1]); y += d[1]; pts.append((x, y))
            x += h[2];                      pts.append((x, y))
        else:
            sy = 1 if dy >= 0 else -1
            x1_eff, y1_eff = x1, y1
            if abs(delta) > 1e-9:
                x1_eff = x1 + delta
                y1_eff = y1 + sy * abs(delta)
                pts.append((x1_eff, y1_eff))
            dx_eff = x2 - x1_eff
            dy_eff = y2 - y1_eff
            wd = self._split(2)
            wh = self._split_inc(3)
            d = [dx_eff * w for w in wd]
            v_total = dy_eff - sy * abs(dx_eff)
            if v_total < 0 and abs(delta) > 1e-9:
                pts = [(x1, y1)]
                x1_eff, y1_eff = x1, y1
                dx_eff, dy_eff = dx, dy
                d = [dx_eff * w for w in wd]
                v_total = dy_eff - sy * abs(dx_eff)
            v = [v_total * w for w in wh]
            x, y = x1_eff, y1_eff
            y += v[0];                      pts.append((x, y))
            x += d[0]; y += sy * abs(d[0]); pts.append((x, y))
            y += v[1];                      pts.append((x, y))
            x += d[1]; y += sy * abs(d[1]); pts.append((x, y))
            y += v[2];                      pts.append((x, y))
        return pts


if __name__ == '__main__':
    Link45().run()