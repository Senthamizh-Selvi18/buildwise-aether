import { useEffect, useState } from 'react';

export const useSocketFallback = (session_id: string) => {
  const [status, setStatus] = useState('READY');

  useEffect(() => {
    if (!session_id) return;
    setStatus('SYNC_COMPLETE');
  }, [session_id]);

  return { status };
};