import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { Page05 } from './pages/Page05';
import { Page06 } from './pages/Page06';
import { Page07 } from './pages/Page07';
import { Page14 } from './pages/Page14';

const page = new URLSearchParams(window.location.search).get('page') || '06';

function App() {
  if (page === '05') return <Page05 />;
  if (page === '07') return <Page07 />;
  if (page === '14') return <Page14 />;
  return <Page06 />;
}

createRoot(document.getElementById('root')!).render(<App />);
