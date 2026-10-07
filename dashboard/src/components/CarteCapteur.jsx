import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts'

export default function CarteCapteur({ titre, valeur, unite, sous, historique, cle, couleur, alerte }) {
  return (
    <div className={'carte' + (alerte ? ' carte-alerte' : '')}>
      <div className="carte-titre">{titre}</div>
      <div className="carte-valeur">
        {valeur ?? '—'}
        {valeur != null && unite && <span className="unite">{unite}</span>}
      </div>
      {sous && <div className="carte-sous">{sous}</div>}
      {historique && (
        <div className="sparkline">
          <ResponsiveContainer width="100%" height={48}>
            <LineChart data={historique}>
              <YAxis hide domain={['auto', 'auto']} />
              <Line type="monotone" dataKey={cle} stroke={couleur} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
