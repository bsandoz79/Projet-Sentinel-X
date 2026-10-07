export default function BadgeIntegrite({ integrite, onClick }) {
  if (!integrite) return <button className="badge gris" onClick={onClick}>Journal : …</button>
  return integrite.ok ? (
    <button className="badge vert" onClick={onClick}>✔ Journal intègre</button>
  ) : (
    <button className="badge rouge clignote" onClick={onClick}>✘ Journal falsifié</button>
  )
}
