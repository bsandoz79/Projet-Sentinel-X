import { useEffect, useState } from 'react'
import { api } from './api'
import Live from './pages/Live.jsx'
import Timeline from './pages/Timeline.jsx'
import Journal from './pages/Journal.jsx'
import BadgeIntegrite from './components/BadgeIntegrite.jsx'

const ONGLETS = [
  { id: 'live', label: 'Live' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'journal', label: 'Journal' },
]

export default function App() {
  const [onglet, setOnglet] = useState('live')
  const [incidentChoisi, setIncidentChoisi] = useState(null)
  const [integrite, setIntegrite] = useState(null)

  // Vérifie le journal toutes les 5 s (badge en haut à droite)
  useEffect(() => {
    const verif = () => api.verifierIntegrite().then(setIntegrite).catch(() => setIntegrite(null))
    verif()
    const id = setInterval(verif, 5000)
    return () => clearInterval(id)
  }, [])

  const ouvrirIncident = (id) => { setIncidentChoisi(id); setOnglet('timeline') }

  return (
    <div className="app">
      <header className="entete">
        <div className="logo">
          <span className="logo-point" /> SENTINEL-X
          <span className="mode">{api.mode === 'demo' ? 'Démo · données simulées' : 'Connecté au Pi'}</span>
        </div>
        <nav className="onglets">
          {ONGLETS.map((o) => (
            <button key={o.id} className={onglet === o.id ? 'actif' : ''} onClick={() => setOnglet(o.id)}>
              {o.label}
            </button>
          ))}
        </nav>
        <BadgeIntegrite integrite={integrite} onClick={() => setOnglet('journal')} />
      </header>

      <main>
        {onglet === 'live' && <Live ouvrirIncident={ouvrirIncident} />}
        {onglet === 'timeline' && <Timeline incidentInitial={incidentChoisi} />}
        {onglet === 'journal' && <Journal integrite={integrite} setIntegrite={setIntegrite} />}
      </main>
    </div>
  )
}
