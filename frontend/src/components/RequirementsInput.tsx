import React from 'react';

interface Props {
  prompt: string; setPrompt: (s: string) => void;
  loading: boolean; onExecute: () => void;
  questions: string[];
}

export const RequirementsInput: React.FC<Props> = ({ prompt, setPrompt, loading, onExecute, questions }) => {
  return (
    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl space-y-4 shadow-xl">
      <h3 className="text-xs font-mono tracking-widest text-emerald-400 uppercase">Input Extraction Workspace</h3>
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-gray-200 focus:outline-none focus:border-cyan-500" placeholder="Describe spatial properties..." />
      <button onClick={onExecute} disabled={loading} className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-mono text-xs py-2.5 rounded-md uppercase tracking-wider transition-all disabled:opacity-40">
        {loading ? 'Synthesizing Architecture...' : 'Trigger ADK Generation Graph'}
      </button>

      {questions.length > 0 && (
        <div className="bg-amber-950/30 border border-amber-900/50 p-4 rounded-lg space-y-2">
          <div className="text-xs font-bold text-amber-400 font-mono uppercase">Missing Requirements Found:</div>
          {questions.map((q, i) => (
            <div key={i} className="text-xs font-mono text-amber-200/80">• {q}</div>
          ))}
        </div>
      )}
    </div>
  );
};