import { Link } from 'react-router-dom';
export default function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  return <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-background-200 bg-white/95 px-6 backdrop-blur"><button className="lg:hidden" aria-label="打开导航" onClick={onMenuClick}>☰</button><Link to="/" className="text-sm font-semibold text-foreground-900">企业风险实验平台</Link><span className="rounded border border-primary-200 bg-primary-50 px-2 py-1 text-xs text-primary-700">SMEsD 匿名企业实验</span><Link to="/search" className="ml-auto text-sm text-primary-600">检索企业 →</Link></header>;
}
