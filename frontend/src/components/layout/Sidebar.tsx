import React from 'react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Dashboard', icon: '▣' },
  { path: '/agent', label: 'Agent Control', icon: '⚙' },
  { path: '/positions', label: 'Positions/Trades', icon: '📈' },
  { path: '/self-check', label: 'Health/SelfCheck', icon: '✓' },
  { path: '/settings', label: 'Settings', icon: '🔐' },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-bg-secondary border-r-3 border-border-primary">
      <nav className="p-4">
        <ul className="space-y-2">
          {navItems.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  `block px-4 py-3 font-mono text-sm border-3 transition-colors ${
                    isActive
                      ? 'bg-accent-cyan text-bg-primary border-accent-cyan'
                      : 'border-border-primary text-text-primary hover:border-accent-cyan hover:text-accent-cyan'
                  }`
                }
              >
                <span className="mr-2">{item.icon}</span>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  );
};
