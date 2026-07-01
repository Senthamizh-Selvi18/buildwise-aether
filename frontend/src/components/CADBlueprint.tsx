import React, { useRef, useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface RoomData {
  name: string;
  x1?: number; y1?: number; x2?: number; y2?: number;
  x?: number; y?: number; width?: number; height?: number;
  area_sqft?: number;
  color?: string;
}

interface DoorData {
  x: number; y: number; wall: string;
}

interface WindowData {
  x: number; y: number; wall: string;
}

interface DimensionData {
  total_width?: number;
  total_length?: number;
  plot_width_ft?: number;
  plot_depth_ft?: number;
}

interface FloorData {
  floor_name?: string;
  level?: string;
  svg_dump?: string;
  rooms?: RoomData[];
  doors?: DoorData[];
  windows?: WindowData[];
  dimensions?: DimensionData;
  dimensions_data?: DimensionData;
}

interface CADBlueprintProps {
  floorData: FloorData;
}

export const CADBlueprint: React.FC<CADBlueprintProps> = ({ floorData }) => {
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const [renderMode, setRenderMode] = useState<'svg_dump' | 'rooms' | 'empty'>('empty');

  useEffect(() => {
    // Determine render mode based on what data is available
    if (floorData?.svg_dump && floorData.svg_dump.trim().length > 50) {
      setRenderMode('svg_dump');
    } else if (floorData?.rooms && floorData.rooms.length > 0) {
      setRenderMode('rooms');
    } else {
      setRenderMode('empty');
    }
  }, [floorData]);

  const floorLabel = floorData?.floor_name || floorData?.level || 'Floor Plan';
  const dims = floorData?.dimensions || floorData?.dimensions_data;
  const totalWidth = dims?.total_width || dims?.plot_width_ft || 30;
  const totalLength = dims?.total_length || dims?.plot_depth_ft || 40;

  // ── MODE 1: Render backend SVG directly ──────────────────────────────────
  if (renderMode === 'svg_dump') {
    // Make the SVG responsive: strip fixed width/height attrs, ensure viewBox
    let svg = floorData.svg_dump!;

    // If SVG lacks a viewBox, inject one from width/height attrs
    if (!svg.includes('viewBox')) {
      const wMatch = svg.match(/width="([^"]+)"/);
      const hMatch = svg.match(/height="([^"]+)"/);
      if (wMatch && hMatch) {
        const w = parseFloat(wMatch[1]);
        const h = parseFloat(hMatch[1]);
        if (!isNaN(w) && !isNaN(h)) {
          svg = svg.replace('<svg', `<svg viewBox="0 0 ${w} ${h}"`);
        }
      }
    }

    // Make width/height 100% so it fills the container responsively
    svg = svg.replace(/(<svg[^>]*)\s+width="[^"]*"/, '$1 width="100%"');
    svg = svg.replace(/(<svg[^>]*)\s+height="[^"]*"/, '$1 height="auto"');

    // If SVG has no explicit styling, inject a dark background to match the theme
    if (!svg.includes('background') && !svg.includes('style="')) {
      svg = svg.replace('<svg', '<svg style="background:#050403;border-radius:8px;"');
    }

    return (
      <div style={{ position: 'relative', width: '100%', maxWidth: '800px', marginInline: 'auto' }}>
        {/* Header bar */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '0 4px 10px 4px', marginBottom: '12px',
          borderBottom: '1px solid rgba(212,175,55,0.12)',
          fontFamily: 'var(--font-mono)', fontSize: '10.5px', color: 'var(--text-secondary)'
        }}>
          <span style={{ color: 'var(--gold-light)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            {floorLabel}
          </span>
          <span>PLOT: {totalWidth}′ × {totalLength}′</span>
        </div>

        {/* SVG rendered directly from backend */}
        <motion.div
          ref={svgContainerRef}
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          style={{
            backgroundColor: '#050403',
            borderRadius: '12px',
            border: '1px solid rgba(212,175,55,0.15)',
            boxShadow: 'inset 0 4px 30px rgba(0,0,0,0.85)',
            overflow: 'hidden',
            width: '100%',
          }}
          dangerouslySetInnerHTML={{ __html: svg }}
        />

        {/* Legend */}
        <div style={{
          display: 'flex', gap: '20px', justifyContent: 'center', marginTop: '12px',
          fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)'
        }}>
          <span>▬ Wall</span>
          <span style={{ color: '#f59e0b' }}>⌒ Door</span>
          <span style={{ color: '#3b82f6' }}>━ Window</span>
          <span style={{ color: 'var(--gold-core)' }}>╌ Plot Boundary</span>
        </div>
      </div>
    );
  }

  // ── MODE 2: Fallback — draw rooms from coordinate data ───────────────────
  if (renderMode === 'rooms') {
    const rooms = floorData.rooms!;

    // Normalize rooms: support both {x1,y1,x2,y2} and {x,y,width,height}
    const normalized = rooms.map(r => ({
      name: r.name,
      x: r.x1 ?? r.x ?? 0,
      y: r.y1 ?? r.y ?? 0,
      w: r.x2 != null && r.x1 != null ? r.x2 - r.x1 : (r.width ?? 5),
      h: r.y2 != null && r.y1 != null ? r.y2 - r.y1 : (r.height ?? 5),
      area: r.area_sqft,
      color: r.color,
    }));

    const viewWidth = 640;
    const viewHeight = 480;
    const scaleX = (viewWidth - 40) / totalWidth;
    const scaleY = (viewHeight - 40) / totalLength;
    const scale = Math.min(scaleX, scaleY) * 0.9;
    const offsetX = (viewWidth - totalWidth * scale) / 2;
    const offsetY = (viewHeight - totalLength * scale) / 2;

    // Room color palette (fallback colors)
    const roomColors: Record<string, string> = {
      'living': 'rgba(212,175,55,0.08)',
      'bedroom': 'rgba(59,130,246,0.08)',
      'kitchen': 'rgba(239,68,68,0.08)',
      'bathroom': 'rgba(20,184,166,0.08)',
      'dining': 'rgba(168,85,247,0.08)',
      'parking': 'rgba(100,116,139,0.08)',
      'pooja': 'rgba(245,158,11,0.08)',
      'staircase': 'rgba(156,163,175,0.08)',
      'balcony': 'rgba(34,197,94,0.08)',
      'garden': 'rgba(34,197,94,0.08)',
    };

    const getRoomColor = (name: string, color?: string) => {
      if (color) return color;
      const key = Object.keys(roomColors).find(k => name.toLowerCase().includes(k));
      return key ? roomColors[key] : 'rgba(212,175,55,0.04)';
    };

    return (
      <div style={{ position: 'relative', width: '100%', maxWidth: '800px', marginInline: 'auto' }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '0 4px 10px 4px', marginBottom: '12px',
          borderBottom: '1px solid rgba(212,175,55,0.12)',
          fontFamily: 'var(--font-mono)', fontSize: '10.5px', color: 'var(--text-secondary)'
        }}>
          <span style={{ color: 'var(--gold-light)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            {floorLabel}
          </span>
          <span>PLOT: {totalWidth}′ × {totalLength}′ · {rooms.length} ROOMS</span>
        </div>

        <div style={{
          backgroundColor: '#050403', borderRadius: '12px', padding: '16px',
          border: '1px solid rgba(212,175,55,0.15)',
          boxShadow: 'inset 0 4px 30px rgba(0,0,0,0.85)',
        }}>
          <svg viewBox={`0 0 ${viewWidth} ${viewHeight}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
            <defs>
              <pattern id={`grid-${floorLabel}`} width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(212,175,55,0.04)" strokeWidth="0.5" />
              </pattern>
            </defs>
            <rect width={viewWidth} height={viewHeight} fill={`url(#grid-${floorLabel})`} />

            {/* Plot boundary */}
            <rect
              x={offsetX} y={offsetY}
              width={totalWidth * scale} height={totalLength * scale}
              fill="none" stroke="rgba(212,175,55,0.3)" strokeWidth="1.5" strokeDasharray="6 4"
            />

            {normalized.map((room, idx) => {
              const rx = offsetX + room.x * scale;
              const ry = offsetY + room.y * scale;
              const rw = Math.max(room.w * scale, 1);
              const rh = Math.max(room.h * scale, 1);
              const cx = rx + rw / 2;
              const cy = ry + rh / 2;
              const fontSize = Math.min(rw, rh) < 40 ? 7 : rw < 80 ? 9 : 11;

              return (
                <motion.g
                  key={idx}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.5, delay: idx * 0.05 }}
                >
                  <rect
                    x={rx} y={ry} width={rw} height={rh}
                    fill={getRoomColor(room.name, room.color)}
                    stroke="var(--gold-core)" strokeWidth="1.5" strokeLinejoin="round"
                  />
                  <rect
                    x={rx + 2} y={ry + 2} width={rw - 4} height={rh - 4}
                    fill="none" stroke="rgba(212,175,55,0.15)" strokeWidth="0.5"
                  />
                  <text
                    x={cx} y={room.area ? cy - 5 : cy}
                    textAnchor="middle" dominantBaseline="middle"
                    fill="#FFFFFF" fontSize={fontSize} fontWeight="600"
                    style={{ fontFamily: 'sans-serif', textTransform: 'uppercase', letterSpacing: '0.04em' }}
                  >
                    {room.name}
                  </text>
                  {room.area && (
                    <text
                      x={cx} y={cy + fontSize}
                      textAnchor="middle" dominantBaseline="middle"
                      fill="rgba(212,175,55,0.7)" fontSize={fontSize - 1}
                      style={{ fontFamily: 'monospace' }}
                    >
                      {Math.round(room.area)} sqft
                    </text>
                  )}
                </motion.g>
              );
            })}
          </svg>
        </div>

        <div style={{
          display: 'flex', gap: '20px', justifyContent: 'center', marginTop: '12px',
          fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)'
        }}>
          <span>▬ Wall</span>
          <span style={{ color: 'rgba(212,175,55,0.6)' }}>╌ Plot Boundary</span>
        </div>
      </div>
    );
  }

  // ── MODE 3: Empty state ───────────────────────────────────────────────────
  return (
    <div style={{
      width: '100%', padding: '48px 24px', textAlign: 'center',
      fontFamily: 'var(--font-mono)', fontSize: '12px',
      color: 'var(--text-muted)', border: '1px dashed rgba(212,175,55,0.15)',
      borderRadius: '12px', backgroundColor: 'rgba(5,4,3,0.6)'
    }}>
      <div style={{ fontSize: '24px', marginBottom: '12px', opacity: 0.3 }}>⬚</div>
      Floor plan data not yet generated. Execute compilation above.
    </div>
  );
};