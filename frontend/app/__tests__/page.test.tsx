import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import Home from '../page';

test('renders the support dashboard shell', () => {
  render(<Home />);

  expect(
    screen.getByRole('heading', { name: /Support Console/i })
  ).toBeInTheDocument();
  expect(screen.getByText(/Active ticket TCK-1048/i)).toBeInTheDocument();
  expect(screen.getByText(/Live Context/i)).toBeInTheDocument();
  expect(
    screen.getByRole('heading', { name: /Tool Calls/i })
  ).toBeInTheDocument();
  expect(screen.getByText(/Agent Activity/i)).toBeInTheDocument();
  expect(
    screen.getByText(/Send a message to start a support session/i)
  ).toBeInTheDocument();
  expect(screen.getByText(/No tool calls yet/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Send/i })).toBeDisabled();
});
