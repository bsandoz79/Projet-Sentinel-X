import { useEffect, useState } from 'react'
import { api } from '../api'
import { ETATS, NOMS_ALERTES, court, fmtDate } from '../utils.js'

export default function Journal({ integrite, setIntegrite }) {
  const [evts, setEvts] = useState([])
  const [verif, setVerif] = useState(false)

  const charger = () => api.getEvenements().then(setEvts)
  useEffect(() => { charger() }, [])

  const verifier = async () => {
    setVerif(true)
    await charger()
    setIntegrite(await api.verifierIntegrite())
    setTimeout(() => setVerif(false), 400)
  }

  const casse = integrite && !integrite.ok ? integrite.premier_invalide : null

  return (
    <div className="page-journal">
      <div className={'integrite ' + (integrite?.ok ? 'ok' : integrite ? 'ko' : '')}>
        <div className="integrite-icone">{integrite?.ok ? '✔' : integrite ? '✘' : '…'}</div>
        <div>
          <div className="integrite-titre">
            {integrite?.ok ? 'Journal intègre' : integrite ? 'Journal FALSIFIÉ' : 'Vérification…'}
          </div>
          <div className="note">
            {integrite?.ok && `${integrite.total} événements, chaque hash correspond au précédent.`}
            {integrite && !integrite.ok && `La chaîne est cassée à l'événement n° ${casse + 1} : il a été modifié après coup.`}
          </div>
        </div>
        <div className="boutons">
          <button onClick={verifier} disabled={verif}>{verif ? 'Vérification…' : 'Vérifier maintenant'}</button>
          {api.falsifier && (
            <>
              <button className="danger" onClick={() => { api.falsifier(); verifier() }}>Falsifier un événement (démo)</button>
              <button onClick={() => { api.restaurer(); verifier() }}>Restaurer</button>
            </>
          )}
        </div>
      </div>

      <div className="panneau explication">
        <b>Comment ça marche :</b> chaque événement contient le hash SHA-256 de l'événement précédent (« prev »).
        Si quelqu'un modifie un événement passé, son hash ne correspond plus et toute la suite de la chaîne devient invalide.
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>#</th><th>Date</th><th>Type</th><th>Détail</th><th>prev</th><th>hash</th></tr>
          </thead>
          <tbody>
            {[...evts].reverse().map((e) => {
              const i = e.id - 1
              const invalide = casse != null && i >= casse
              return (
                <tr key={e.id} className={invalide ? (i === casse ? 'casse' : 'invalide') : ''}>
                  <td>{e.id}</td>
                  <td>{fmtDate(e.ts)}</td>
                  <td><span className="pastille" style={{ background: ETATS[e.type]?.color || '#64748b' }} /> {ETATS[e.type]?.label || e.type}</td>
                  <td>
                    {(e.details.alertes || []).map((a) => NOMS_ALERTES[a] || a).join(', ')}
                    {e.details.gaz != null && <span className="note"> gaz {e.details.gaz}</span>}
                    {i === casse && <span className="tag rouge">modifié ici</span>}
                  </td>
                  <td><code>{court(e.prev)}</code></td>
                  <td><code>{court(e.hash)}</code></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
