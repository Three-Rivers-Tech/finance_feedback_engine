import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OllamaStatusAlert } from '../OllamaStatusAlert';
import type { OllamaComponent } from '../../../api/types';

describe('OllamaStatusAlert', () => {
  it('should not render when Ollama is healthy', () => {
    const ollama: OllamaComponent = {
      status: 'healthy',
      available: true,
      models_loaded: ['mistral', 'neural-chat', 'orca-mini'],
      models_missing: [],
      host: 'http://localhost:11434',
    };

    const { container } = render(<OllamaStatusAlert ollama={ollama} />);
    expect(container.firstChild).toBeNull();
  });

  it('should show error when Ollama is unavailable', () => {
    const ollama: OllamaComponent = {
      status: 'unavailable',
      available: false,
      models_loaded: [],
      models_missing: ['mistral', 'neural-chat', 'orca-mini'],
      host: 'http://localhost:11434',
      error: 'Cannot connect to Ollama',
    };

    render(<OllamaStatusAlert ollama={ollama} />);

    expect(screen.getByText('Ollama Not Available')).toBeInTheDocument();
    expect(screen.getByText('Cannot connect to Ollama')).toBeInTheDocument();
    expect(screen.getByText('Run ./scripts/setup-ollama.sh to install')).toBeInTheDocument();
  });

  it('should show warning when models are missing', () => {
    const ollama: OllamaComponent = {
      status: 'degraded',
      available: true,
      models_loaded: ['mistral'],
      models_missing: ['neural-chat', 'orca-mini'],
      host: 'http://localhost:11434',
      warning: 'Some models not installed',
    };

    render(<OllamaStatusAlert ollama={ollama} />);

    expect(screen.getByText('Missing Required Models')).toBeInTheDocument();
    expect(screen.getByText(/Models not installed: neural-chat, orca-mini/)).toBeInTheDocument();
    expect(screen.getByText('Run ./scripts/pull-ollama-models.sh to download')).toBeInTheDocument();
    expect(screen.getByText(/Models loaded: mistral/)).toBeInTheDocument();
  });

  it('should display warning message when provided', () => {
    const ollama: OllamaComponent = {
      status: 'degraded',
      available: true,
      models_loaded: [],
      models_missing: ['mistral'],
      host: 'http://localhost:11434',
      warning: 'Custom warning message',
    };

    render(<OllamaStatusAlert ollama={ollama} />);
    expect(screen.getByText('Custom warning message')).toBeInTheDocument();
  });
});
