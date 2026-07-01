import uuid
from typing import List, Tuple
from backend.app.core.geometry.models import (
    RoomGeometry, WallGeometry, PortalGeometry, DimensionLine
)


class SVGRenderer:
    """
    Renders purely mathematical geometry objects into a professional architectural SVG string.
    Implements native alpha channels and precise path drawing for CAD-accurate floorplans.

    Dark CAD theme — matches the BuildWise Aether UI exactly:
      • Dark olive canvas  (#0d0d06) with a full-bleed grid (#2a2a1a) that
        extends across the whole viewbox, NOT clipped to the plot polygon.
      • Plot boundary drawn as the ACTUAL polygon (rectangle, L/T/U shape, or
        any custom irregular outline) in a gold stroke (#d4af37) so the true
        silhouette is always clearly visible against the dark background.
      • Semi-transparent room fills (opacity 0.22) so the dark background
        shows through and rooms read as coloured zones, not opaque blocks.
      • Gold / amber exterior walls (#c8a84b) and dark-gold interior partitions
        (#5a4f1e) — both readable against the dark canvas.
      • Thick cyan window bars (#0ea5e9, stroke-width 2.0) matching the
        prominent window symbols visible in the reference screenshot.
      • Door gap cleared with the canvas colour (#0d0d06) so there is a clean
        break in the wall line; door panels drawn in gold (#c8a84b); swing arc
        in muted gold (#8a7a3a).
      • Dimension lines, arrows, and labels all in muted gold (#8a7a3a).
      • North compass drawn in light cream (#e8dfc8) for readability.
    """

    # ── Visual constants ──────────────────────────────────────────────────────

    # Canvas / theme
    BG_COLOR        = "#0d0d06"   # dark olive-black canvas
    GRID_COLOR      = "#2a2a1a"   # subtle dark grid lines

    # Rooms
    FILL_OPACITY    = "0.22"      # semi-transparent room fills
    ROOM_TEXT_COLOR = "#e8dfc8"   # warm cream for room name
    AREA_TEXT_COLOR = "#8a7a3a"   # muted gold for sq-ft label

    # Plot boundary
    PLOT_STROKE     = "#d4af37"   # gold polygon outline
    PLOT_SW         = "0.35"

    # Walls
    EXT_WALL_COLOR  = "#c8a84b"   # gold exterior shell
    INT_WALL_COLOR  = "#5a4f1e"   # dark-gold interior partitions

    # Windows
    WIN_COLOR       = "#0ea5e9"   # bright cyan
    WIN_SW          = 2.0         # thick bar matching screenshot

    # Doors
    DOOR_CLEAR      = "#0d0d06"   # matches canvas (clears wall gap)
    DOOR_CLEAR_SW   = "2.2"
    DOOR_PANEL_COL  = "#c8a84b"   # gold door panel
    DOOR_PANEL_SW   = "0.8"
    DOOR_ARC_COL    = "#8a7a3a"   # muted-gold swing arc
    DOOR_ARC_SW     = "0.3"

    # Dimensions / annotations
    DIM_COLOR       = "#8a7a3a"
    DIM_SW          = "0.2"
    DIM_FONT_SZ     = "1.4"
    COMPASS_COLOR   = "#e8dfc8"

    # ── Text-fit constants ────────────────────────────────────────────────────
    # NOTE on units: these are SVG font-size units in the SAME coordinate
    # space as the floor plan itself (feet), not screen pixels. On a
    # typical ~30x40ft plot rendered into a normal-width container, 1 unit
    # here is roughly 10-12 actual screen pixels. The previous floors
    # (_MIN_FONT=0.42, area=0.3) worked out to ~4-5px and ~3-4px on
    # screen -- technically "fitted" inside a room's box, but not
    # actually readable. Raised to real legibility floors below.
    _CHAR_WIDTH_RATIO = 0.62
    _LINE_HEIGHT_RATIO = 1.15
    _MAX_FONT = 2.0
    _MIN_FONT = 1.05        # room name floor -> stays readable at normal render sizes
    _AREA_MIN_FONT = 0.75   # dimensions/area floor -> smaller than name, still legible
    _CLIP_MARGIN = 0.5      # ft of clip-path tolerance around each room's own
                             # bbox, so a name held at the legibility floor
                             # in a too-small room is allowed to spill a
                             # little rather than being invisibly clipped

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _wrap_words_only(name: str, max_chars_per_line: int):
        """Greedy word-wrap that NEVER splits a word mid-way. Returns None
        if any single word alone is longer than max_chars_per_line, so the
        caller can try a smaller font (more chars fit per line) before
        resorting to a hard character break."""
        max_chars_per_line = max(2, max_chars_per_line)
        words = name.split() or [name]
        if any(len(w) > max_chars_per_line for w in words):
            return None
        lines: List[str] = []
        current = ""
        for w in words:
            candidate = (current + " " + w).strip()
            if len(candidate) <= max_chars_per_line:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines or [name]

    @staticmethod
    def _wrap_text_to_width(name: str, max_chars_per_line: int) -> List[str]:
        """Greedy word-wrap to a target character width. If a single word
        alone is still wider than a full line (common for compound room
        names like 'ATTACHED BATHROOM' once it's down to one word per
        line, or any long single-word name in a very small room), hard-
        breaks that word into fixed-width chunks so text still fits
        within the available width instead of overflowing indefinitely."""
        max_chars_per_line = max(2, max_chars_per_line)
        words = name.split() or [name]
        lines: List[str] = []
        current = ""
        for w in words:
            while len(w) > max_chars_per_line:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(w[:max_chars_per_line])
                w = w[max_chars_per_line:]
            candidate = (current + " " + w).strip()
            if len(candidate) <= max_chars_per_line:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
        return lines or [name]

    @staticmethod
    def _fit_room_text(name: str, area_label: str, room_w: float, room_h: float):
        """
        Computes a font size + line layout that genuinely adapts to the
        room's own available area: big rooms get a big single-line name,
        small rooms wrap onto more (smaller) lines, and the size search
        never drops below a real legibility floor. Unlike a fixed
        line-count search, this tries progressively smaller font sizes
        and re-wraps the name to fit the resulting width at each size,
        so the layout always matches what actually fits rather than
        guessing a line count first.

        Word-boundary wrapping (never splitting a word) is always tried
        first, across the whole font range down to the legibility floor,
        before a hard mid-word character break is used -- so a slightly
        smaller, cleanly-wrapped label is preferred over a bigger one
        that chops a word in half.

        The area/dimension label still only appears when there's
        genuinely enough leftover space for it to also be legible --
        that's what makes tiny rooms show name-only, adjusting
        automatically to the space available.

        Returns:
            (name_lines: List[str], name_font: float,
             area_font: float, show_area: bool)
        """
        pad = min(0.3, room_w * 0.06, room_h * 0.06)
        avail_w = max(room_w - 2 * pad, 0.6)
        avail_h = max(room_h - 2 * pad, 0.6)
        cw = SVGRenderer._CHAR_WIDTH_RATIO
        lh = SVGRenderer._LINE_HEIGHT_RATIO
        min_font = SVGRenderer._MIN_FONT

        # ── Step 1: search downward from the largest comfortable size to
        # the legibility floor, using word-boundary-only wrapping. First
        # (largest) size that both wraps cleanly AND fits the available
        # height wins -- this is what makes the label scale down smoothly
        # as the room shrinks, instead of jumping straight to a
        # worst-case tiny font or breaking a word unnecessarily.
        best = None
        font = SVGRenderer._MAX_FONT
        while font >= min_font - 1e-9:
            max_chars = max(2, int(avail_w / (cw * font)))
            lines = SVGRenderer._wrap_words_only(name, max_chars)
            if lines is not None:
                block_h = len(lines) * font * lh
                if block_h <= avail_h * 0.92:
                    best = (font, lines)
                    break
            font = round(font - 0.05, 2)

        if best is None:
            # No clean word-boundary wrap fits even at the legibility
            # floor (e.g. a single long word in a very small room) --
            # fall back to a hard character break AT the floor size, and
            # accept that it may spill slightly past the room's own
            # bounds. The per-room clip-path tolerance (_CLIP_MARGIN)
            # makes that spill actually visible instead of being
            # silently cropped away.
            max_chars = max(2, int(avail_w / (cw * min_font)))
            best = (min_font, SVGRenderer._wrap_text_to_width(name, max_chars))

        font, lines = best
        font = round(font, 2)

        # ── Step 2: fit the area/dimension label into whatever vertical
        # space is left below the name. Only shown once it can also sit
        # at or above its own legibility floor -- otherwise the room is
        # simply too small for dimensions and shows the name alone.
        name_block_h = len(lines) * font * lh
        remaining_h = avail_h - name_block_h
        show_area = False
        area_font = 0.0
        if remaining_h >= SVGRenderer._AREA_MIN_FONT * lh:
            area_font = min(font * 0.7, remaining_h / lh, avail_w / (max(len(area_label), 1) * cw))
            if area_font >= SVGRenderer._AREA_MIN_FONT:
                area_font = round(area_font, 2)
                show_area = True

        return lines, font, area_font, show_area


    # ── Public render entry point ─────────────────────────────────────────────

    @staticmethod
    def render(
        plot_w: float,
        plot_d: float,
        rooms: List[RoomGeometry],
        walls: List[WallGeometry],
        portals: List[PortalGeometry],
        dimensions: List[DimensionLine],
        plot_points: List[Tuple[float, float]] = None,
    ) -> str:
        # Fall back to a plain rectangle if no polygon was supplied so this
        # renderer stays fully backward-compatible with rectangular plots.
        if not plot_points:
            plot_points = [(0, 0), (plot_w, 0), (plot_w, plot_d), (0, plot_d)]

        # ── Per-render unique id namespace ──────────────────────────────────
        # Every floor's SVG is embedded inline into the SAME html document
        # (multiple floors x multiple layout options on one page). SVG/HTML
        # ids must be unique across the WHOLE document, not just within one
        # <svg>. Before this fix, every render() call reused identical ids
        # ("arrow", "cad_grid", "roomClip0", "roomClip1", ...), so
        # url(#roomClip0) on, say, the First Floor SVG resolved to the
        # FIRST "roomClip0" anywhere in the page -- the Ground Floor's --
        # clipping First Floor room text through a rectangle sized for a
        # totally different room. Text positioned outside that borrowed
        # rectangle simply vanished, which is exactly the "only one room
        # shows a label" symptom. Suffixing every id (and every reference
        # to it) with a fresh uid per render() call makes ids globally
        # unique so each floor's clip-paths/markers/patterns only ever
        # resolve to their own definitions.
        uid = uuid.uuid4().hex[:8]
        arrow_id = f"arrow-{uid}"
        grid_id = f"cad_grid-{uid}"

        poly_id = "plotBoundary"
        points_attr = " ".join(f"{px},{py}" for px, py in plot_points)
        BG  = SVGRenderer.BG_COLOR
        vW  = plot_w + 40   # total viewbox width  (20 px margin each side)
        vH  = plot_d + 40   # total viewbox height

        # ── 1. SVG header + defs ────────────────────────────────────────────
        svg = (
            f'<svg viewBox="-20 -20 {vW} {vH}" width="100%" height="100%" '
            f'xmlns="http://www.w3.org/2000/svg" style="background:{BG}">'
        )

        # Solid dark canvas fill
        svg += f'<rect x="-20" y="-20" width="{vW}" height="{vH}" fill="{BG}"/>'

        # Defs: arrow marker, grid pattern, per-room clip-paths added inline
        svg += (
            f'<defs>'
            f'<marker id="{arrow_id}" viewBox="0 0 10 10" refX="5" refY="5" '
            f'markerWidth="4" markerHeight="4" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{SVGRenderer.DIM_COLOR}"/>'
            f'</marker>'
            f'<pattern id="{grid_id}" width="2" height="2" patternUnits="userSpaceOnUse">'
            f'<path d="M 2 0 L 0 0 0 2" fill="none" '
            f'stroke="{SVGRenderer.GRID_COLOR}" stroke-width="0.05"/>'
            f'</pattern>'
            f'</defs>'
        )

        # ── 2. Full-bleed grid (covers entire canvas, NOT clipped to plot) ──
        # This matches the reference screenshot where the grid is visible in
        # the margin area outside the plot polygon as well.
        svg += (
            f'<rect x="-20" y="-20" width="{vW}" height="{vH}" '
            f'fill="url(#{grid_id})"/>'
        )

        # ── 3. Room fills & text labels ─────────────────────────────────────
        for idx, r in enumerate(rooms):
            b            = r.bbox
            name         = r.name.upper()
            area_val     = round(b.area) if b.area is not None else 0
            dim_w        = round(b.width, 1)
            dim_h        = round(b.height, 1)
            area_label   = f"{dim_w}' × {dim_h}' · {area_val} SQ.FT"
            room_clip_id = f"roomClip{idx}-{uid}"
            cm = SVGRenderer._CLIP_MARGIN

            # Per-room clip-path prevents label bleeding into walls /
            # neighbours, but is intentionally slightly larger than the
            # room's own bbox (by _CLIP_MARGIN) so text held at the
            # legibility floor in an undersized room can spill a little
            # instead of being invisibly cropped. The FILL rect below
            # stays at the exact bbox -- only the text clip gets the
            # tolerance, so room colours never bleed into neighbours.
            svg += (
                f'<clipPath id="{room_clip_id}">'
                f'<rect x="{b.x1 - cm}" y="{b.y1 - cm}" '
                f'width="{b.width + 2 * cm}" height="{b.height + 2 * cm}"/>'
                f'</clipPath>'
            )

            # Semi-transparent fill so the dark canvas shows through subtly
            svg += (
                f'<rect x="{b.x1}" y="{b.y1}" '
                f'width="{b.width}" height="{b.height}" '
                f'fill="{r.paint_hex}" '
                f'fill-opacity="{SVGRenderer.FILL_OPACITY}" stroke="none"/>'
            )

            name_lines, name_font, area_font, show_area = SVGRenderer._fit_room_text(
                name, area_label, b.width, b.height
            )

            block_h = len(name_lines) * name_font * SVGRenderer._LINE_HEIGHT_RATIO
            if show_area:
                block_h += area_font * SVGRenderer._LINE_HEIGHT_RATIO
            start_y = r.center.y - block_h / 2 + name_font * 0.78

            svg += f'<g clip-path="url(#{room_clip_id})">'
            for i, line in enumerate(name_lines):
                ly = start_y + i * name_font * SVGRenderer._LINE_HEIGHT_RATIO
                svg += (
                    f'<text x="{r.center.x}" y="{ly}" font-family="monospace" '
                    f'font-size="{name_font}" font-weight="bold" '
                    f'fill="{SVGRenderer.ROOM_TEXT_COLOR}" '
                    f'text-anchor="middle">{line}</text>'
                )
            if show_area:
                area_y = (
                    start_y
                    + len(name_lines) * name_font * SVGRenderer._LINE_HEIGHT_RATIO
                    + area_font * 0.78
                )
                svg += (
                    f'<text x="{r.center.x}" y="{area_y}" font-family="monospace" '
                    f'font-size="{area_font}" '
                    f'fill="{SVGRenderer.AREA_TEXT_COLOR}" '
                    f'text-anchor="middle">{area_label}</text>'
                )
            svg += '</g>'

        # ── 4. Plot boundary polygon ─────────────────────────────────────────
        # Drawn on top of room fills so the true plot silhouette is always
        # clearly visible against the dark canvas (gold outline, no fill).
        svg += (
            f'<polygon points="{points_attr}" fill="none" '
            f'stroke="{SVGRenderer.PLOT_STROKE}" '
            f'stroke-width="{SVGRenderer.PLOT_SW}" stroke-dasharray="0"/>'
        )

        # ── 5. Walls ─────────────────────────────────────────────────────────
        for w in walls:
            color = SVGRenderer.EXT_WALL_COLOR if w.is_exterior else SVGRenderer.INT_WALL_COLOR
            svg += (
                f'<line x1="{w.x1}" y1="{w.y1}" x2="{w.x2}" y2="{w.y2}" '
                f'stroke="{color}" stroke-width="{w.thickness}" '
                f'stroke-linecap="square"/>'
            )

        # ── 6. Portals (windows and doors) ───────────────────────────────────
        for p in portals:
            if p.portal_type == "window":
                # Thick cyan bar drawn directly on the wall line —
                # WIN_SW (2.0) gives the prominent rectangular appearance
                # that matches the reference screenshot.
                svg += (
                    f'<line x1="{p.x1}" y1="{p.y1}" x2="{p.x2}" y2="{p.y2}" '
                    f'stroke="{SVGRenderer.WIN_COLOR}" '
                    f'stroke-width="{SVGRenderer.WIN_SW}" '
                    f'stroke-linecap="square"/>'
                )

            elif p.portal_type == "door":
                # a) Clear the wall line with the canvas colour so the door
                #    opening appears as a clean gap (no white bleed on dark bg)
                svg += (
                    f'<line x1="{p.x1}" y1="{p.y1}" x2="{p.x2}" y2="{p.y2}" '
                    f'stroke="{SVGRenderer.DOOR_CLEAR}" '
                    f'stroke-width="{SVGRenderer.DOOR_CLEAR_SW}"/>'
                )

                if p.is_horizontal:
                    swing_end_y = p.y1 + (3.0 * p.swing_direction_y)
                    sweep = "1" if p.swing_direction_x > 0 else "0"
                    arc_end_x = p.hinge_x + (3.0 * p.swing_direction_x)

                    # b) Door panel (gold line from hinge)
                    svg += (
                        f'<line x1="{p.hinge_x}" y1="{p.y1}" '
                        f'x2="{p.hinge_x}" y2="{swing_end_y}" '
                        f'stroke="{SVGRenderer.DOOR_PANEL_COL}" '
                        f'stroke-width="{SVGRenderer.DOOR_PANEL_SW}"/>'
                    )
                    # c) Swing arc (muted gold, dashed)
                    svg += (
                        f'<path d="M {arc_end_x} {p.y1} A 3 3 0 0 {sweep} '
                        f'{p.hinge_x} {swing_end_y}" fill="none" '
                        f'stroke="{SVGRenderer.DOOR_ARC_COL}" '
                        f'stroke-width="{SVGRenderer.DOOR_ARC_SW}" '
                        f'stroke-dasharray="0.5"/>'
                    )
                else:
                    swing_end_x = p.x1 + (3.0 * p.swing_direction_x)
                    sweep = "1" if p.swing_direction_y > 0 else "0"
                    arc_end_y = p.hinge_y + (3.0 * p.swing_direction_y)

                    # b) Door panel
                    svg += (
                        f'<line x1="{p.x1}" y1="{p.hinge_y}" '
                        f'x2="{swing_end_x}" y2="{p.hinge_y}" '
                        f'stroke="{SVGRenderer.DOOR_PANEL_COL}" '
                        f'stroke-width="{SVGRenderer.DOOR_PANEL_SW}"/>'
                    )
                    # c) Swing arc
                    svg += (
                        f'<path d="M {p.x1} {arc_end_y} A 3 3 0 0 {sweep} '
                        f'{swing_end_x} {p.hinge_y}" fill="none" '
                        f'stroke="{SVGRenderer.DOOR_ARC_COL}" '
                        f'stroke-width="{SVGRenderer.DOOR_ARC_SW}" '
                        f'stroke-dasharray="0.5"/>'
                    )

        # ── 7. Dimension lines ───────────────────────────────────────────────
        for d in dimensions:
            text_x = (d.x1 + d.x2) / 2
            text_y = (d.y1 + d.y2) / 2

            svg += (
                f'<line x1="{d.x1}" y1="{d.y1}" x2="{d.x2}" y2="{d.y2}" '
                f'stroke="{SVGRenderer.DIM_COLOR}" '
                f'stroke-width="{SVGRenderer.DIM_SW}" '
                f'marker-start="url(#{arrow_id})" marker-end="url(#{arrow_id})"/>'
            )

            if d.is_horizontal:
                svg += (
                    f'<text x="{text_x}" y="{text_y - 1.5}" '
                    f'font-family="monospace" font-size="{SVGRenderer.DIM_FONT_SZ}" '
                    f'fill="{SVGRenderer.DIM_COLOR}" text-anchor="middle">'
                    f'{d.label}</text>'
                )
            else:
                svg += (
                    f'<text x="{text_x - 1.5}" y="{text_y}" '
                    f'font-family="monospace" font-size="{SVGRenderer.DIM_FONT_SZ}" '
                    f'fill="{SVGRenderer.DIM_COLOR}" text-anchor="middle" '
                    f'transform="rotate(-90, {text_x - 1.5}, {text_y})">'
                    f'{d.label}</text>'
                )

        # ── 8. North compass overlay ─────────────────────────────────────────
        compass_x = plot_w + 6
        compass_y = plot_d + 6
        svg += (
            f'<g transform="translate({compass_x}, {compass_y})">'
            f'<circle cx="0" cy="0" r="2.5" fill="none" '
            f'stroke="{SVGRenderer.COMPASS_COLOR}" stroke-width="0.4"/>'
            f'<polygon points="0,-3 1.5,1.5 0,0 -1.5,1.5" '
            f'fill="{SVGRenderer.COMPASS_COLOR}"/>'
            f'<text x="0" y="4.5" font-family="monospace" font-size="1.2" '
            f'fill="{SVGRenderer.COMPASS_COLOR}" text-anchor="middle">N</text>'
            f'</g>'
        )

        svg += '</svg>'
        return svg