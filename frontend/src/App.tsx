import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from './components/layout/AppLayout';
import { ConnectionProvider } from './contexts/ConnectionContext';
import { FloatingConnectionStatus } from './components/ConnectionStatus';
import { Dashboard } from './pages/Dashboard';
import { AgentControl } from './pages/AgentControl';
import { queryClient } from './api/queryClient';
import { SelfCheck } from './pages/SelfCheck';
import { PositionsTrades } from './pages/PositionsTrades';
import { Settings } from './pages/Settings';

function AppContent() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="agent" element={<AgentControl />} />
          <Route path="positions" element={<PositionsTrades />} />
          <Route path="self-check" element={<SelfCheck />} />
          <Route path="settings" element={<Settings />} />

          {/* Legacy routes archived for v1 focus */}
          <Route path="analytics" element={<Navigate to="/" replace />} />
          <Route path="optimization" element={<Navigate to="/" replace />} />
          <Route path="models" element={<Navigate to="/settings" replace />} />
        </Route>
      </Routes>
      <FloatingConnectionStatus />
    </BrowserRouter>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConnectionProvider>
        <AppContent />
      </ConnectionProvider>
    </QueryClientProvider>
  );
}

export default App;
