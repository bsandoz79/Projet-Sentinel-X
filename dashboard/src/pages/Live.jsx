import { useEffect, useState } from 'react'
import { api } from '../api'
import { NOMS_ALERTES, SEUILS, fmtHeure, fmtDate } from '../utils.js'
import BandeauEtat from '../components/BandeauEtat.jsx'
import CarteCapteur from '../components/CarteCapteur.jsx'

const MAX_POINTS = 120 // 2 minutes d'historique dans les mini-courbes

export default function Live({ ouvrirIncident }) {
  const [mesure, setMesure] = useState(null)
  const [historique, setHistorique] = useState([])
  const [incidents, setIncidents] = useState([])
  const [erreur, setErreur] = useState(null)
  const [simu, setSimu] = useState(null)

  useEffect(() => {
    let actif = true
    const tick = async () => {
      try {
        const m = await api.getLive()
        if (!actif) return
        setMesure(m)
        setHistorique((h) => [...h.slice(-(MAX_POINTS - 1)), m])
        setErreur(null)
        if (api.simulationEnCours) setSimu(api.simulationEnCours())
      } catch (e) {
        setErreur(e.message)
      }
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => { actif = false; clearInterval(id) }
  }, [])

  useEffect(() => {
    const charger = () => api.getIncidents().then(setIncidents).catch(() => {})
    charger()
    const id = setInterval(charger, 5000)
    return () => clearInterval(id)
  }, [])

  if (erreur) return <div className="erreur">Impossible de joindre l'API du Pi : {erreur}</div>
  if (!mesure) return <div className="chargement">Connexion aux capteurs…</div>

  const a = mesure.alertes || []
  const dhtErr = mesure.temp == null

  return (
    <div className="page-live">
      <BandeauEtat etat={dhtErr ? 'dht' : mesure.etat} alertes={a} />
      <div className="maj">Dernière mesure : {fmtHeure(mesure.ts)}</div>

      <div className="grille-cartes">
        <CarteCapteur titre="Température" valeur={mesure.temp} unite="°C" cle="temp" couleur="#f97316"
          historique={historique} alerte={a.includes('temperature')} sous={`seuil ${SEUILS.temp} °C`} />
        <CarteCapteur titre="Humidité" valeur={mesure.hum} unite="%" cle="hum" couleur="#38bdf8"
          historique={historique} alerte={a.includes('humidite')} sous={`seuil ${SEUILS.hum} %`} />
        <CarteCapteur titre="Distance" valeur={mesure.dist > 0 ? mesure.dist : null} unite="cm" cle="dist" couleur="#a3e635"
          historique={historique} alerte={a.includes('intrusion')} sous={`alerte < ${SEUILS.distAlerte} cm`} />
        <CarteCapteur titre="Gaz" valeur={mesure.gaz} cle="gaz" couleur="#eab308"
          historique={historique} alerte={a.includes('gaz')} sous={`référence ${mesure.ref_gaz} · alerte > +${SEUILS.ecartGaz}`} />
        <CarteCapteur titre="Son" valeur={mesure.son} cle="son" couleur="#e879f9"
          historique={historique} alerte={a.includes('bruit')} sous={`alerte > ${SEUILS.son}`} />
        <CarteCapteur titre="Mouvement" valeur={mesure.pir ? 'OUI' : 'non'} alerte={a.includes('presence')}
          sous={mesure.pir ? 'quelqu’un bouge' : 'rien détecté'} />
      </div>

      {api.simuler && (
        <div className="panneau demo">
          <div className="panneau-titre">Démo : simuler un incident</div>
          <div className="boutons">
            {[['intrusion', 'Intrusion'], ['gaz', 'Fuite de gaz'], ['chaleur', 'Départ de feu']].map(([k, l]) => (
              <button key={k} disabled={!!simu} onClick={() => { api.simuler(k); setSimu(k) }}>{l}</button>
            ))}
          </div>
          {simu && <div className="note">Simulation « {simu} » en cours… elle apparaîtra dans la Timeline à la fin (≈ 70 s).</div>}
        </div>
      )}

      <div className="panneau">
        <div className="panneau-titre">Derniers incidents</div>
        {incidents.length === 0 && <div className="note">Aucun incident enregistré.</div>}
        {incidents.slice(0, 5).map((i) => (
          <button key={i.id} className="ligne-incident" onClick={() => ouvrirIncident(i.id)}>
            <span className="pastille rouge" />
            <span className="li-date">{fmtDate(i.debut)}</span>
            <span className="li-titre">{i.titre}</span>
            <span className="li-alertes">{i.alertes.map((x) => NOMS_ALERTES[x] || x).join(', ')}</span>
            <span className="li-go">Rejouer ▶</span>
          </button>
        ))}
      </div>
    </div>
  )
}
