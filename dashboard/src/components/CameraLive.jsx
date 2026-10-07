import { useEffect, useState } from 'react'
import { api } from '../api'

// Image de la webcam du Pi, rafraîchie toutes les 3 s
export default function CameraLive({ alerte }) {
  const [src, setSrc] = useState(api.cameraUrl())
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    const id = setInterval(() => setSrc(api.cameraUrl()), 3000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className={'panneau camera' + (alerte ? ' camera-alerte' : '')}>
      <div className="panneau-titre">
        Webcam <span className="rec">● EN DIRECT</span>
      </div>
      {erreur ? (
        <div className="note">Caméra non disponible (branchée sur le Pi ? conteneur API relancé ?)</div>
      ) : null}
      <img src={src} alt="Webcam" style={{ display: erreur ? 'none' : 'block' }}
        onError={() => setErreur(true)} onLoad={() => setErreur(false)} />
    </div>
  )
}
