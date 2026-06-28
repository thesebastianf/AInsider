import { useState } from 'react';
import Layout from './components/Layout';
import BottomNav from './components/BottomNav';
import PortfoliosTab from './pages/PortfoliosTab';
import FeedTab from './pages/FeedTab';
import SettingsTab from './pages/SettingsTab';
import DeveloperTab from './pages/DeveloperTab';

const tabs = {
  portfolios: PortfoliosTab,
  feed: FeedTab,
  settings: SettingsTab,
  developer: DeveloperTab,
};

export default function App() {
  const [activeTab, setActiveTab] = useState('portfolios');
  const ActivePage = tabs[activeTab];

  return (
    <Layout 
      activeTab={activeTab} 
      bottomNav={<BottomNav activeTab={activeTab} onTabChange={setActiveTab} />}
    >
      <ActivePage />
    </Layout>
  );
}
