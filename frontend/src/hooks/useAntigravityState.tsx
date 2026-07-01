import { useState } from 'react';

export const useAntigravityState = () => {
  const [prompt, setPrompt] = useState('I need a modern 3BHK house on a 1200 sq ft plot with parking, one pooja room and 2 floors.');
  const [activeOption, setActiveOption] = useState('OPTION_A_SPACE');
  const [activeFloor, setActiveFloor] = useState(0);
  const [loading, setLoading] = useState(false);
  const [resultData, setResultData] = useState<any>(null);
  const [clarifications, setClarifications] = useState<string[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [errorMessage, setErrorMessage] = useState<string>('');

  const handleSynthesize = async () => {
    setLoading(true);
    setErrorMessage('');
    try {
      const response = await fetch('http://127.0.0.1:8000/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: "session_" + Date.now(),
          user_prompt: prompt,
          current_answers: answers
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        setErrorMessage(errData.detail || "The structural arrangement is invalid for this configuration space.");
        setResultData(null);
        return;
      }

      const data = await response.json();
      if (data.requires_clarification) {
        setClarifications(data.questions);
        setResultData(null);
      } else {
        setClarifications([]);
        setResultData(data.options);
        setActiveFloor(0);
      }
    } catch (error) {
      console.error("Connection link broke down:", error);
      setErrorMessage("Could not connect to the backend architectural generator engine.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnswerChange = (fieldKey: string, value: string) => {
    setAnswers(prev => ({ ...prev, [fieldKey]: value }));
  };

  return {
    prompt, setPrompt,
    activeOption, setActiveOption, 
    activeFloor, setActiveFloor, 
    loading, resultData, clarifications, answers, errorMessage,
    handleSynthesize, handleAnswerChange
  };
};