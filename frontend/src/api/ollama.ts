export interface OllamaModelTag {
  name: string;
  modified?: string;
  size?: number;
}

export interface OllamaTagsResponse {
  models?: OllamaModelTag[];
  tags?: { name: string }[];
}

export interface OllamaModelDetails {
  [key: string]: unknown;
}

export async function listOllamaModels(): Promise<OllamaModelTag[]> {
  const res = await fetch('/ollama/api/tags');
  if (!res.ok) throw new Error(`Ollama tags failed: ${res.status}`);
  const data: OllamaTagsResponse = await res.json();
  if (data.models && Array.isArray(data.models)) return data.models;
  if (data.tags && Array.isArray(data.tags)) return data.tags.map((t) => ({ name: t.name }));
  return [];
}

export type PullProgress = {
  status?: string;
  digest?: string;
  total?: number;
  completed?: number;
  error?: string;
};

export async function pullOllamaModel(
  name: string,
  onProgress?: (progress: PullProgress) => void
): Promise<void> {
  const res = await fetch('/ollama/api/pull', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });

  if (!res.ok || !res.body) {
    throw new Error(`Ollama pull failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      try {
        const evt: PullProgress = JSON.parse(trimmed);
        onProgress?.(evt);
        if (evt.error) throw new Error(evt.error);
      } catch (error) {
        if (error instanceof Error && error.message) {
          throw error;
        }
      }
    }
  }

  const last = buffer.trim();
  if (last) {
    try {
      onProgress?.(JSON.parse(last) as PullProgress);
    } catch (error) {
      void error;
    }
  }
}

export async function showOllamaModel(name: string): Promise<OllamaModelDetails> {
  const res = await fetch(`/ollama/api/show?name=${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error(`Ollama show failed: ${res.status}`);
  return (await res.json()) as OllamaModelDetails;
}

export async function deleteOllamaModel(name: string): Promise<void> {
  const res = await fetch('/ollama/api/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`Ollama delete failed: ${res.status}`);
}
