import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export const AppLayout: React.FC = () => {
  return (
    <div className="h-full flex flex-col">
      <Header />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto scrollbar-thin bg-bg-primary">
          <div className="p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
