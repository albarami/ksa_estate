import { motion } from 'framer-motion'
import { Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Line, ComposedChart, CartesianGrid } from 'recharts'
import type { CashFlows, Labels } from '../types'
import { formatNum } from '../utils/formatters'

interface Props {
  cashFlows: CashFlows
  labels: Labels
}

export default function CashFlowChart({ cashFlows, labels }: Props) {
  const data = cashFlows.years.map((yr, i) => ({
    name: `Y${yr}`,
    inflows: cashFlows.inflows_sales[i],
    outflows: -cashFlows.outflows_total[i],
    net: cashFlows.net_cash_flow[i],
    cumulative: cashFlows.cumulative[i],
  }))

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      <h3 className="font-bold text-lg mb-4">{labels.cashFlows}</h3>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="name" stroke="var(--color-text-dim)" fontSize={12} />
          <YAxis
            stroke="var(--color-text-dim)"
            fontSize={10}
            tickFormatter={(v: number) => `${(v / 1e6).toFixed(0)}M`}
          />
          <Tooltip
            contentStyle={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 8 }}
            labelStyle={{ color: 'var(--color-text)' }}
            formatter={(v, name) => [
              `${formatNum(v as number)} ر.س`,
              name === 'inflows' ? labels.inflows :
              name === 'outflows' ? labels.outflows :
              name === 'net' ? labels.net :
              labels.cumulative,
            ]}
          />
          <Bar dataKey="inflows" fill="var(--color-positive)" radius={[4, 4, 0, 0]} />
          <Bar dataKey="outflows" fill="var(--color-negative)" radius={[4, 4, 0, 0]} />
          <Line type="monotone" dataKey="cumulative" stroke="var(--color-gold)" strokeWidth={2} dot={{ r: 4, fill: 'var(--color-gold)' }} />
        </ComposedChart>
      </ResponsiveContainer>
    </motion.div>
  )
}
