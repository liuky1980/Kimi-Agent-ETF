import { useState, useCallback } from 'react';
import type { Tab } from '@/components/Navbar';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import Home from '@/pages/Home';
import ChanlunAnalysis from '@/pages/ChanlunAnalysis';
import DingChangAnalysis from '@/pages/DingChangAnalysis';
import Overview from '@/pages/Overview';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('home');
  const [selectedETF, setSelectedETF] = useState<string | undefined>(undefined);

  const handleTabChange = useCallback((tab: Tab) => {
    setActiveTab(tab);
    // 切换Tab时不重置selectedETF，保持全局选中标的
  }, []);

  const handleNavigate = useCallback((tab: Tab, etfCode?: string) => {
    setActiveTab(tab);
    if (etfCode) {
      setSelectedETF(etfCode);
    }
  }, []);

  return (
    <div className="min-h-[100dvh] flex flex-col bg-slate-950 text-slate-100">
      <Navbar activeTab={activeTab} onTabChange={handleTabChange} />
      
      <main className="flex-1 pt-20 pb-8">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {activeTab === 'home' && <Home onNavigate={handleNavigate} />}
          {activeTab === 'overview' && <Overview initialCode={selectedETF} />}
          {activeTab === 'chanlun' && <ChanlunAnalysis initialCode={selectedETF} />}
          {activeTab === 'dingchang' && <DingChangAnalysis initialCode={selectedETF} />}
        </div>
      </main>

      <Footer />
    </div>
  );
}
