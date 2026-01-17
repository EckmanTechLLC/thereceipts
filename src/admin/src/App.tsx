/**
 * TheReceipts Admin Application.
 *
 * Standalone admin interface for managing topic queue, reviewing blog posts,
 * and configuring scheduler/auto-suggest settings.
 */

import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Navigation } from './components/Navigation';
import { TopicQueuePage } from './pages/TopicQueuePage';
import { ReviewPage } from './pages/ReviewPage';
import { SettingsPage } from './pages/SettingsPage';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/topics" element={<TopicQueuePage />} />
            <Route path="/review" element={<ReviewPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/" element={<Navigate to="/topics" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
