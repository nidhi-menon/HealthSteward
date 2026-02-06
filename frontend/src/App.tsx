import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import ProfileList from './pages/ProfileList';
import ProfileDetail from './pages/ProfileDetail';
import VisitPrep from './pages/VisitPrep';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<ProfileList />} />
            <Route path="/profiles/:profileId" element={<ProfileDetail />} />
            <Route path="/profiles/:profileId/appointments/:appointmentId/prep" element={<VisitPrep />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
