import { useState } from 'react';

export interface Point2D { x: number; y: number; }
export interface FurnitureItem { name: string; type: string; x: number; y: number; w: number; h: number; }
export interface ArchitecturalElement { type: string; x1: number; y1: number; x2: number; y2: number; }
export interface RoomLayout { name: string; label: string; x1: number; y1: number; x2: number; y2: number; area_sqft: number; furniture: FurnitureItem[]; elements: ArchitecturalElement[]; }
export interface FloorPlan { floor_name: string; rooms: RoomLayout[]; walls: Point2D[][]; }
export interface LayoutOption { option_id: string; display_name: string; floors: FloorPlan[]; vastu_score: number; vastu_report: string[]; style_applied: string; paint_palette: any; space_utilization_score: number; circulation_score: number; wasted_area_score: number; explanation: string; }

export const useAetherState = () => {
  const [prompt, setPrompt] = useState('Build a premium modern 3BHK villa with a pooja room');
  const [shape, setShape] = useState('rectangle');
  const [width, setWidth] = useState(40);
  const [depth, setDepth] = useState(60);
  const [floors, setFloors] = useState(2);
  const [activeOption, setActiveOption] = useState('OPTION_A_SPACE');
  const [activeFloorIndex, setActiveFloorIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState<Record<string, LayoutOption> | null>(null);
  const [questions, setQuestions] = useState<string[]>([]);

  const triggerGeneration = async (answers: Record<string, string> = {}) => {
    setLoading(true);
    setQuestions([]);
    try {
      const res = await fetch('http://localhost:8000/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: "session_" + Date.now(),
          user_prompt: prompt,
          plot_shape: shape,
          plot_width: width,
          plot_depth: depth,
          floors_requested: floors,
          current_answers: answers
        })
      });
      const data = await res.json();
      if (data.clarification && data.clarification.requires_clarification) {
        setQuestions(data.clarification.questions);
      } else if (data.options) {
        setOptions(data.options);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return {
    prompt, setPrompt, shape, setShape, width, setWidth, depth, setDepth, floors, setFloors,
    activeOption, setActiveOption, activeFloorIndex, setActiveFloorIndex, loading, options, questions, triggerGeneration
  };
};