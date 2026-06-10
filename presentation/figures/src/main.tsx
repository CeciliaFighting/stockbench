import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { Page05 } from './pages/Page05';
import { Page06 } from './pages/Page06';
import { Page07 } from './pages/Page07';
import { Page08 } from './pages/Page08';
import { Page09 } from './pages/Page09';
import { Page10 } from './pages/Page10';
import { Page11 } from './pages/Page11';
import { Page12 } from './pages/Page12';
import { Page13 } from './pages/Page13';
import { Page14 } from './pages/Page14';
import { Page15 } from './pages/Page15';

const page = new URLSearchParams(window.location.search).get('page') || '06';

function App() {
  if (page === '05') return <Page05 />;
  if (page === '07') return <Page07 />;
  if (page === '08') return <Page08 />;
  if (page === '09') return <Page09 />;
  if (page === '10') return <Page10 />;
  if (page === '11') return <Page11 />;
  if (page === '12') return <Page12 />;
  if (page === '13') return <Page13 />;
  if (page === '14') return <Page14 />;
  if (page === '15') return <Page15 />;
  return <Page06 />;
}

createRoot(document.getElementById('root')!).render(<App />);
