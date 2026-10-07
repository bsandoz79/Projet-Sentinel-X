import { useEffect, useState } from 'react'
import { api } from '../api'

// Flux vidéo MJPEG de la webcam du Pi (reconnexion auto si le flux coupe)
export default function CameraLive({ alerte }) {
  const [src, setSrc] = useState(api.cameraUrl())
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    if (!erreur) return
    const id = setTimeout(() => setSrc(api.cameraUrl()), 3000)   // nouvel essai dans 3 s
    return () => clearTimeout(id)
  }, [erreur, src])

  return (
    <div className={'panneau camera' + (alerte ? ' camera-alerte' : '')}>
      <div className="panneau-titre">
        Webcam <span className="rec">● EN DIRECT</span>
      </div>
      {erreur && <div className="note">Caméra non disponible, nouvel essai…</div>}
      <img key={src} src={src} alt="Webcam" style={{ display: erreur ? 'none' : 'block' }}
        onError={() => setErreur(true)} onLoad={() => setErreur(false)} />
    </div>
  )
}
