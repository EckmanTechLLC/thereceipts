import { Link, useLocation } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import './TopNav.css';

export function TopNav() {
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="top-nav">
      <div className="nav-container">
        <div className="nav-brand">
          <Link to="/">TheReceipts</Link>
        </div>
        <div className="nav-links">
          <Link
            to="/"
            className={isActive('/') ? 'active' : ''}
          >
            Home
          </Link>
          <Link
            to="/ask"
            className={isActive('/ask') ? 'active' : ''}
          >
            Ask
          </Link>
          <Link
            to="/read"
            className={isActive('/read') ? 'active' : ''}
          >
            Read
          </Link>
          <Link
            to="/audits"
            className={isActive('/audits') ? 'active' : ''}
          >
            Audits
          </Link>
          <Link
            to="/sources"
            className={isActive('/sources') ? 'active' : ''}
          >
            Sources
          </Link>
          {/* Graph link hidden - feature in progress
          <Link
            to="/graph"
            className={isActive('/graph') ? 'active' : ''}
          >
            Graph
          </Link>
          */}
        </div>
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === 'light' ? '🌙' : '☀️'}
        </button>
      </div>
    </nav>
  );
}
