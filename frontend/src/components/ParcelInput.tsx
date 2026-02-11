import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Labels } from '../utils/i18n'

const EXAMPLES = [3710897, 3710898, 3900000]

interface Props {
  labels: Labels
  onSubmit: (query: string) => void
}

export default function ParcelInput({ labels, onSubmit }: Props) {
  const [value, setValue] = useState('')

  const handleSubmit = () => {
    const trimmed = value.trim()
    if (trimmed) onSubmit(trimmed)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      className="min-h-screen flex flex-col items-center justify-center px-4"
    >
      <motion.h1
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="text-4xl md:text-5xl font-bold mb-2 text-center"
        style={{ color: 'var(--color-gold)' }}
      >
        {labels.appTitle}
      </motion.h1>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="text-[var(--color-text-dim)] mb-10 text-lg"
      >
        Riyadh Parcel Intelligence
      </motion.p>

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.5 }}
        className="flex gap-3 w-full max-w-lg"
      >
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          placeholder="رقم القطعة أو رابط Google Maps"
          className="flex-1 bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl px-5 py-4 text-lg text-center outline-none focus:border-[var(--color-gold)] transition-colors"
          dir="ltr"
        />
        <button
          onClick={handleSubmit}
          className="px-8 py-4 rounded-xl text-lg font-semibold transition-all hover:scale-105 active:scale-95"
          style={{ background: 'var(--color-gold)', color: '#0A0A0F' }}
        >
          {labels.analyze}
        </button>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="mt-6 flex gap-2 items-center"
      >
        <span className="text-sm text-[var(--color-text-dim)]">{labels.examples}:</span>
        {EXAMPLES.map((id) => (
          <button
            key={id}
            onClick={() => { setValue(String(id)); onSubmit(String(id)) }}
            className="px-3 py-1 rounded-lg text-sm border border-[var(--color-border)] hover:border-[var(--color-gold)] hover:text-[var(--color-gold)] transition-colors"
          >
            {id.toLocaleString()}
          </button>
        ))}
      </motion.div>
    </motion.div>
  )
}
