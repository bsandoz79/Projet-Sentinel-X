import { ETATS, NOMS_ALERTES } from '../utils.js'

export default function BandeauEtat({ etat, alertes = [], petit }) {
  const e = ETATS[etat] || { label: '…', color: '#64748b' }
  return (
    <div className={'bandeau' + (petit ? ' petit' : '') + (etat === 'alerte' ? ' pulse' : '')} style={{ background: e.color }}>
      <div className="bandeau-label">{e.label}</div>
      {alertes.length > 0 && (
        <div className="bandeau-alertes">{alertes.map((a) => NOMS_ALERTES[a] || a).join(' · ')}</div>
      )}
    </div>
  )
}
