import React from "react";
import { motion } from "framer-motion";

export default function BlueprintCanvas({ floorData, planType }) {
  if (!floorData) return null;

  // Sizing matrix configuration
  const viewWidth = 700;
  const viewHeight = 420;
  const padding = 40;

  // Determine scaling ratios dynamically from computed metrics
  const maxRoomX = Math.max(...floorData.rooms.flatMap(r => r.points.map(p => p.x)), 40);
  const maxRoomY = Math.max(...floorData.rooms.flatMap(r => r.points.map(p => p.y)), 30);
  
  const scaleX = (viewWidth - padding * 2) / maxRoomX;
  const scaleY = (viewHeight - padding * 2) / maxRoomY;
  const scale = Math.min(scaleX, scaleY, 12);

  const cx = (viewWidth - maxRoomX * scale) / 2;
  const cy = (viewHeight - maxRoomY * scale) / 2;

  const tX = (val) => cx + val * scale;
  const tY = (val) => cy + val * scale;
  const tW = (val) => val * scale;
  const tH = (val) => val * scale;

  // Custom function to return realistic paint values based on space names
  const getColorTokens = (name) => {
    const n = name.toLowerCase();
    if (n.includes("bedroom")) return { bg: "#f0f9ff", border: "#0ea5e9", text: "#0369a1", label: "Light Blue Paint" };
    if (n.includes("kitchen")) return { bg: "#fffbeb", border: "#f59e0b", text: "#b45309", label: "Cream Paint" };
    if (n.includes("bathroom") || n.includes("toilet")) return { bg: "#ecfeff", border: "#06b6d4", text: "#0e7490", label: "Sky Blue Paint" };
    if (n.includes("dining")) return { bg: "#fefce8", border: "#eab308", text: "#a16207", label: "Light Yellow Paint" };
    if (n.includes("pooja")) return { bg: "#fff7ed", border: "#f97316", text: "#c2410c", label: "Soft Marigold Paint" };
    if (n.includes("parking")) return { bg: "#f1f5f9", border: "#64748b", text: "#475569", label: "Slate Matte Finish" };
    return { bg: "#ffffff", border: "#cbd5e1", text: "#1e293b", label: "Warm White Paint" };
  };

  return (
    <div style={{ backgroundColor: "#0b1329", border: "1px solid #1e293b", borderRadius: "12px", padding: "24px", position: "relative", boxShadow: "inset 0 0 40px rgba(0,0,0,0.5)" }}>
      {/* CAD Overlay Metadata Tags */}
      <div style={{ display: "flex", justifyContent: "between", alignItems: "center", borderBottom: "1px solid #1e293b", paddingBottom: "12px", marginBottom: "16px" }}>
        <div>
          <span style={{ fontFamily: "Space Grotesk", fontSize: "14px", fontWeight: "600", color: "#38bdf8", letterSpacing: "0.5px" }}>
            {floorData.floor_name?.toUpperCase() || "STRUCTURAL FLOOR SHEET"}
          </span>
          <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>SCALE 1:50 | AUTOMATIC VECTOR PARTITION MATRIX</div>
        </div>
        <div style={{ marginLeft: "auto", fontSize: "11px", backgroundColor: "rgba(56,189,248,0.1)", color: "#38bdf8", padding: "4px 8px", borderRadius: "4px", border: "1px solid rgba(56,189,248,0.2)", fontFamily: "Space Grotesk" }}>
          {planType === "vastu" ? "VASTU ALIGNED CORE" : "GEOMETRIC SPACE OPTIMIZED"}
        </div>
      </div>

      {/* Main SVG Plot Canvas Render Pipeline */}
      <svg width="100%" height={viewHeight} viewBox={`0 0 ${viewWidth} ${viewHeight}`} style={{ display: "block" }}>
        {/* Subtle interior measurement lines grid */}
        <defs>
          <pattern id="canvas-grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(56, 189, 248, 0.03)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#canvas-grid)" />

        {/* 1. ROOM POLYGON CARPENTRY FILL LAYER */}
        {floorData.rooms?.map((room, idx) => {
          const tokens = getColorTokens(room.name);
          const pointsString = room.points.map(p => `${tX(p.x)},${tY(p.y)}`).join(" ");
          
          const xs = room.points.map(p => p.x);
          const ys = room.points.map(p => p.y);
          const minX = Math.min(...xs), maxX = Math.max(...xs);
          const minY = Math.min(...ys), maxY = Math.max(...ys);
          const rw = maxX - minX;
          const rh = maxY - minY;

          return (
            <g key={`room-${idx}`}>
              <motion.polygon
                points={pointsString}
                fill={tokens.bg}
                stroke={tokens.border}
                strokeWidth="1.5"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: idx * 0.08 }}
              />
              
              {/* Internal Custom Furniture CAD Blocks Render Engines */}
              {room.name.toLowerCase().includes("bedroom") && (
                <g opacity="0.65" transform={`translate(${tX(minX + rw*0.2)}, ${tY(minY + rh*0.2)})`}>
                  {/* Bed Mattress and Pillow Vector Outlines */}
                  <rect width={tW(rw*0.5)} height={tH(rh*0.5)} fill="none" stroke={tokens.text} strokeWidth="1.5" rx="2" />
                  <rect x="2" y="2" width={tW(rw*0.45)} height={tH(rh*0.12)} fill="none" stroke={tokens.text} strokeWidth="1" />
                  {/* Wardrobe/Closet Track Overlay */}
                  <rect x={tW(rw*0.55)} y="0" width={tW(rw*0.2)} height={tH(rh*0.5)} fill="none" stroke={tokens.text} strokeWidth="1" strokeDasharray="2,2" />
                </g>
              )}

              {/* Sofa & Living Furniture Blocks Layout Renderers */}
              {room.name.toLowerCase().includes("living") && (
                <g opacity="0.65" transform={`translate(${tX(minX + rw*0.25)}, ${tY(minY + rh*0.25)})`}>
                  {/* Sectional sofa configuration */}
                  <path d={`M 0,0 L ${tW(rw*0.5)},0 L ${tW(rw*0.5)},${tH(rh*0.15)} L ${tW(rw*0.15)},${tH(rh*0.15)} L ${tW(rw*0.15)},${tH(rh*0.5)} L 0,${tH(rh*0.5)} Z`} fill="none" stroke={tokens.text} strokeWidth="1.5" />
                  {/* Media TV Screen Console Track */}
                  <rect x="0" y={tH(rh*0.6)} width={tW(rw*0.5)} height="4" fill={tokens.text} />
                </g>
              )}

              {/* Kitchen Counters & Utilities Blocks Renderers */}
              {room.name.toLowerCase().includes("kitchen") && (
                <g opacity="0.65" transform={`translate(${tX(minX)}, ${tY(minY)})`}>
                  {/* Counter Top Tracks */}
                  <path d={`M 0,0 L ${tW(rw)},0 L ${tW(rw)},${tH(rh*0.2)} L ${tW(rw*0.2)},${tH(rh*0.2)} L ${tW(rw*0.2)},${tH(rh)} L 0,${tH(rh)} Z`} fill="none" stroke={tokens.text} strokeWidth="1.5" />
                  {/* Kitchen Sink Basin Circle */}
                  <circle cx={tW(rw*0.5)} cy={tH(rh*0.1)} r="6" fill="none" stroke={tokens.text} strokeWidth="1" />
                </g>
              )}

              {/* Bathroom Fixture Sets Layout Renderers */}
              {(room.name.toLowerCase().includes("bathroom") || room.name.toLowerCase().includes("toilet")) && (
                <g opacity="0.65" transform={`translate(${tX(minX + rw*0.1)}, ${tY(minY + rh*0.1)})`}>
                  {/* Bathtub Oval and Toilet Commode Outlines */}
                  <rect width={tW(rw*0.8)} height={tH(rh*0.3)} rx="8" fill="none" stroke={tokens.text} strokeWidth="1.2" />
                  <circle cx={tW(rw*0.2)} cy={tH(rh*0.7)} r="5" fill="none" stroke={tokens.text} strokeWidth="1.2" />
                  <rect x={tW(rw*0.1)} y={tH(rh*0.78)} width={tW(rw*0.2)} height="6" rx="2" fill="none" stroke={tokens.text} strokeWidth="1" />
                </g>
              )}

              {/* Dining Room Table Configurations Renderers */}
              {room.name.toLowerCase().includes("dining") && (
                <g opacity="0.65" transform={`translate(${tX(minX + rw*0.25)}, ${tY(minY + rh*0.25)})`}>
                  <rect width={tW(rw*0.5)} height={tH(rh*0.4)} rx="4" fill="none" stroke={tokens.text} strokeWidth="1.5" />
                  {/* 4 Dining Seats Circles */}
                  <circle cx={tW(rw*0.25)} cy="-4" r="3" fill="none" stroke={tokens.text} />
                  <circle cx={tW(rw*0.25)} cy={tH(rh*0.4)+4} r="3" fill="none" stroke={tokens.text} />
                  <circle cx="-4" cy={tH(rh*0.2)} r="3" fill="none" stroke={tokens.text} />
                  <circle cx={tW(rw*0.5)+4} cy={tH(rh*0.2)} r="3" fill="none" stroke={tokens.text} />
                </g>
              )}

              {/* Staircase Step Bars Core Render Engine */}
              {room.name.toLowerCase().includes("staircase") && (
                <g opacity="0.5" transform={`translate(${tX(minX)}, ${tY(minY)})`}>
                  {[...Array(6)].map((_, stepIdx) => (
                    <line key={stepIdx} x1="0" y1={tH(rh * (stepIdx / 6))} x2={tW(rw)} y2={tH(rh * (stepIdx / 6))} stroke={tokens.text} strokeWidth="1" />
                  ))}
                </g>
              )}

              {/* Room Text Labels, Dimension Metrics & Architectural Square Footage */}
              <text
                x={tX(room.center_x || (minX + rw / 2))}
                y={tY(room.center_y || (minY + rh / 2)) - 4}
                textAnchor="middle"
                fill={tokens.text}
                style={{ fontFamily: "Space Grotesk", fontSize: "11px", fontWeight: "700", letterSpacing: "0.2px" }}
              >
                {room.name.toUpperCase()}
              </text>
              <text
                x={tX(room.center_x || (minX + rw / 2))}
                y={tY(room.center_y || (minY + rh / 2)) + 10}
                textAnchor="middle"
                fill={tokens.text}
                opacity="0.8"
                style={{ fontSize: "9px", fontWeight: "500" }}
              >
                {Math.round(rw)}' × {Math.round(rh)}' ({room.area_sqft || Math.round(rw * rh)} sqft)
              </text>
            </g>
          );
        })}

        {/* 2. ARCHITECTURAL PORTALS (DOORS & SWINGS AND WINDOWS OVERLAYS) */}
        {floorData.portals?.map((portal, idx) => {
          const dx = portal.x2 - portal.x1;
          const dy = portal.y2 - portal.y1;
          const length = Math.sqrt(dx*dx + dy*dy);
          
          const px1 = tX(portal.x1);
          const py1 = tY(portal.y1);
          const px2 = tX(portal.x2);
          const py2 = tY(portal.y2);

          if (portal.portal_type?.toLowerCase() === "window") {
            return (
              <g key={`window-${idx}`}>
                <line x1={px1} y1={py1} x2={px2} y2={py2} stroke="#38bdf8" strokeWidth="4" />
                <line x1={px1} y1={py1} x2={px2} y2={py2} stroke="#020617" strokeWidth="1.2" />
              </g>
            );
          }

          // Generate detailed 90-degree vector door swing arcs
          const radius = length * scale;
          const pathArcString = `M ${px1},${py1} A ${radius},${radius} 0 0,1 ${px1 + (py2-py1)},${py1 - (px2-px1)}`;

          return (
            <g key={`door-${idx}`} opacity="0.85">
              <line x1={px1} y1={py1} x2={px2} y2={py2} stroke="#ef4444" strokeWidth="1.5" strokeDasharray="3,3" />
              {/* Door Panel Sheet Vector line */}
              <line x1={px1} y1={py1} x2={px1 + (py2-py1)} y2={py1 - (px2-px1)} stroke="#e11d48" strokeWidth="2.5" />
              {/* Open Swing Path Curve */}
              <path d={pathArcString} fill="none" stroke="#f43f5e" strokeWidth="1" strokeDasharray="2,2" />
            </g>
          );
        })}

        {/* 3. SOLID STRUCTURAL THICKENED WALL LAYOUT FRAMES */}
        {floorData.walls?.map((wall, idx) => (
          <motion.line
            key={`wall-${idx}`}
            x1={tX(wall.x1)}
            y1={tY(wall.y1)}
            x2={tX(wall.x2)}
            y2={tY(wall.y2)}
            stroke="#1e293b"
            strokeWidth={wall.is_exterior ? "5" : "3.5"}
            strokeLinecap="square"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1, delay: 0.2 }}
          />
        ))}

        {/* 4. REINFORCED LOAD-BEARING CONCRETE SECTIONS COLUMNS */}
        {floorData.columns?.map((col, idx) => (
          <rect
            key={`col-${idx}`}
            x={tX(col.x) - 3}
            y={tY(col.y) - 3}
            width="6"
            height="6"
            fill="#0f172a"
            stroke="#64748b"
            strokeWidth="1.5"
          />
        ))}
      </svg>
    </div>
  );
}