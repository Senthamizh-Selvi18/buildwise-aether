import uuid
from typing import List
from backend.app.core.geometry.models import RoomGeometry, BoundingBox

class RoomAllocator:
    """
    Executes Binary Space Partitioning (BSP) to divide mathematical plot area
    into proportional, non-overlapping RoomGeometry objects.

    Also supports irregular plots: allocate_multi() takes the list of
    axis-aligned rectangles an irregular polygon was decomposed into
    (see plot_geometry.PlotShapeBuilder.decompose) and distributes the
    EXACT room list the caller supplied across them -- every room the
    user asked for is placed exactly once, nothing is invented and
    nothing is dropped, regardless of how many rectangles the plot
    shape breaks down into.
    """
    MIN_ROOM_SPAN = 6.0

    @staticmethod
    def _get_room_weight(room_name: str) -> float:
        name = room_name.lower()
        if "living" in name or "hall" in name: return 3.5
        if "master" in name or "parking" in name: return 2.5
        if "kitchen" in name or "dining" in name: return 1.8
        if "bedroom" in name: return 2.0
        if "bath" in name or "toilet" in name: return 0.8
        if "pooja" in name or "stair" in name: return 0.6
        return 1.2

    @staticmethod
    def allocate(x: float, y: float, w: float, h: float, rooms: List[str], is_horizontal: bool, mode: str) -> List[RoomGeometry]:
        if not rooms:
            return []
            
        # Base case: Single room fills the remaining allocated partition
        if len(rooms) == 1:
            return [RoomGeometry(
                id=uuid.uuid4().hex[:8],
                name=rooms[0],
                bbox=BoundingBox(x1=x, y1=y, x2=x + w, y2=y + h)
                # Paint defaults are handled by the dataclass, palette applied later by orchestrator
            )]
        
        # Determine split midpoint based on algorithmic weights
        mid = len(rooms) // 2
        rooms1, rooms2 = rooms[:mid], rooms[mid:]
        
        weight1 = sum(RoomAllocator._get_room_weight(r) for r in rooms1)
        weight2 = sum(RoomAllocator._get_room_weight(r) for r in rooms2)
        
        target_ratio = weight1 / (weight1 + weight2) if (weight1 + weight2) > 0 else 0.5

        # Apply AI-driven spatial bias based on user layout preference
        ratio = max(0.35, min(0.65, target_ratio * 1.1)) if mode == "vastu_prioritization" else max(0.3, min(0.7, target_ratio))
        
        # Enforce minimum liveable dimensions (prevent rendering structurally impossible slivers)
        if is_horizontal and h > (RoomAllocator.MIN_ROOM_SPAN * 2):
            split_y = y + max(RoomAllocator.MIN_ROOM_SPAN, min(h - RoomAllocator.MIN_ROOM_SPAN, h * ratio))
            return RoomAllocator.allocate(x, y, w, split_y - y, rooms1, not is_horizontal, mode) + \
                   RoomAllocator.allocate(x, split_y, w, h - (split_y - y), rooms2, not is_horizontal, mode)
                   
        elif w > (RoomAllocator.MIN_ROOM_SPAN * 2):
            split_x = x + max(RoomAllocator.MIN_ROOM_SPAN, min(w - RoomAllocator.MIN_ROOM_SPAN, w * ratio))
            return RoomAllocator.allocate(x, y, split_x - x, h, rooms1, not is_horizontal, mode) + \
                   RoomAllocator.allocate(split_x, y, w - (split_x - x), h, rooms2, not is_horizontal, mode)
                   
        else:
            # Fallback axis split if strict dimensional constraints force it.
            # w and h are both too small here to guarantee a full
            # MIN_ROOM_SPAN on both sides (that's *why* we're in this
            # branch) -- but the split point must still be clamped to some
            # hard floor. Left totally unclamped, deep recursion on
            # room-dense floors (e.g. several bedrooms + attached
            # bathrooms upstairs) can push a partition's width or height
            # to near zero. A near-zero bbox doesn't just look small --
            # SVGRenderer clips each room's label to its own bbox size, so
            # a degenerate bbox makes the room's name/dimensions (and
            # fill) disappear from the render entirely. Clamping to a
            # reduced hard minimum keeps every room visibly, legibly
            # rendered even when the ideal 6ft minimum isn't achievable.
            HARD_MIN_SPAN = 2.0  # smallest allowable span (ft) -- still visible/legible
            if is_horizontal:
                span = (max(HARD_MIN_SPAN, min(w - HARD_MIN_SPAN, w * ratio))
                        if w > HARD_MIN_SPAN * 2 else w / 2)
                split_x = x + span
                return RoomAllocator.allocate(x, y, split_x - x, h, rooms1, not is_horizontal, mode) + \
                       RoomAllocator.allocate(split_x, y, w - (split_x - x), h, rooms2, not is_horizontal, mode)
            else:
                span = (max(HARD_MIN_SPAN, min(h - HARD_MIN_SPAN, h * ratio))
                        if h > HARD_MIN_SPAN * 2 else h / 2)
                split_y = y + span
                return RoomAllocator.allocate(x, y, w, split_y - y, rooms1, not is_horizontal, mode) + \
                       RoomAllocator.allocate(x, split_y, w, h - (split_y - y), rooms2, not is_horizontal, mode)

    @staticmethod
    def allocate_multi(rectangles: List[BoundingBox], rooms: List[str], mode: str) -> List[RoomGeometry]:
        """
        Distributes `rooms` (in the exact order/content given -- no rooms
        added, removed, or substituted) across one or more rectangles that
        an irregular plot polygon decomposed into. Each rectangle gets a
        room count proportional to its share of the total buildable area
        (largest-remainder method), then RoomAllocator.allocate() runs the
        normal BSP split within each rectangle independently.
        """
        if not rectangles:
            return []
        if not rooms:
            return []
        if len(rectangles) == 1:
            r = rectangles[0]
            return RoomAllocator.allocate(r.x1, r.y1, r.width, r.height, rooms, r.width >= r.height, mode)

        n = len(rooms)
        total_area = sum(r.area for r in rectangles) or 1.0

        # Proportional base count per rectangle (every rectangle gets at
        # least 1 room whenever there are enough rooms to go around).
        raw = [n * (r.area / total_area) for r in rectangles]
        base = [max(1, int(v)) if n >= len(rectangles) else 0 for v in raw]
        while sum(base) > n:
            i = base.index(max(base))
            base[i] = max(0, base[i] - 1)

        remainder = n - sum(base)
        frac_order = sorted(range(len(rectangles)), key=lambda i: raw[i] - int(raw[i]), reverse=True)
        for i in frac_order:
            if remainder <= 0:
                break
            base[i] += 1
            remainder -= 1

        result: List[RoomGeometry] = []
        idx = 0
        for rect, cnt in zip(rectangles, base):
            chunk = rooms[idx: idx + cnt]
            idx += cnt
            if chunk:
                result.extend(RoomAllocator.allocate(
                    rect.x1, rect.y1, rect.width, rect.height, chunk, rect.width >= rect.height, mode
                ))

        # Rounding can leave a few rooms unplaced -- put them in the
        # largest rectangle so every requested room is still guaranteed
        # to appear (strict adherence to the user's room program).
        if idx < n:
            leftover = rooms[idx:]
            largest = max(rectangles, key=lambda r: r.area)
            result.extend(RoomAllocator.allocate(
                largest.x1, largest.y1, largest.width, largest.height,
                leftover, largest.width >= largest.height, mode
            ))

        return result