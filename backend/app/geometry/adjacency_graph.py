from collections import deque
from typing import Dict, Any, List, Set, Tuple, Optional
from backend.app.geometry.models import RoomType

class GraphNode:
    """Represents an unallocated room or functional space within the structural topology."""
    def __init__(self, room_id: str, name: str, room_type: str, floor_index: int):
        self.room_id: str = room_id
        self.name: str = name
        self.room_type: str = room_type.lower().strip()
        self.floor_index: int = floor_index
        self.metadata: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "room_id": self.room_id,
            "name": self.name,
            "room_type": self.room_type,
            "floor_index": self.floor_index,
            "metadata": self.metadata
        }

class ArchitecturalAdjacencyGraph:
    """Deterministic relational graph managing architectural adjacencies and flow distribution."""
    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.adjacency_list: Dict[str, Set[str]] = {}

    def add_node(self, room_id: str, name: str, room_type: str, floor_index: int = 0) -> bool:
        """Adds an architectural node into the target calculation plane."""
        if room_id in self.nodes:
            return False
        
        node = GraphNode(room_id=room_id, name=name, room_type=room_type, floor_index=floor_index)
        self.nodes[room_id] = node
        self.adjacency_list[room_id] = set()
        return True

    def remove_node(self, room_id: str) -> bool:
        """Safely purges an architectural node and resolves orphaned edges."""
        if room_id not in self.nodes:
            if room_id not in self.nodes:
                return False
        
        # Dissolve all relational ties across adjacent elements
        adjacent_nodes = list(self.adjacency_list[room_id])
        for target_id in adjacent_nodes:
            self.disconnect_rooms(room_id, target_id)
            
        del self.nodes[room_id]
        del self.adjacency_list[room_id]
        return True

    def connect_rooms(self, room_id_a: str, room_id_b: str) -> bool:
        """Establishes a bi-directional structural boundary opening between two entities."""
        if room_id_a not in self.nodes or room_id_b not in self.nodes:
            return False
        if room_id_a == room_id_b:
            return False
            
        self.adjacency_list[room_id_a].add(room_id_b)
        self.adjacency_list[room_id_b].add(room_id_a)
        return True

    def disconnect_rooms(self, room_id_a: str, room_id_b: str) -> bool:
        """Dissolves an adjacency connection between two structural nodes."""
        if room_id_a not in self.adjacency_list or room_id_b not in self.adjacency_list:
            return False
            
        if room_id_b in self.adjacency_list[room_id_a]:
            self.adjacency_list[room_id_a].remove(room_id_b)
        if room_id_a in self.adjacency_list[room_id_b]:
            self.adjacency_list[room_id_b].remove(room_id_a)
        return True

    def validate_graph(self) -> Tuple[bool, List[str]]:
        """
        Executes structural architectural compilation checks deterministically.
        Returns a boolean validation state alongside diagnostic warnings.
        """
        is_valid = True
        errors = []

        if not self.nodes:
            return True, []

        # Find isolated structures via absolute adjacency counts
        for r_id, neighbors in self.adjacency_list.items():
            node = self.nodes[r_id]
            if len(neighbors) == 0:
                # Garden and Parking can be root-adjacent or face boundary zones
                if node.room_type not in ["garden", "parking"]:
                    is_valid = False
                    errors.append(f"Isolated structure detected: Space '{node.name}' ({r_id}) has no access pathways.")

        # Architectural standard compliance checking
        for r_id, node in self.nodes.items():
            neighbors = self.adjacency_list[r_id]
            neighbor_types = {self.nodes[n].room_type for n in neighbors}
            neighbor_names = {self.nodes[n].name.lower() for n in neighbors}

            # Rule: Kitchen must connect to dining, family hall, or corridor transitions
            if "kitchen" in node.room_type:
                if not any(t in neighbor_types for t in ["dining", "corridor", "living"]) and not any("dining" in name for name in neighbor_names):
                    is_valid = False
                    errors.append(f"Circulation violation: Kitchen '{node.name}' must directly connect to dining or living space.")

            # Rule: Bedrooms must link to transit corridors, common access halls, or central lobbies
            if "bedroom" in node.room_type:
                if not any(t in neighbor_types for t in ["corridor", "living", "stairs"]):
                    is_valid = False
                    errors.append(f"Circulation containment failure: Bedroom '{node.name}' requires transition access to core circulation infrastructure.")

            # Rule: Bathrooms must link safely to corridors or associated bedrooms
            if "bathroom" in node.room_type or "toilet" in node.room_type:
                if not any(t in neighbor_types for t in ["corridor", "bedroom", "living", "utility"]):
                    is_valid = False
                    errors.append(f"Egress error: Bathroom '{node.name}' must be attached to a bedroom or link directly to common areas.")

            # Rule: Parking must link to entryways, porches, or external access lobbies
            if "parking" in node.room_type:
                if not any(t in neighbor_types for t in ["living", "corridor", "garden"]):
                    if len(neighbors) == 0:
                        is_valid = False
                        errors.append(f"Access error: Parking facility '{node.name}' must remain accessible to standard circulation paths.")

        return is_valid, errors

    def shortest_path(self, start_id: str, end_id: str) -> List[str]:
        """Calculates topological walking steps between two elements using Breadth-First Search."""
        if start_id not in self.nodes or end_id not in self.nodes:
            return []
        if start_id == end_id:
            return [start_id]

        queue = deque([[start_id]])
        visited = {start_id}

        while queue:
            path = queue.popleft()
            current = path[-1]

            if current == end_id:
                return path

            for neighbor in sorted(list(self.adjacency_list[current])):  # Sorted for deterministic traversal path stability
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = list(path)
                    new_path.append(neighbor)
                    queue.append(new_path)

        return []

    def circulation_order(self, start_id: str) -> List[str]:
        """Maps functional structural transitions deterministically using Depth-First Search."""
        if start_id not in self.nodes:
            return []

        visited = []
        visited_set = set()

        def dfs_traverse(current_id: str):
            visited.append(current_id)
            visited_set.add(current_id)
            # Sort neighbors alphabetically by ID to guarantee deterministic outputs
            neighbors = sorted(list(self.adjacency_list[current_id]))
            for next_node in neighbors:
                if next_node not in visited_set:
                    dfs_traverse(next_node)

        dfs_traverse(start_id)
        return visited

    def entrance_path(self, entrance_id: str) -> Dict[str, List[str]]:
        """Generates topological routes from a single entry point out to all reachable layout structures."""
        paths = {}
        if entrance_id not in self.nodes:
            return paths

        for target_id in self.nodes.keys():
            if target_id != entrance_id:
                path = self.shortest_path(entrance_id, target_id)
                if path:
                    paths[target_id] = path
        return paths

    def export_graph(self) -> Dict[str, Any]:
        """Serializes current relational model state variables for downstream operations processing."""
        exported_nodes = {r_id: node.to_dict() for r_id, node in self.nodes.items()}
        exported_edges = []
        
        seen_edges = set()
        for node_id, neighbors in self.adjacency_list.items():
            for neighbor_id in neighbors:
                edge_signature = tuple(sorted([node_id, neighbor_id]))
                if edge_signature not in seen_edges:
                    seen_edges.add(edge_signature)
                    exported_edges.append({
                        "source": edge_signature[0],
                        "target": edge_signature[1]
                    })

        return {
            "nodes": exported_nodes,
            "edges": exported_edges
        }