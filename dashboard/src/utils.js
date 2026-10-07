// ---------- États (mêmes couleurs que l'écran LCD) ----------
export const ETATS = {
  ok:        { label: 'Tout est OK',        color: '#22c55e' },
  vigilance: { label: 'Vigilance',          color: '#f59e0b' },
  alerte:    { label: 'ALERTE',             color: '#ef4444' },
  dht:       { label: 'Capteur DHT en erreur', color: '#a855f7' },
}

export const NOMS_ALERTES = {
  temperature: 'Température',
  humidite: 'Humidité',
  intrusion: 'Intrusion proche',
  gaz: 'Gaz',
  bruit: 'Bruit fort',
  presence: 'Présence confirmée',
  mouvement: 'Mouvement',
}

// Mêmes seuils que sentinel_pi.py
export const SEUILS = {
  temp: 30, hum: 80, distAlerte: 30, distVigilance: 100, ecartGaz: 100, son: 600,
}

export const fmtHeure = (ts) => new Date(ts).toLocaleTimeString('fr-FR')
export const fmtDate = (ts) =>
  new Date(ts).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
export const court = (h) => (h ? h.slice(0, 10) + '…' : '—')

// ---------- JSON canonique (clés triées) ----------
export function stableStringify(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v)
  if (Array.isArray(v)) return '[' + v.map(stableStringify).join(',') + ']'
  return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + stableStringify(v[k])).join(',') + '}'
}

// ---------- SHA-256 en pur JavaScript (marche aussi en http:// sur le réseau local) ----------
const K = [], H0 = []
;(() => {
  const frac = (x) => ((x - Math.floor(x)) * 2 ** 32) >>> 0
  let n = 2, found = 0
  while (found < 64) {
    let premier = true
    for (let d = 2; d * d <= n; d++) if (n % d === 0) { premier = false; break }
    if (premier) {
      if (found < 8) H0.push(frac(Math.sqrt(n)))
      K.push(frac(Math.cbrt(n)))
      found++
    }
    n++
  }
})()
const ror = (x, n) => (x >>> n) | (x << (32 - n))

export function sha256(texte) {
  const bytes = new TextEncoder().encode(texte)
  const l = bytes.length
  const buf = new Uint8Array(((l + 9 + 63) >> 6) << 6)
  buf.set(bytes)
  buf[l] = 0x80
  const dv = new DataView(buf.buffer)
  dv.setUint32(buf.length - 4, (l * 8) >>> 0)
  dv.setUint32(buf.length - 8, Math.floor((l * 8) / 2 ** 32))
  const h = H0.slice()
  const w = new Uint32Array(64)
  for (let i = 0; i < buf.length; i += 64) {
    for (let j = 0; j < 16; j++) w[j] = dv.getUint32(i + j * 4)
    for (let j = 16; j < 64; j++) {
      const s0 = ror(w[j - 15], 7) ^ ror(w[j - 15], 18) ^ (w[j - 15] >>> 3)
      const s1 = ror(w[j - 2], 17) ^ ror(w[j - 2], 19) ^ (w[j - 2] >>> 10)
      w[j] = (w[j - 16] + s0 + w[j - 7] + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, hh] = h
    for (let j = 0; j < 64; j++) {
      const S1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25)
      const ch = (e & f) ^ (~e & g)
      const t1 = (hh + S1 + ch + K[j] + w[j]) >>> 0
      const S0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22)
      const maj = (a & b) ^ (a & c) ^ (b & c)
      const t2 = (S0 + maj) >>> 0
      hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0
    }
    ;[a, b, c, d, e, f, g, hh].forEach((v, k) => (h[k] = (h[k] + v) >>> 0))
  }
  return h.map((x) => x.toString(16).padStart(8, '0')).join('')
}

// ---------- Journal chaîné ----------
export const GENESE = '0'.repeat(64)

export function hashEvenement(evt) {
  const { hash, id, _original, ...contenu } = evt
  return sha256(stableStringify(contenu))
}

// Recalcule toute la chaîne : renvoie le premier maillon cassé
export function verifierChaine(evenements) {
  let prev = GENESE
  for (let i = 0; i < evenements.length; i++) {
    const e = evenements[i]
    if (e.prev !== prev || hashEvenement(e) !== e.hash) {
      return { ok: false, total: evenements.length, premier_invalide: i }
    }
    prev = e.hash
  }
  return { ok: true, total: evenements.length, premier_invalide: null }
}
