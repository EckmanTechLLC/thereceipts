/**
 * Navigation component for admin app.
 */

import { Link, useLocation } from 'react-router-dom';
import './Navigation.css';

export function Navigation() {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="admin-nav">
      <div className="nav-container">
        <div className="nav-brand">
          <Link to="/topics">TheReceipts Admin</Link>
        </div>
        <div className="nav-links">
          <Link
            to="/topics"
            className={isActive('/topics') ? 'active' : ''}
          >
            Topic Queue
          </Link>
          <Link
            to="/review"
            className={isActive('/review') ? 'active' : ''}
          >
            Review
          </Link>
          <Link
            to="/settings"
            className={isActive('/settings') ? 'active' : ''}
          >
            Settings
          </Link>
        </div>
      </div>
    </nav>
  );
}
