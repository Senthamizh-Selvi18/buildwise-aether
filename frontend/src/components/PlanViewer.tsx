import React from 'react';
import { FloorPlan } from '../hooks/useAetherState';

interface Props { plan: FloorPlan; }

export const PlanViewer: React.FC<Props> = ({ plan }) => {
  const scale = 8;
  const viewWidth = 450;
  const viewHeight = 450;

  return (
    <div className="bg-black border-2 border-cyan-900 rounded-2xl p-6 shadow-2xl relative overflow-hidden flex flex-col items-center">
      <div className="absolute top-3 left-4 bg-cyan-950/80 text-cyan-400 border border-cyan-800 px-3 py-1 rounded-md text-xs font-mono tracking-widest uppercase">
        Active Viewport: {plan.floor_name}
      </div>

      <svg width={viewWidth} height={viewHeight} className="bg-slate-950 rounded-lg mt-6 border border-gray-900">
        <defs>
          <pattern id="blueprint-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1e293b" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#blueprint-grid)" />

        {plan.rooms.map((room, idx) => {
          const w = (room.x2 - room.x1) * scale;
          const h = (room.y2 - room.y1) * scale;
          const rx = room.x1 * scale + 20;
          const ry = room.y1 * scale + 20;

          return (
            <g key={idx}>
              {/* Outer Room Walls */}
              <rect x={rx} y={ry} width={w} height={h} fill="#020617" fillOpacity="0.75" stroke="#06b6d4" strokeWidth="2.5" strokeDasharray="none" />
              {/* Inner Layout Core Envelope Offset Boundary Line */}
              <rect x={rx + 3} y={ry + 3} width={w - 6} height={h - 6} fill="none" stroke="#0891b2" strokeWidth="0.75" opacity="0.5" />

              {/* Internal Assets Loop */}
              {room.furniture?.map((item, fIdx) => (
                <rect key={fIdx} x={rx + item.x * scale} y={ry + item.y * scale} width={item.w * scale} height={item.h * scale} fill="#1e293b" stroke="#94a3b8" strokeWidth="1" rx="2" />
              ))}

              {/* Doors and Openings */}
              {room.elements?.map((el, eIdx) => {
                if (el.type === 'door') {
                  return <circle key={eIdx} cx={rx} cy={ry} r="10" fill="none" stroke="#f59e0b" strokeWidth="2" strokeDasharray="2,2" />;
                }
                return <line key={eIdx} x1={rx + 10} y1={ry} x2={rx + w - 10} y2={ry} stroke="#3b82f6" strokeWidth="4" />;
              })}

              {/* Dynamic Labels and Dimensions */}
              <text x={rx + w / 2} y={ry + h / 2} textAnchor="middle" fill="#f8fafc" fontSize="10" fontWeight="bold" className="pointer-events-none font-sans">
                {room.name}
              </text>
              <text x={rx + w / 2} y={ry + h / 2 + 12} textAnchor="middle" fill="#22d3ee" fontSize="8" className="pointer-events-none font-mono">
                {room.area_sqft} SQFT
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};