import { mock } from './mock.js'
import { real } from './real.js'

const BASE = import.meta.env.VITE_API_URL
// Pas d'adresse d'API => mode démo (données simulées)
// "/" => l'API est servie par le même serveur que le dashboard (nginx sécurisé du Pi)
export const api = BASE ? real(BASE) : mock
