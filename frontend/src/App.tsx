import { useState } from "react";
import {
  Routes,
  Route,
  NavLink,
  Navigate,
  Outlet,
  Link,
  useLocation,
} from "react-router-dom";
import {
  Dumbbell,
  LayoutDashboard,
  Users,
  IdCard,
  ScanLine,
  CalendarDays,
  HeartPulse,
  Receipt,
  Package,
  BarChart3,
  Settings,
  ShieldCheck,
  Bell,
  LogOut,
  Menu,
  X,
  ArrowUpRight,
} from "lucide-react";
import { useAuth } from "./auth";
import { Loading, ErrorBox } from "./components/ui";
import Login, { Activate } from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Members from "./pages/Members";
import Memberships from "./pages/Memberships";
import AttendancePage from "./pages/Attendance";
import Billing from "./pages/Billing";
import { ResourceModule } from "./pages/Resources";
import { SettingsPage, Notifications, Audit } from "./pages/Settings";
import Portal from "./pages/Portal";
import Account from "./pages/Account";
const nav = [
  ["/", "Overview", LayoutDashboard, "reports.read"],
  ["/members", "Members", Users, "members.read"],
  ["/memberships", "Memberships", IdCard, "memberships.read"],
  ["/attendance", "Attendance", ScanLine, "attendance.read"],
  ["/training", "Trainers & sessions", CalendarDays, "training.read"],
  ["/workouts", "Workout studio", HeartPulse, "training.read"],
  ["/billing", "Billing & payments", Receipt, "finance.read"],
  ["/inventory", "Inventory & equipment", Package, "inventory.read"],
  ["/reports", "Analytics & reports", BarChart3, "reports.read"],
  ["/settings", "Team & settings", Settings, "org.manage"],
  ["/audit", "Audit trail", ShieldCheck, "audit.read"],
] as const;
function Shell() {
  const { info, can, logout } = useAuth();
  const [open, setOpen] = useState(false),
    [error, setError] = useState<unknown>(null);
  const location = useLocation();
  const current =
    nav.find((n) => n[0] === location.pathname)?.[1] || "Your workspace";
  return (
    <div className="shell">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <Link to="/" className="brand">
          <span className="brand-icon">
            <Dumbbell />
          </span>
          <span>
            GymOS<small>ENTERPRISE</small>
          </span>
        </Link>
        <div className="workspace">
          <div className="workspace-avatar">
            {info?.organization.name.slice(0, 1)}
          </div>
          <div>
            <strong>{info?.organization.name}</strong>
            <small>Club workspace</small>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {nav
            .filter((n) => can(n[3]))
            .map(([url, label, Icon]) => (
              <NavLink
                end={url === "/"}
                to={url}
                key={url}
                onClick={() => setOpen(false)}
              >
                <Icon size={19} />
                {label}
              </NavLink>
            ))}
          {can("self.read") && (
            <NavLink to="/portal">
              <Users size={19} />
              My fitness portal
            </NavLink>
          )}
          <NavLink to="/account" onClick={() => setOpen(false)}>
            <ShieldCheck size={19} />
            Account security
          </NavLink>
          <NavLink to="/notifications" onClick={() => setOpen(false)}>
            <Bell size={19} />
            Notifications
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <div className="connection-dot" /> Connected to your gym
          <p>Real records. Clear decisions.</p>
        </div>
      </aside>
      {open && (
        <button
          className="sidebar-scrim"
          aria-label="Close menu"
          onClick={() => setOpen(false)}
        />
      )}
      <div className="main">
        <header>
          <button
            className="icon mobile-menu"
            onClick={() => setOpen(!open)}
            aria-label="Toggle navigation"
          >
            {open ? <X /> : <Menu />}
          </button>
          <div className="breadcrumb">
            Workspace <span>/</span> <strong>{current}</strong>
          </div>
          <div className="header-right">
            <span className="role-tag">{info?.user.role}</span>
            <Link
              className="icon"
              to="/notifications"
              aria-label="Notifications"
            >
              <Bell size={19} />
            </Link>
            <div className="avatar">
              {info?.user.name
                .split(" ")
                .map((n) => n[0])
                .slice(0, 2)
                .join("")}
            </div>
            <div className="header-user">
              <strong>{info?.user.name}</strong>
              <small>{info?.organization.slug}</small>
            </div>
            <button
              className="icon"
              onClick={() => logout().catch(setError)}
              aria-label="Sign out"
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <main>
          {error != null && <ErrorBox error={error} />}
          <Outlet />
        </main>
        <footer>
          GymOS Enterprise <span>Member care, in motion.</span>
        </footer>
      </div>
    </div>
  );
}
function Gate({
  permission,
  children,
}: {
  permission: string;
  children: React.ReactNode;
}) {
  const { can } = useAuth();
  return can(permission) ? (
    children
  ) : (
    <div className="card">
      <h2>Access restricted</h2>
      <p>Your role does not have access to this area.</p>
    </div>
  );
}
function Home() {
  const { can } = useAuth();
  if (can("reports.read")) return <Dashboard />;
  if (can("self.read")) return <Navigate to="/portal" replace />;
  if (can("attendance.read"))
    return (
      <div>
        <div className="page-head">
          <div>
            <div className="eyebrow">TODAY’S WORKSPACE</div>
            <h1>Let’s make it a good session.</h1>
            <p>Your daily member and training operations.</p>
          </div>
        </div>
        <div className="quick-grid">
          {[
            ["/members", "Member directory"],
            ["/attendance", "Check-in desk"],
            ["/training", "Training schedule"],
          ].map(([to, label]) => (
            <Link className="card quick" to={to} key={to}>
              <h2>{label}</h2>
              <ArrowUpRight />
            </Link>
          ))}
        </div>
      </div>
    );
  return <Navigate to="/notifications" replace />;
}
export default function App() {
  const { info, loading } = useAuth();
  if (loading)
    return (
      <div className="activation">
        <Loading />
      </div>
    );
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/activate" element={<Activate />} />
      <Route element={info ? <Shell /> : <Navigate to="/login" replace />}>
        <Route index element={<Home />} />
        <Route
          path="members"
          element={
            <Gate permission="members.read">
              <Members />
            </Gate>
          }
        />
        <Route
          path="memberships"
          element={
            <Gate permission="memberships.read">
              <Memberships />
            </Gate>
          }
        />
        <Route
          path="attendance"
          element={
            <Gate permission="attendance.read">
              <AttendancePage />
            </Gate>
          }
        />
        <Route
          path="training"
          element={
            <Gate permission="training.read">
              <ResourceModule group="training" />
            </Gate>
          }
        />
        <Route
          path="workouts"
          element={
            <Gate permission="training.read">
              <ResourceModule group="workouts" />
            </Gate>
          }
        />
        <Route
          path="billing"
          element={
            <Gate permission="finance.read">
              <Billing />
            </Gate>
          }
        />
        <Route
          path="inventory"
          element={
            <Gate permission="inventory.read">
              <ResourceModule group="inventory" />
            </Gate>
          }
        />
        <Route
          path="reports"
          element={
            <Gate permission="reports.read">
              <Dashboard reports />
            </Gate>
          }
        />
        <Route
          path="settings"
          element={
            <Gate permission="org.manage">
              <SettingsPage />
            </Gate>
          }
        />
        <Route
          path="audit"
          element={
            <Gate permission="audit.read">
              <Audit />
            </Gate>
          }
        />
        <Route path="account" element={<Account />} />
        <Route path="notifications" element={<Notifications />} />
        <Route
          path="portal"
          element={
            <Gate permission="self.read">
              <Portal />
            </Gate>
          }
        />
        <Route
          path="*"
          element={
            <div className="card">
              <h1>Page not found</h1>
              <Link to="/">Back to workspace</Link>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}
