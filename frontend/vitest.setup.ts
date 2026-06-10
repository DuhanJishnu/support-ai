import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
import { loadEnvConfig } from '@next/env';

// Load environment variables from Next.js env files into process.env
loadEnvConfig(process.cwd());

// Clean up DOM and reset mocks after each test
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
