import React from 'react';

interface EvaluationPanelProps {
  optionData: {
    design_title: string;
    space_efficiency_rating: string;
    space_efficiency_explanation: string;
    vastu_score: number;
    vastu_report_text: string;
    estimated_cost_usd: number;
  };
}

export const EvaluationPanel: React.FC<EvaluationPanelProps> = ({ optionData }) => {
  if (!optionData) return null;

  return (
    <div className="bg-white rounded-2xl border border-slate-100 p-6 space-y-6 shadow-sm text-slate-800">
      <div className="text-xs font-semibold tracking-wider text-slate-400 uppercase border-b border-slate-50 pb-2">
        Plan Summary
      </div>

      <div className="space-y-4">
        {/* Layout Characteristic Card */}
        <div>
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-1">
            Space Layout:
          </div>
          <div className="text-xs font-medium text-slate-700 bg-slate-50 p-2.5 rounded-xl border border-slate-100/60">
            {optionData.space_efficiency_explanation}
          </div>
        </div>

        {/* Alignment Flag Text info label */}
        <div>
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-1">
            Vastu Orientation:
          </div>
          <div className="text-xs font-medium text-slate-700 bg-slate-50 p-2.5 rounded-xl border border-slate-100/60">
            {optionData.vastu_report_text}
          </div>
        </div>

        {/* Total Cost Estimates Field */}
        <div className="pt-4 border-t border-slate-100">
          <div className="text-[10px] uppercase font-bold tracking-wider text-slate-400 mb-0.5">
            Estimated Cost:
          </div>
          <div className="text-2xl font-bold tracking-tight text-slate-900">
            ${optionData.estimated_cost_usd.toLocaleString()}
          </div>
        </div>
      </div>
    </div>
  );
};