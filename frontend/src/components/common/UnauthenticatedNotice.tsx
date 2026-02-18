import React from 'react';
import { Link } from 'react-router-dom';
import { hasUsableApiKey } from '../../utils/auth';

export const UnauthenticatedNotice: React.FC = () => {
  if (hasUsableApiKey()) {
    return null;
  }

  return (
    <div className="mb-4 border-3 border-accent-yellow bg-accent-yellow/10 rounded p-3">
      <p className="text-xs font-mono text-text-primary">
        API key not configured. Some endpoints may return 401 until you add a valid key.
      </p>
      <Link to="/settings" className="text-xs font-mono text-accent-cyan underline">
        Open Settings
      </Link>
    </div>
  );
};
