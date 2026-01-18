import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { Layout } from './components/Layout';
import { HomePage } from './pages/HomePage';
import { AskPage } from './pages/AskPage';
import { ReadPage } from './pages/ReadPage';
import { AuditsPage } from './pages/AuditsPage';
import { SourcesPage } from './pages/SourcesPage';
import { GraphPage } from './pages/GraphPage';

function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="ask" element={<AskPage />} />
            <Route path="read" element={<ReadPage />} />
            <Route path="audits" element={<AuditsPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="graph" element={<GraphPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
