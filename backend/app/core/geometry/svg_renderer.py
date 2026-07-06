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
    _CHAR_WIDTH_RATIO = 0.62
    _LINE_HEIGHT_RATIO = 1.15
    _MAX_FONT = 2.0
    _MIN_FONT = 0.42

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _balanced_wrap(words: List[str], n_lines: int) -> List[str]:
        """Greedily distribute words across up to n_lines, balancing total
        character length per line so multi-word room names (e.g. 'POOJA
        ROOM', 'MASTER BEDROOM') wrap sensibly instead of overflowing."""
        n_lines = max(1, min(n_lines, len(words)))
        if n_lines == 1:
            return [" ".join(words)]
        lines = [""] * n_lines
        lengths = [0] * n_lines
        for w in words:
            idx = lengths.index(min(lengths))
            lines[idx] = (lines[idx] + " " + w).strip()
            lengths[idx] = len(lines[idx])
        return [l for l in lines if l]

    @staticmethod
    def _fit_room_text(name: str, area_label: str, room_w: float, room_h: float):
        """
        Computes a font size + line layout that is GUARANTEED to fit
        entirely inside the room's own bounding box.

        Earlier versions of this method forced the name font up to a
        "legibility floor" (_MIN_FONT) even when that size didn't actually
        fit the room, on the theory that a slightly-overflowing label is
        better than a tiny one. In practice that overflow gets sliced off
        by the room's own clip-path, which produced two different-looking
        symptoms depending on how much the forced size overflowed by:
          - severe overflow  -> the label was clipped away almost
            entirely, so the room appeared to have NO name at all.
          - moderate overflow -> only a clipped FRAGMENT of the name
            remained visible (e.g. "LIVING" / "ROOM" showing up as
            "..NG" / "..OM"), which is arguably even more confusing than
            a blank room since it looks like corrupted data.

        The fix: the font size is always derived directly from (and can
        therefore never exceed) the room's real available space. A room
        that's too small for a "normal" font size simply gets a smaller
        -- but always complete and always fully visible -- label, instead
        of a bigger font that then gets cut apart by the clip-path.

        Returns:
            (name_lines: List[str], name_font: float,
             area_font: float, show_area: bool)
        """
        pad = min(0.4, room_w * 0.08, room_h * 0.08)
        # Never assume more space is available than the room actually has
        # -- capping avail_w/avail_h at the room's real dimensions (instead
        # of only ever flooring them at 0.6) is what guarantees every font
        # computed below actually fits inside the room, no matter how
        # small that room is.
        avail_w = min(max(room_w - 2 * pad, 0.15), max(room_w, 0.05))
        avail_h = min(max(room_h - 2 * pad, 0.15), max(room_h, 0.05))
        cw = SVGRenderer._CHAR_WIDTH_RATIO
        lh = SVGRenderer._LINE_HEIGHT_RATIO
        words = name.split() or [name]

        # ── Step 1: find the best name-only layout. Trying up to 4 lines
        # (not just 3) gives long multi-word names like "ATTACHED
        # BATHROOM" or "COMMON BATHROOM" more chances to reduce their
        # widest-line character count, which lets a bigger font still
        # fit inside a narrow room. ──
        best_name = None
        max_possible_lines = min(4, len(words)) if len(words) > 1 else 1
        for n_lines in range(1, max_possible_lines + 1):
            lines = SVGRenderer._balanced_wrap(words, n_lines)
            widest = max((len(l) for l in lines), default=1) or 1
            font_by_height = (avail_h * 0.92) / (len(lines) * lh + 1e-6)
            font_by_width = avail_w / (widest * cw)
            font = min(font_by_height, font_by_width, SVGRenderer._MAX_FONT)
            score = font - (len(lines) * 0.05)
            if best_name is None or score > best_name[0]:
                best_name = (score, lines, font)

        _, lines, font = best_name
        # `font` is already the largest size that provably fits this line
        # layout inside avail_w/avail_h -- it must not be pushed any
        # higher, or the label will overflow the clip region and come out
        # either fragmented or invisible. We only round it here; the tiny
        # 0.05 floor exists purely so font-size never rounds down to a
        # literal 0 on a truly degenerate sliver room -- it is NOT a
        # "legibility" floor, so it never re-introduces overflow.
        font = max(round(font, 2), 0.05)

        # ── Step 2: fit the area/dimension label into whatever vertical
        # space is left below the name. Shown whenever there's any
        # meaningful space left, shrunk down as needed rather than dropped.
        name_block_h = len(lines) * font * lh
        remaining_h = avail_h - name_block_h
        show_area = False
        area_font = 0.0
        _AREA_MIN_FONT = 0.2  # smaller floor than name text -- still legible
        if remaining_h >= _AREA_MIN_FONT * lh:
            area_font = min(font * 0.7, remaining_h / lh, avail_w / (max(len(area_label), 1) * cw))
            area_font = max(round(area_font, 2), _AREA_MIN_FONT)
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
            f'<marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" '
            f'markerWidth="4" markerHeight="4" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{SVGRenderer.DIM_COLOR}"/>'
            f'</marker>'
            f'<pattern id="cad_grid" width="2" height="2" patternUnits="userSpaceOnUse">'
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
            f'fill="url(#cad_grid)"/>'
        )

        # ── 3. Room fills & text labels ─────────────────────────────────────
        for idx, r in enumerate(rooms):
            b            = r.bbox
            name         = r.name.upper()
            area_val     = round(b.area) if b.area is not None else 0
            dim_w        = round(b.width, 1)
            dim_h        = round(b.height, 1)
            area_label   = f"{dim_w}' × {dim_h}' · {area_val} SQ.FT"

            # NOTE: room labels are intentionally NOT wrapped in a clip-path.
            # A clip-path sized to the room's own box used to slice small
            # rooms' labels mid-word (e.g. "LIVING ROOM" rendering as just
            # "ING" / "OM") whenever the legibility-floor font made the text
            # wider than the room. A label that slightly overflows into the
            # empty margin around a small room is fully readable; a label
            # that gets clipped mid-word is not -- so no clipping is used.

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
                f'marker-start="url(#arrow)" marker-end="url(#arrow)"/>'
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