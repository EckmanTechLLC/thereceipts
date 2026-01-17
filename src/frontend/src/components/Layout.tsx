import { Outlet } from 'react-router-dom';
import { TopNav } from './TopNav';
import './Layout.css';

export function Layout() {
  return (
    <div className="layout">
      <TopNav />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
