import { useEffect, useMemo, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid } from 'recharts'
import { api } from '../api'
import { ETATS, NOMS_ALERTES, SEUILS, fmtDate, fmtHeure } from '../utils.js'
import BandeauEtat from '../components/BandeauEtat.jsx'

const VITESSES = [1, 2, 5, 10]
const COURBES = [
  { cle: 'temp', titre: 'Température (°C)', couleur: '#f97316', seuil: SEUILS.temp, domaine: [(m) => Math.floor(Math.min(m, 20)), (M) => Math.ceil(Math.max(M, SEUILS.temp + 2))] },
  { cle: 'dist', titre: 'Distance (cm)', couleur: '#a3e635', seuil: SEUILS.distAlerte, domaine: [0, 200] },
  { cle: 'gaz', titre: 'Gaz', couleur: '#eab308', seuilRef: true, domaine: [(m) => Math.floor(m / 50) * 50 - 50, (M) => Math.max(Math.ceil(M / 50) * 50 + 50, 500)] },
  { cle: 'son', titre: 'Son', couleur: '#e879f9', seuil: SEUILS.son, domaine: [0, 1023] },
]

export default function Timeline({ incidentInitial }) {
  const [incidents, setIncidents] = useState([])
  const [choix, setChoix] = useState(incidentInitial)
  const [replay, setReplay] = useState(null)
  const [pos, setPos] = useState(0)
  const [lecture, setLecture] = useState(false)
  const [vitesse, setVitesse] = useState(2)

  useEffect(() => {
    api.getIncidents().then((l) => {
      setIncidents(l)
      if (!choix && l.length) setChoix(l[0].id)
    })
  }, [])

  useEffect(() => {
    if (!choix) return
    setLecture(false)
    api.getReplay(choix).then((r) => { setReplay(r); setPos(0) })
  }, [choix])

  const mesures = replay?.mesures || []

  // Lecteur : avance d'une mesure toutes les (1 s / vitesse)
  useEffect(() => {
    if (!lecture) return
    const id = setInterval(() => {
      setPos((p) => {
        if (p >= mesures.length - 1) { setLecture(false); return p }
        return p + 1
      })
    }, 1000 / vitesse)
    return () => clearInterval(id)
  }, [lecture, vitesse, mesures.length])

  const courante = mesures[pos]
  const tCourant = courante?.t ?? 0
  const evtsPasses = useMemo(
    () => (replay?.evenements || []).filter((e) => courante && Date.parse(e.ts) <= courante.ts),
    [replay, courante]
  )

  // Photo de la webcam : la dernière prise avant la position du curseur
  const photos = (replay?.evenements || []).filter((e) => e.photo)
  const photoCourante = [...photos].reverse().find((e) => evtsPasses.includes(e)) || null
  // Séquence vidéo de l'incident (1 image / s, 10 s avant -> 10 s après) synchronisée avec le curseur
  const images = replay?.images || []
  const idxImage = (() => {
    let k = -1
    images.forEach((im, i) => { if (im.t <= tCourant) k = i })
    return k
  })()
  const imageCourante = idxImage >= 0 ? images[idxImage] : null

  return (
    <div className="page-timeline">
      <aside className="liste-incidents">
        <div className="panneau-titre">Incidents</div>
        {incidents.length === 0 && <div className="note">Aucun incident.</div>}
        {incidents.map((i) => (
          <button key={i.id} className={'incident' + (i.id === choix ? ' choisi' : '')} onClick={() => setChoix(i.id)}>
            <div className="inc-titre">{i.titre}</div>
            <div className="inc-date">{fmtDate(i.debut)}</div>
            <div className="inc-tags">{i.alertes.map((a) => <span key={a} className="tag">{NOMS_ALERTES[a] || a}</span>)}</div>
          </button>
        ))}
      </aside>

      <section className="lecteur">
        {!replay && <div className="chargement">Choisis un incident à rejouer.</div>}
        {replay && courante && (
          <>
            <div className="lecteur-entete">
              <div>
                <h2>{replay.titre}</h2>
                <div className="note">{fmtDate(replay.debut)} · {mesures.length} mesures</div>
              </div>
              <BandeauEtat etat={courante.etat} alertes={courante.alertes} petit />
            </div>

            <div className="controles">
              <button onClick={() => { setPos(0); setLecture(false) }} title="Début">⏮</button>
              <button className="play" onClick={() => {
                if (pos >= mesures.length - 1) setPos(0)
                setLecture(!lecture)
              }}>{lecture ? '⏸ Pause' : '▶ Lecture'}</button>
              <select value={vitesse} onChange={(e) => setVitesse(Number(e.target.value))}>
                {VITESSES.map((v) => <option key={v} value={v}>×{v}</option>)}
              </select>
              <input type="range" min={0} max={mesures.length - 1} value={pos}
                onChange={(e) => { setPos(Number(e.target.value)); setLecture(false) }} />
              <div className="temps">
                <b>{tCourant >= 0 ? `T+${tCourant}` : `T${tCourant}`} s</b>
                <span>{fmtHeure(courante.ts)}</span>
              </div>
            </div>

            <div className="valeurs-instant">
              <Val l="Temp." v={courante.temp} u="°C" />
              <Val l="Hum." v={courante.hum} u="%" />
              <Val l="Distance" v={courante.dist > 0 ? courante.dist : '—'} u="cm" />
              <Val l="Gaz" v={courante.gaz} />
              <Val l="Son" v={courante.son} />
              <Val l="Mouvement" v={courante.pir ? 'OUI' : 'non'} />
            </div>

            {images.length > 0 && (
              <div className="panneau photo-incident">
                <div className="panneau-titre">
                  Caméra de l'incident <span className="note">· 1 image / s · synchronisée avec la lecture</span>
                </div>
                {imageCourante ? (
                  <>
                    <img src={api.urlComplete(imageCourante.url)} alt="Image de l'incident" />
                    <div className="note">
                      Image {idxImage + 1}/{images.length} · {imageCourante.t >= 0 ? `T+${imageCourante.t}` : `T${imageCourante.t}`} s ·
                      {' '}{fmtHeure(imageCourante.ts)} · SHA-256 : <code>{imageCourante.sha256.slice(0, 16)}…</code>
                    </div>
                    <div className="vignettes">
                      {images.map((im, i) => (
                        <button key={im.ts} className={'vignette' + (i === idxImage ? ' active' : '')}
                          onClick={() => { const p = mesures.findIndex((m) => m.t >= im.t); if (p >= 0) { setPos(p); setLecture(false) } }}
                          title={`T${im.t >= 0 ? '+' : ''}${im.t} s`}>
                          <img src={api.urlComplete(im.url)} alt="" loading="lazy" />
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="note">Les images commencent {Math.abs(images[0].t)} s avant l'alerte : avance la lecture.</div>
                )}
              </div>
            )}

            {images.length === 0 && photos.length > 0 && (
              <div className="panneau photo-incident">
                <div className="panneau-titre">Photo de la webcam</div>
                {photoCourante ? (
                  <>
                    <img src={api.urlComplete(photoCourante.photo)} alt="Photo prise pendant l'alerte" />
                    <div className="note">
                      Prise à {fmtHeure(photoCourante.ts)} · empreinte SHA-256 : <code>{photoCourante.photo_sha256.slice(0, 16)}…</code>
                    </div>
                  </>
                ) : (
                  <div className="note">La photo apparaîtra au moment de l'alerte (avance la lecture).</div>
                )}
              </div>
            )}

            <div className="grille-courbes">
              {COURBES.map((c) => (
                <div className="courbe" key={c.cle}>
                  <div className="courbe-titre">{c.titre}</div>
                  <ResponsiveContainer width="100%" height={150}>
                    <LineChart data={mesures} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid stroke="#1e293b" />
                      <XAxis dataKey="t" stroke="#64748b" fontSize={11} />
                      <YAxis stroke="#64748b" fontSize={11} domain={c.domaine || ['auto', 'auto']} />
                      <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} labelFormatter={(t) => `T${t >= 0 ? '+' : ''}${t} s`} />
                      <ReferenceLine x={0} stroke="#ef4444" strokeDasharray="4 4" />
                      {c.seuil != null && <ReferenceLine y={c.seuil} stroke="#ef4444" strokeOpacity={0.5} />}
                      {c.seuilRef && <ReferenceLine y={courante.ref_gaz + SEUILS.ecartGaz} stroke="#ef4444" strokeOpacity={0.5} />}
                      <Line type="monotone" dataKey={c.cle} stroke={c.couleur} strokeWidth={2} dot={false} isAnimationActive={false} />
                      <ReferenceLine x={tCourant} stroke="#f8fafc" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ))}
            </div>

            <div className="panneau">
              <div className="panneau-titre">Événements du journal ({evtsPasses.length}/{replay.evenements.length})</div>
              {replay.evenements.map((e) => {
                const passe = evtsPasses.includes(e)
                return (
                  <div key={e.id} className={'evt' + (passe ? '' : ' futur')}>
                    <span className="pastille" style={{ background: ETATS[e.type]?.color || '#64748b' }} />
                    <span className="evt-heure">{fmtHeure(e.ts)}</span>
                    <span className="evt-type">{ETATS[e.type]?.label || e.type}</span>
                    <span className="evt-detail">{(e.details.alertes || []).map((a) => NOMS_ALERTES[a] || a).join(', ')}</span>
                    {e.photo && <span title="Photo webcam">📷</span>}
                    <code className="evt-hash">#{e.hash.slice(0, 8)}</code>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </section>
    </div>
  )
}

function Val({ l, v, u }) {
  return (
    <div className="val">
      <span>{l}</span>
      <b>{v ?? '—'}{u && v !== '—' ? ` ${u}` : ''}</b>
    </div>
  )
}
