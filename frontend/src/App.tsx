import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from './components/layout/AppLayout';
import { ConnectionProvider } from './contexts/ConnectionContext';
import { FloatingConnectionStatus } from './components/ConnectionStatus';
import { Dashboard } from './pages/Dashboard';
import { AgentControl } from './pages/AgentControl';
import { Analytics } from './pages/Analytics';
import { Optimization } from './pages/Optimization';
import { Models } from './pages/Models';
import { queryClient } from './api/queryClient';
import { SelfCheck } from './pages/SelfCheck';



function AppContent() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="agent" element={<AgentControl />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="optimization" element={<Optimization />} />
          <Route path="models" element={<Models />} />
          <Route path="self-check" element={<SelfCheck />} />
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
