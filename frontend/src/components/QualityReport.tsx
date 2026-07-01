import React from 'react';
import { LayoutOption } from '../hooks/useAetherState';

interface Props { option: LayoutOption; }

export const QualityReport: React.FC<Props> = ({ option }) => {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <h3 className="text-sm font-bold tracking-wider uppercase text-cyan-400">Quantitative Compliance Metrics</h3>
      
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="bg-black p-3 rounded-lg border border-gray-800">
          <div className="text-xs text-gray-400">Space Utilization</div>
          <div className="text-lg font-mono font-bold text-emerald-400">{option.space_utilization_score}%</div>
        </div>
        <div className="bg-black p-3 rounded-lg border border-gray-800">
          <div className="text-xs text-gray-400">Circulation Loss</div>
          <div className="text-lg font-mono font-bold text-amber-400">{option.circulation_score}%</div>
        </div>
        <div className="bg-black p-3 rounded-lg border border-gray-800">
          <div className="text-xs text-gray-400">Vastu Score</div>
          <div className="text-lg font-mono font-bold text-cyan-400">{option.vastu_score}/100</div>
        </div>
      </div>

      <div className="bg-black p-4 rounded-lg border border-gray-800">
        <div className="text-xs font-bold text-gray-300 mb-2">Orientation Validation Log:</div>
        <ul className="text-xs space-y-1 font-mono text-gray-400">
          {option.vastu_report.map((line, idx) => (
            <li key={idx} className={line.startsWith('PASS') ? 'text-emerald-500' : 'text-amber-500'}>
              • {line}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};