// =====================================================
//  MODE DÉMO : fausses données générées dans le navigateur
//  Même logique de décision que sentinel_pi.py
// =====================================================
import { SEUILS, GENESE, hashEvenement, verifierChaine } from '../utils.js'

const REF_GAZ = 300
let graine = 42
const alea = () => ((graine = (graine * 16807) % 2147483647) / 2147483647)
const bruit = (amp) => (alea() - 0.5) * 2 * amp

// ---------- Scénarios d'incident (dt = secondes depuis le début de l'incident) ----------
const SCENARIOS = {
  intrusion: {
    titre: 'Intrusion détectée',
    duree: 60,
    appliquer(m, dt) {
      if (dt >= -8 && dt < 30) m.pir = true
      if (dt >= -8 && dt < 0) m.dist = Math.round(180 - ((dt + 8) / 8) * 150)
      else if (dt >= 0 && dt < 25) m.dist = Math.round(22 + bruit(3))
      else if (dt >= 25 && dt < 35) m.dist = Math.round(25 + ((dt - 25) / 10) * 155)
      if (dt >= 2 && dt < 6) m.son = Math.round(650 + bruit(80))
    },
  },
  gaz: {
    titre: 'Fuite de gaz',
    duree: 60,
    appliquer(m, dt) {
      if (dt >= 0 && dt < 20) m.gaz = Math.round(REF_GAZ + (dt / 20) * 380 + bruit(10))
      else if (dt >= 20 && dt < 40) m.gaz = Math.round(680 + bruit(15))
      else if (dt >= 40 && dt < 60) m.gaz = Math.round(680 - ((dt - 40) / 20) * 370 + bruit(10))
    },
  },
  chaleur: {
    titre: 'Départ de feu (chaleur + gaz)',
    duree: 60,
    appliquer(m, dt) {
      if (dt >= 0) {
        const k = Math.min(1, dt / 25) * (dt > 45 ? Math.max(0, 1 - (dt - 45) / 15) : 1)
        m.temp = +(m.temp + k * 12).toFixed(1)
        m.hum = Math.round(m.hum - k * 15)
        m.gaz = Math.round(m.gaz + k * 160)
      }
    },
  },
}

// ---------- Une mesure "au calme" ----------
function mesureCalme(ts) {
  const s = ts / 1000
  return {
    ts,
    temp: +(22.5 + Math.sin(s / 900) * 0.6 + bruit(0.1)).toFixed(1),
    hum: Math.round(45 + Math.sin(s / 1200) * 3 + bruit(0.8)),
    dist: Math.round(180 + bruit(2)),
    gaz: Math.round(REF_GAZ + bruit(6)),
    ref_gaz: REF_GAZ,
    son: Math.round(120 + bruit(35)),
    pir: false,
  }
}

// ---------- Décision (copie de sentinel_pi.py) ----------
function decider(m) {
  const a = []
  if (m.temp > SEUILS.temp) a.push('temperature')
  if (m.hum > SEUILS.hum) a.push('humidite')
  if (m.dist > 0 && m.dist < SEUILS.distAlerte) a.push('intrusion')
  if (m.gaz > m.ref_gaz + SEUILS.ecartGaz) a.push('gaz')
  if (m.son > SEUILS.son) a.push('bruit')
  if (m.pir && m.dist > 0 && m.dist < SEUILS.distVigilance) a.push('presence')
  let vig = false
  if (!a.length) {
    if (m.pir) vig = true
    if (m.dist > 0 && m.dist < SEUILS.distVigilance) vig = true
    if (m.temp > SEUILS.temp - 3 || m.hum > SEUILS.hum - 10) vig = true
    if (m.gaz > m.ref_gaz + SEUILS.ecartGaz / 2) vig = true
  }
  m.alertes = a
  m.etat = a.length ? 'alerte' : vig ? 'vigilance' : 'ok'
  return m
}

// ---------- Stockage en mémoire ----------
const evenements = []
const incidents = []
let precedent = null

function ajouterEvenement(type, ts, details) {
  const prev = evenements.length ? evenements[evenements.length - 1].hash : GENESE
  const evt = { ts: new Date(ts).toISOString(), type, details, prev }
  evt.hash = hashEvenement(evt)
  evt.id = evenements.length + 1
  evenements.push(evt)
  return evt
}

function suivreEtat(m) {
  const cle = m.etat + '|' + m.alertes.join(',')
  if (cle !== precedent) {
    const { ts, etat, ...valeurs } = m
    ajouterEvenement(etat, ts, valeurs)
    precedent = cle
  }
}

function enregistrerIncident(nom, debut, mesures) {
  const evts = evenements.filter((e) => {
    const t = Date.parse(e.ts)
    return t >= mesures[0].ts && t <= mesures[mesures.length - 1].ts
  })
  const alertes = [...new Set(mesures.flatMap((m) => m.alertes))]
  incidents.push({
    id: incidents.length + 1,
    titre: SCENARIOS[nom].titre,
    scenario: nom,
    debut: new Date(debut).toISOString(),
    fin: new Date(debut + SCENARIOS[nom].duree * 1000).toISOString(),
    alertes,
    mesures,
    evenements: evts.map((e) => e.id),
  })
}

// ---------- Historique : démarrage + 3 incidents passés ----------
;(function historique() {
  const now = Date.now()
  const debut = now - 2 * 3600e3
  ajouterEvenement('demarrage', debut, { ref_gaz: REF_GAZ })
  precedent = 'ok|'
  const passes = [['intrusion', now - 95 * 60e3], ['gaz', now - 52 * 60e3], ['chaleur', now - 18 * 60e3]]
  for (const [nom, t0] of passes) {
    const mesures = []
    for (let dt = -30; dt <= SCENARIOS[nom].duree; dt++) {
      const m = mesureCalme(t0 + dt * 1000)
      SCENARIOS[nom].appliquer(m, dt)
      decider(m)
      suivreEtat(m)
      mesures.push({ ...m, t: dt })
    }
    enregistrerIncident(nom, t0, mesures)
  }
})()

// ---------- Live ----------
let simulation = null // { nom, t0, mesures }

export const mock = {
  mode: 'demo',

  async getLive() {
    const ts = Date.now()
    const m = mesureCalme(ts)
    if (simulation) {
      const dt = Math.round((ts - simulation.t0) / 1000)
      SCENARIOS[simulation.nom].appliquer(m, dt)
      decider(m)
      simulation.mesures.push({ ...m, t: dt })
      if (dt >= SCENARIOS[simulation.nom].duree) {
        suivreEtat(m)
        enregistrerIncident(simulation.nom, simulation.t0, simulation.mesures)
        simulation = null
        return m
      }
    } else decider(m)
    suivreEtat(m)
    return m
  },

  async getIncidents() {
    return incidents.map(({ mesures, ...i }) => i).reverse()
  },

  async getReplay(id) {
    const inc = incidents.find((i) => i.id === Number(id))
    if (!inc) return null
    return { ...inc, evenements: evenements.filter((e) => inc.evenements.includes(e.id)) }
  },

  async getEvenements() {
    return evenements.map(({ _original, ...e }) => ({ ...e, details: { ...e.details } }))
  },

  async verifierIntegrite() {
    return verifierChaine(evenements)
  },

  // --- spécifique à la démo ---
  simuler(nom) {
    if (simulation) return false
    const t0 = Date.now() + 8000 // l'incident "commence" dans 8 s (approche)
    simulation = { nom, t0, mesures: [] }
    return true
  },
  simulationEnCours: () => (simulation ? simulation.nom : null),

  falsifier() {
    const cible = evenements.find((e) => e.type === 'alerte' && e.details.alertes?.includes('gaz'))
      || evenements[Math.floor(evenements.length / 2)]
    cible._original = cible._original ?? JSON.stringify(cible.details)
    cible.details.gaz = 310 // on "efface" la fuite de gaz
    cible.details.alertes = []
    return cible.id
  },
  restaurer() {
    for (const e of evenements) if (e._original) { e.details = JSON.parse(e._original); delete e._original }
  },
}
