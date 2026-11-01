"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { Home, Users, Package, BarChart3 } from "lucide-react";

const tabs = [
  { href: "/", label: "होम", labelEn: "Home", icon: Home },
  { href: "/customers", label: "ग्राहक", labelEn: "Customers", icon: Users },
  { href: "/inventory", label: "सामान", labelEn: "Inventory", icon: Package },
  { href: "/reports", label: "रिपोर्ट", labelEn: "Reports", icon: BarChart3 },
];

export default function Navigation() {
  const pathname = usePathname();

  // Hide nav on onboarding
  if (pathname === "/onboarding") return null;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200 shadow-[0_-2px_10px_rgba(0,0,0,0.06)]">
      <div className="flex items-center justify-around h-[60px] max-w-lg mx-auto">
        {tabs.map((tab) => {
          const isActive =
            tab.href === "/"
              ? pathname === "/"
              : pathname.startsWith(tab.href);
          const Icon = tab.icon;

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex flex-col items-center justify-center gap-0.5 min-w-[64px] min-h-[44px] px-2 py-1 rounded-xl transition-colors ${
                isActive
                  ? "text-orange-500"
                  : "text-gray-400 active:text-gray-600"
              }`}
            >
              <Icon
                size={22}
                strokeWidth={isActive ? 2.5 : 2}
                className="shrink-0"
              />
              <span
                className={`text-[11px] leading-tight ${
                  isActive ? "font-semibold" : "font-medium"
                }`}
              >
                {tab.label}
              </span>
            </Link>
          );
        })}
      </div>
      {/* Safe area spacer for iOS */}
      <div className="h-[env(safe-area-inset-bottom)]" />
    </nav>
  );
}
