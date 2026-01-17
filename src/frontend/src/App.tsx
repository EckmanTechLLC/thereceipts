import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { Layout } from './components/Layout';
import { AskPage } from './pages/AskPage';
import { ReadPage } from './pages/ReadPage';
import { AuditsPage } from './pages/AuditsPage';

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/ask" replace />} />
            <Route path="ask" element={<AskPage />} />
            <Route path="read" element={<ReadPage />} />
            <Route path="audits" element={<AuditsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
