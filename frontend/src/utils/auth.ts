const API_KEY_STORAGE_KEY = 'api_key';

const PLACEHOLDER_PATTERNS = [
  /^your[_-]?api[_-]?key/i,
  /^api[_-]?key/i,
  /^changeme/i,
  /^example/i,
  /^test$/i,
  /^demo/i,
  /^placeholder/i,
];

export function isPlaceholderApiKey(key: string | null | undefined): boolean {
  if (!key) return true;
  const trimmed = key.trim();
  if (!trimmed) return true;
  return PLACEHOLDER_PATTERNS.some((pattern) => pattern.test(trimmed));
}

export function getStoredApiKey(): string | null {
  const key = localStorage.getItem(API_KEY_STORAGE_KEY);
  if (!key || isPlaceholderApiKey(key)) {
    return null;
  }
  return key;
}

export function getEnvApiKey(): string | null {
  const key = import.meta.env.VITE_API_KEY as string | undefined;
  if (!key || isPlaceholderApiKey(key)) {
    return null;
  }
  return key;
}

export function getEffectiveApiKey(): string | null {
  return getStoredApiKey() ?? getEnvApiKey();
}

export function hasUsableApiKey(): boolean {
  return Boolean(getEffectiveApiKey());
}

export function setStoredApiKey(value: string): void {
  const trimmed = value.trim();
  if (!trimmed || isPlaceholderApiKey(trimmed)) {
    throw new Error('Please enter a real API key (not a placeholder).');
  }
  localStorage.setItem(API_KEY_STORAGE_KEY, trimmed);
}

export function clearStoredApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE_KEY);
}

export { API_KEY_STORAGE_KEY };
