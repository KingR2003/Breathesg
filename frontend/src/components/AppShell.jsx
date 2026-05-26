import React from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, FileText, Upload, Database,
  LogOut, Leaf
} from 'lucide-react'
import useAuthStore from '../store/useAuthStore'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/records', icon: FileText, label: 'Records' },
  { to: '/upload', icon: Upload, label: 'Upload Data' },
  { to: '/batches', icon: Database, label: 'Ingestion Batches' },
]

export default function AppShell() {
  const { user, logout } = useAuthStore()

  const initials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.username?.slice(0, 2).toUpperCase() || 'U'

  return (
    <div className="app-shell">
      {/* Topbar */}
      <header className="topbar">
        <a href="/dashboard" className="topbar-brand">
          <div className="topbar-brand-icon">
            <Leaf size={18} color="white" />
          </div>
          <span className="topbar-brand-name">
            Breathe<span>ESG</span>
          </span>
        </a>
        <div className="topbar-right">
          <div className="topbar-user" onClick={logout} title="Click to log out">
            <div className="topbar-avatar">{initials}</div>
            <span>{user?.full_name || user?.username || 'Analyst'}</span>
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={logout}
            id="logout-btn"
            title="Log out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </header>

      {/* Sidebar */}
      <nav className="sidebar">
        <div className="sidebar-section">
          <div className="sidebar-label">Navigation</div>
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              id={`nav-${label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <Icon className="nav-item-icon" size={18} />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main content */}
      <main className="main-content fade-in">
        <Outlet />
      </main>
    </div>
  )
}
