from typing import List
from backend.app.schemas.floorplan import FurnitureItem, RoomLayout

class DeterministicFurniturePlacer:
    @staticmethod
    def populate_room_interior(room: RoomLayout) -> List[FurnitureItem]:
        items = []
        rx = room.x1
        ry = room.y1
        rw = room.x2 - room.x1
        rh = room.y2 - room.y1
        
        name_lower = room.name.lower()
        
        if "bedroom" in name_lower:
            items.append(FurnitureItem(name="King Bed", type="bed", x=rx + 1.0, y=ry + 1.0, w=6.0, h=6.5))
            items.append(FurnitureItem(name="Wardrobe", type="wardrobe", x=rx + rw - 2.5, y=ry + 1.0, w=2.0, h=4.0))
        elif "kitchen" in name_lower:
            items.append(FurnitureItem(name="Burner Stove", type="stove", x=rx + 0.5, y=ry + 0.5, w=3.0, h=2.0))
            items.append(FurnitureItem(name="Wash Sink", type="sink", x=rx + rw - 3.5, y=ry + 0.5, w=3.0, h=2.0))
        elif "living" in name_lower:
            items.append(FurnitureItem(name="Sectional Sofa", type="sofa", x=rx + 2.0, y=ry + rh - 4.0, w=7.0, h=3.0))
            items.append(FurnitureItem(name="Media Console TV", type="tv", x=rx + 2.0, y=ry + 1.0, w=5.0, h=1.0))
        elif "bathroom" in name_lower or "toilet" in name_lower:
            items.append(FurnitureItem(name="Water Closet Commode", type="toilet", x=rx + 0.5, y=ry + 0.5, w=2.0, h=2.5))
            items.append(FurnitureItem(name="Vanity Basin", type="sink", x=rx + rw - 2.5, y=ry + 0.5, w=2.0, h=2.0))
            
        return items