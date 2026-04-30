import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('renders the incident dashboard shell', () => {
    render(<App />);
    expect(screen.getByText(/Mission-Critical IMS/i)).toBeInTheDocument();
    expect(screen.getByText(/Live Feed/i)).toBeInTheDocument();
    expect(screen.getByText(/RCA Form/i)).toBeInTheDocument();
  });
});
