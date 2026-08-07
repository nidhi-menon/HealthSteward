import type { ReactElement, ReactNode } from 'react';
import { render as rtlRender } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

/**
 * Renders a component with the providers the app always supplies (issue #27).
 *
 * The components under test call `useQuery` and `useNavigate`, so rendering
 * them bare throws before any assertion runs. Retries are off and the cache is
 * per-render, so a failing request fails immediately and no state leaks between
 * tests.
 */
export function renderWithProviders(
  ui: ReactElement,
  { route = '/' }: { route?: string } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  return { queryClient, ...rtlRender(ui, { wrapper: Wrapper }) };
}
