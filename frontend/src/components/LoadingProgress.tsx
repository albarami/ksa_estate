import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { fetchParcel, fetchProforma, locateParcel } from '../utils/api'
import type { LandObject, ProFormaResult, Overrides, Labels } from '../types'

interface Props {
  parcelId: number | null
  query?: string  // Google Maps URL or coordinates (when parcelId is null)
  overrides: Overrides
  labels: Labels
  onComplete: (land: LandObject, proforma: ProFormaResult) => void
  onError: (msg: string) => void
}

type Step = 'parcel' | 'regulations' | 'proforma' | 'done'

export default function LoadingProgress({ parcelId, query, overrides, labels, onComplete, onError }: Props) {
  const [step, setStep] = useState<Step>('parcel')

  useEffect(() => {
    let cancelled = false

    async function run() {
      try {
        let pid = parcelId

        // Step 1: locate or fetch parcel
        setStep('parcel')
        if (!pid && query) {
          const located = await locateParcel(query)
          if (cancelled) return
          pid = located.parcel_id
        } else if (pid) {
          await fetchParcel(pid)
          if (cancelled) return
        } else {
          onError('No parcel ID or location provided')
          return
        }

        setStep('regulations')
        await new Promise(r => setTimeout(r, 400))
        if (cancelled) return

        setStep('proforma')
        const result = await fetchProforma(pid!, overrides)
        if (cancelled) return
        setStep('done')

        await new Promise(r => setTimeout(r, 300))
        if (cancelled) return
        onComplete(result.land_object, result.proforma)
      } catch (err) {
        if (!cancelled) onError(String(err))
      }
    }

    run()
    return () => { cancelled = true }
  }, [parcelId, query]) // eslint-disable-line react-hooks/exhaustive-deps

  const steps: { key: Step; label: string }[] = [
    { key: 'parcel', label: labels.step1 },
    { key: 'regulations', label: labels.step2 },
    { key: 'proforma', label: labels.step3 },
  ]

  const stepOrder: Step[] = ['parcel', 'regulations', 'proforma', 'done']
  const currentIdx = stepOrder.indexOf(step)

  return (
    <div className="min-h-screen flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md space-y-4 px-4"
      >
        <h2 className="text-2xl font-bold text-center mb-8 truncate max-w-md" style={{ color: 'var(--color-gold)' }}>
          {parcelId ? parcelId.toLocaleString() : '📍 ' + (query || '').substring(0, 50)}
        </h2>

        {steps.map((s, i) => {
          const isActive = currentIdx === i
          const isDone = currentIdx > i

          return (
            <motion.div
              key={s.key}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.15 }}
              className={`flex items-center gap-4 p-4 rounded-xl border transition-all ${
                isDone ? 'border-[var(--color-positive)] bg-[var(--color-positive)]/5' :
                isActive ? 'border-[var(--color-gold)] bg-[var(--color-gold)]/5' :
                'border-[var(--color-border)] opacity-40'
              }`}
            >
              <div className="w-8 h-8 flex items-center justify-center">
                <AnimatePresence mode="wait">
                  {isDone ? (
                    <motion.svg
                      key="check"
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="w-6 h-6"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="var(--color-positive)"
                      strokeWidth={3}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </motion.svg>
                  ) : isActive ? (
                    <motion.div
                      key="spinner"
                      animate={{ rotate: 360 }}
                      transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
                      className="w-5 h-5 border-2 border-[var(--color-gold)] border-t-transparent rounded-full"
                    />
                  ) : (
                    <div className="w-3 h-3 rounded-full bg-[var(--color-border)]" />
                  )}
                </AnimatePresence>
              </div>
              <span className={`text-base ${isDone ? 'text-[var(--color-positive)]' : isActive ? 'text-[var(--color-text)]' : ''}`}>
                {s.label}
              </span>
            </motion.div>
          )
        })}

        {step === 'done' && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center text-[var(--color-positive)] font-semibold mt-6"
          >
            {labels.complete} ✓
          </motion.p>
        )}
      </motion.div>
    </div>
  )
}
