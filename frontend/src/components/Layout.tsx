import { Link, Outlet, useLocation } from 'react-router-dom';

const navigation = [
  { name: 'Profiles', href: '/' },
  { name: 'Settings', href: '/settings' },
];

export default function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-brand-paper">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2">
                <svg width="22" height="22" viewBox="0 0 20 20" aria-hidden="true" className="flex-none">
                  <rect x="1.5" y="1.5" width="17" height="17" fill="none" stroke="#111827" strokeWidth="1.4" />
                  <line x1="4.5" y1="6.5" x2="15.5" y2="6.5" stroke="#9ca3af" strokeWidth="1.4" strokeLinecap="square" />
                  <rect x="4.5" y="9.3" width="11" height="2.4" fill="#059669" />
                  <line x1="4.5" y1="14.5" x2="11" y2="14.5" stroke="#9ca3af" strokeWidth="1.4" strokeLinecap="square" />
                </svg>
                <span className="font-semibold text-gray-900">HealthSteward</span>
              </Link>
              <nav className="flex gap-6">
                {navigation.map((item) => (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`text-sm font-medium transition-colors ${
                      location.pathname === item.href
                        ? 'text-brand-teal-bright'
                        : 'text-gray-600 hover:text-gray-900'
                    }`}
                  >
                    {item.name}
                  </Link>
                ))}
              </nav>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  );
}
