import React from 'react';

interface Props {
  shape: string; setShape: (s: string) => void;
  width: number; setWidth: (n: number) => void;
  depth: number; setDepth: (n: number) => void;
  floors: number; setFloors: (n: number) => void;
}

export const PlotSelector: React.FC<Props> = ({ shape, setShape, width, setWidth, depth, setDepth, floors, setFloors }) => {
  return (
    <div className="bg-gray-900 p-5 rounded-xl border border-gray-800 space-y-4 shadow-xl">
      <h3 className="text-sm font-bold tracking-wider uppercase text-cyan-400">Boundary Parameter Control Matrix</h3>
      
      <div>
        <label className="block text-xs text-gray-400 mb-1">Geometric Plot Configuration Profile</label>
        <select value={shape} onChange={(e) => setShape(e.target.value)} className="w-full bg-gray-800 text-white rounded p-2 text-sm border border-gray-700">
          <option value="rectangle">Orthogonal Rectangle (Standard)</option>
          <option value="square">Equilateral Square Perimeter</option>
          <option value="triangle">Angular Wedge Triangle</option>
          <option value="l_shape">Asymmetric L-Shape Boundary</option>
          <option value="irregular">Irregular Polygon Boundary</option>
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-400">Width (ft)</label>
          <input type="number" value={width} onChange={(e) => setWidth(Number(e.target.value))} className="w-full bg-gray-800 text-white rounded p-2 text-sm border border-gray-700" />
        </div>
        <div>
          <label className="block text-xs text-gray-400">Depth (ft)</label>
          <input type="number" value={depth} onChange={(e) => setDepth(Number(e.target.value))} className="w-full bg-gray-800 text-white rounded p-2 text-sm border border-gray-700" />
        </div>
      </div>

      <div>
        <label className="block text-xs text-gray-400 mb-1">Multi-Floor Elevation Stacking Profile ({floors} Floors)</label>
        <input type="range" min="1" max="3" value={floors} onChange={(e) => setFloors(Number(e.target.value))} className="w-full accent-cyan-500" />
      </div>
    </div>
  );
};