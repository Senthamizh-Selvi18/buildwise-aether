import React from 'react';

interface Props {
  prompt: string; setPrompt: (s: string) => void;
  loading: boolean; trigger: () => void;
  questions: string[];
}

export const ControlConsole: React.FC<Props> = ({ prompt, setPrompt, loading, trigger, questions }) => {
  return (
    <div className="bg-gray-900 border border-gray-800 p-5 rounded-xl space-y-4 shadow-xl">
      <h3 className="text-sm font-bold tracking-wider uppercase text-cyan-400">Natural Language Translation Console</h3>
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} className="w-full bg-black border border-gray-800 rounded-lg p-3 text-sm text-gray-200 focus:outline-none focus:border-cyan-500" placeholder="State your requirements..." />
      
      <button onClick={() => trigger()} disabled={loading} className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white py-2.5 px-4 rounded-lg font-bold text-sm tracking-widest uppercase transition-all duration-200 disabled:opacity-40">
        {loading ? 'Executing Multi-Agent Sequence...' : 'Synthesize Layout Blueprint'}
      </button>

      {questions.length > 0 && (
        <div className="bg-amber-950/40 border border-amber-900/60 p-4 rounded-lg space-y-2">
          <div className="text-xs font-bold text-amber-400 uppercase tracking-wider">Required Clarifications Missing:</div>
          {questions.map((q, idx) => (
            <div key={idx} className="text-xs text-amber-200 font-sans">• {q}</div>
          ))}
        </div>
      )}
    </div>
  );
};