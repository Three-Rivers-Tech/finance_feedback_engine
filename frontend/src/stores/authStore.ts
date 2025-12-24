import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  apiKey: string | null;
  isAuthenticated: boolean;
  setApiKey: (key: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      apiKey: null,
      isAuthenticated: false,
      setApiKey: (key) => set({ apiKey: key, isAuthenticated: true }),
      clearAuth: () => set({ apiKey: null, isAuthenticated: false }),
    }),
    { name: 'auth-storage' }
  )
);
