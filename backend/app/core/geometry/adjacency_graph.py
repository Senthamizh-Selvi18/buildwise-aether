from typing import List
from backend.app.core.geometry.models import RoomGeometry, AdjacencyEdge

class AdjacencyGraphBuilder:
    """
    Computes shared geometric boundaries between allocated rooms.
    Uses a small floating-point tolerance to ensure mathematical edge cases 
    do not result in disconnected topology.
    """
    TOLERANCE = 0.1

    @staticmethod
    def build(rooms: List[RoomGeometry]) -> List[AdjacencyEdge]:
        edges: List[AdjacencyEdge] = []
        
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                r1 = rooms[i]
                r2 = rooms[j]
                
                # 1. Check Vertical Adjacency (Shared Horizontal Edge)
                # Rooms touch top-to-bottom
                if abs(r1.bbox.y2 - r2.bbox.y1) < AdjacencyGraphBuilder.TOLERANCE or \
                   abs(r2.bbox.y2 - r1.bbox.y1) < AdjacencyGraphBuilder.TOLERANCE:
                    
                    shared_y = r1.bbox.y2 if abs(r1.bbox.y2 - r2.bbox.y1) < AdjacencyGraphBuilder.TOLERANCE else r1.bbox.y1
                    
                    # Calculate horizontal (X-axis) overlap
                    overlap_x1 = max(r1.bbox.x1, r2.bbox.x1)
                    overlap_x2 = min(r1.bbox.x2, r2.bbox.x2)
                    
                    # If the overlap distance is greater than the tolerance, it is a valid edge
                    if overlap_x2 - overlap_x1 > AdjacencyGraphBuilder.TOLERANCE:
                        edges.append(AdjacencyEdge(
                            room_a_id=r1.id,
                            room_b_id=r2.id,
                            x1=overlap_x1,
                            y1=shared_y,
                            x2=overlap_x2,
                            y2=shared_y,
                            is_horizontal=True
                        ))
                        
                # 2. Check Horizontal Adjacency (Shared Vertical Edge)
                # Rooms touch side-to-side
                if abs(r1.bbox.x2 - r2.bbox.x1) < AdjacencyGraphBuilder.TOLERANCE or \
                   abs(r2.bbox.x2 - r1.bbox.x1) < AdjacencyGraphBuilder.TOLERANCE:
                    
                    shared_x = r1.bbox.x2 if abs(r1.bbox.x2 - r2.bbox.x1) < AdjacencyGraphBuilder.TOLERANCE else r1.bbox.x1
                    
                    # Calculate vertical (Y-axis) overlap
                    overlap_y1 = max(r1.bbox.y1, r2.bbox.y1)
                    overlap_y2 = min(r1.bbox.y2, r2.bbox.y2)
                    
                    # If the overlap distance is greater than the tolerance, it is a valid edge
                    if overlap_y2 - overlap_y1 > AdjacencyGraphBuilder.TOLERANCE:
                        edges.append(AdjacencyEdge(
                            room_a_id=r1.id,
                            room_b_id=r2.id,
                            x1=shared_x,
                            y1=overlap_y1,
                            x2=shared_x,
                            y2=overlap_y2,
                            is_horizontal=False
                        ))
                        
        return edges