import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => {
  cleanup();
  // Tests that call vi.setSystemTime must not leak a frozen clock into the
  // next one — date-relative nudge logic is exactly what these tests cover.
  vi.useRealTimers();
});
