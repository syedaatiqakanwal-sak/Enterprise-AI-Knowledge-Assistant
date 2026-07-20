import { useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { LogOut, MessageSquare, Sparkles, User as UserIcon } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { Avatar, AvatarFallback } from "@/components/common/Avatar";
import { cn, initials } from "@/lib/utils";

/**
 * Minimal ChatGPT-style shell for the User Portal.
 * Chat history lives inside ChatPage; this shell only frames profile chrome.
 */
export function UserLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border/60 px-3 sm:px-4">
        <Link to="/chat" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <Sparkles className="h-4 w-4" />
          </div>
          <span className="font-display text-sm font-semibold tracking-tight">
            Knowledge Assistant
          </span>
        </Link>
        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            className="flex items-center gap-2 rounded-xl px-2 py-1 hover:bg-muted"
          >
            <Avatar className="h-8 w-8">
              <AvatarFallback>{initials(user?.full_name || "U")}</AvatarFallback>
            </Avatar>
            <span className="hidden text-sm sm:inline">{user?.full_name}</span>
          </button>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute right-0 z-50 mt-2 w-48 overflow-hidden rounded-xl border border-border bg-card shadow-soft"
            >
              <Link
                to="/chat"
                className="flex items-center gap-2 px-3 py-2.5 text-sm hover:bg-muted"
                onClick={() => setMenuOpen(false)}
              >
                <MessageSquare className="h-4 w-4" />
                Chat
              </Link>
              <Link
                to="/profile"
                className="flex items-center gap-2 px-3 py-2.5 text-sm hover:bg-muted"
                onClick={() => setMenuOpen(false)}
              >
                <UserIcon className="h-4 w-4" />
                Profile
              </Link>
              <button
                type="button"
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
                onClick={() => void handleLogout()}
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </motion.div>
          )}
        </div>
      </header>
      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
    </div>
  );
}
