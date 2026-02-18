import { useEffect, useState, useCallback, useRef } from 'react';

export function usePolling<T>(
  fetcher: () => Promise<T>,
  interval: number,
  enabled: boolean = true
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [hasFetched, setHasFetched] = useState(false);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const refetch = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err as Error);
    } finally {
      setHasFetched(true);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    void refetch();
    const intervalId = setInterval(() => {
      void refetch();
    }, interval);

    return () => clearInterval(intervalId);
  }, [interval, enabled, refetch]);

  const isLoading = enabled && !hasFetched;

  return { data, error, isLoading, refetch };
}
