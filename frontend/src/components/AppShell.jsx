import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import {
  Plus,
  Home as HomeIcon,
  Inbox,
  FolderKanban,
  LayoutGrid,
  Settings,
  HelpCircle,
  MessageSquare,
  Bell,
  Search,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path) => location.pathname === path || location.pathname.startsWith(path + "/");

  const navItems = [
    { label: "Home", icon: HomeIcon, to: "/app" },
    { label: "My Issues", icon: Inbox, to: "/app/my-issues" },
    { label: "Projects", icon: FolderKanban, to: "/app/projects" },
    { label: "Views", icon: LayoutGrid, to: "/app/views" },
    { label: "Settings", icon: Settings, to: "/app/settings" },
  ];

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen flex bg-white text-[var(--tf-text)]">
      {/* Sidebar */}
      <aside
        className="w-64 shrink-0 bg-[var(--tf-sidebar-bg)] text-[var(--tf-sidebar-text)] flex flex-col"
        data-testid="app-sidebar"
      >
        <div className="px-5 pt-6 pb-5 border-b border-[var(--tf-sidebar-border)]">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-md bg-[#0055ff] grid place-items-center text-white font-bold font-mono text-sm shrink-0">
              P
            </div>
            <div className="min-w-0">
              <div className="text-white font-semibold text-sm leading-tight font-heading">Project Workspace</div>
              <div className="text-[11px] text-neutral-500 font-mono tracking-wider mt-0.5 uppercase">
                High-performance Team
              </div>
            </div>
          </div>
        </div>

        <div className="px-3 pt-4">
          <Link
            to="/app/board/proj_coreplatform"
            className="tf-btn-primary w-full flex items-center justify-center gap-1.5 text-sm font-medium py-2 rounded-md"
            data-testid="sidebar-create-new-btn"
          >
            <Plus size={14} /> Create New
          </Link>
        </div>

        <nav className="px-3 mt-5 space-y-0.5 flex-1">
          {navItems.map((item) => (
            <Link
              key={item.label}
              to={item.to}
              className={`tf-sidebar-item flex items-center gap-2.5 text-sm px-3 py-2 rounded-md ${
                isActive(item.to) ? "tf-sidebar-item-active" : ""
              }`}
              data-testid={`sidebar-nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
            >
              <item.icon size={15} />
              <span>{item.label}</span>
            </Link>
          ))}
        </nav>

        <div className="px-3 pb-4 mt-2 space-y-0.5 border-t border-[var(--tf-sidebar-border)] pt-3">
          <button className="tf-sidebar-item w-full flex items-center gap-2.5 text-sm px-3 py-2 rounded-md" data-testid="sidebar-help-btn">
            <HelpCircle size={15} /> Help
          </button>
          <button className="tf-sidebar-item w-full flex items-center gap-2.5 text-sm px-3 py-2 rounded-md" data-testid="sidebar-feedback-btn">
            <MessageSquare size={15} /> Feedback
          </button>
          <button
            onClick={handleLogout}
            className="tf-sidebar-item w-full flex items-center gap-2.5 text-sm px-3 py-2 rounded-md"
            data-testid="sidebar-logout-btn"
          >
            <LogOut size={15} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col bg-[var(--tf-bg-soft)]">
        {/* Topbar */}
        <header className="h-14 border-b border-[var(--tf-border)] bg-white flex items-center px-6 gap-4">
          <div className="font-heading font-semibold tracking-tight">LinearSync</div>
          <div className="flex-1 max-w-md relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search issues..."
              className="w-full text-sm bg-[#f3f4f6] border border-transparent rounded-md pl-9 pr-3 py-1.5 outline-none focus:border-[var(--tf-primary)] focus:bg-white transition"
              data-testid="topbar-search-input"
            />
          </div>
          <div className="ml-auto flex items-center gap-3">
            <button className="text-neutral-500 hover:text-neutral-900 transition" data-testid="topbar-notifications-btn">
              <Bell size={16} />
            </button>
            <button className="text-neutral-500 hover:text-neutral-900 transition" data-testid="topbar-help-btn">
              <HelpCircle size={16} />
            </button>
            <div className="h-5 w-px bg-[var(--tf-border)]" />
            <div className="flex items-center gap-2" data-testid="topbar-user-chip">
              {user?.picture ? (
                <img src={user.picture} alt="" className="w-7 h-7 rounded-full object-cover" />
              ) : (
                <div className="w-7 h-7 rounded-full bg-neutral-200 grid place-items-center text-[10px] font-medium text-neutral-700">
                  {(user?.name || "U").slice(0, 1).toUpperCase()}
                </div>
              )}
              <span className="text-sm text-neutral-700 hidden sm:inline">{user?.name?.split(" ")[0] || "User"}</span>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
