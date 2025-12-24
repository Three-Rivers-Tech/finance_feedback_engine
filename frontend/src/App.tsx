import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { Dashboard } from './pages/Dashboard';
import { AgentControl } from './pages/AgentControl';
import { Analytics } from './pages/Analytics';
import { Optimization } from './pages/Optimization';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="agent" element={<AgentControl />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="optimization" element={<Optimization />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
