// =====================================================
//  MODE API : vraies données venant du Pi (FastAPI)
//  Contrat attendu : voir README.md
// =====================================================
export function real(BASE) {
  const get = async (chemin) => {
    const r = await fetch(BASE.replace(/\/$/, '') + chemin)
    if (!r.ok) throw new Error(`${r.status} sur ${chemin}`)
    return r.json()
  }
  return {
    mode: 'api',
    getLive: () => get('/api/live'),
    getIncidents: () => get('/api/incidents'),
    getReplay: (id) => get(`/api/incidents/${id}/replay`),
    getEvenements: () => get('/api/evenements'),
    verifierIntegrite: () => get('/api/integrite'),
  }
}
