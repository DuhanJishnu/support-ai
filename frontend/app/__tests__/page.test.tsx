import { render, screen } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import Home from '../page';

// Mock next/image since it is optimized for server-side environments
vi.mock('next/image', () => ({
  default: ({ src, alt, width, height, priority, ...props }: { src: string; alt: string; width?: number; height?: number; priority?: boolean; [key: string]: unknown }) => {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt} width={width} height={height} {...props} />;
  },
}));

test('renders Next.js homepage text', () => {
  render(<Home />);
  const heading = screen.getByText(/To get started/i);
  expect(heading).toBeInTheDocument();
});
