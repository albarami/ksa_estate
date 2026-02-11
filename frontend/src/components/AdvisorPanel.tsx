import { useState } from 'react'
import { motion } from 'framer-motion'
import { fetchAdvice } from '../utils/api'
import type { ProFormaResult, Labels } from '../types'

interface Props {
  parcelId: number
  proforma: ProFormaResult | null
  labels: Labels
}

export default function AdvisorPanel({ parcelId, proforma, labels }: Props) {
  const [response, setResponse] = useState('')
  const [loading, setLoading] = useState(false)

  const questions = [
    labels.advisorQ1,
    labels.advisorQ2,
    labels.advisorQ3,
    labels.advisorQ4,
  ]

  const ask = async (q: string) => {
    setLoading(true)
    setResponse('')
    try {
      const r = await fetchAdvice(parcelId, proforma, q)
      setResponse(r.response)
    } catch (err) {
      setResponse(`Error: ${err}`)
    }
    setLoading(false)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5"
    >
      <h3 className="font-bold text-lg mb-3">{labels.advisor}</h3>

      <div className="flex flex-wrap gap-2 mb-4">
        {questions.map((q) => (
          <button
            key={q}
            onClick={() => ask(q)}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-sm border border-[var(--color-border)] hover:border-[var(--color-gold)] hover:text-[var(--color-gold)] transition-colors disabled:opacity-50"
          >
            {q}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-[var(--color-text-dim)] py-4">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
            className="w-4 h-4 border-2 border-[var(--color-gold)] border-t-transparent rounded-full"
          />
          <span>{labels.askAdvisor}...</span>
        </div>
      )}

      {response && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="p-4 rounded-lg bg-[var(--color-bg)] text-sm leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto"
        >
          {response}
        </motion.div>
      )}
    </motion.div>
  )
}
