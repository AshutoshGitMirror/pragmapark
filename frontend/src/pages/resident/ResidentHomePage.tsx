import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../../context/AuthContext'
import {
  listPermits,
  listShares,
  createShare,
  cancelShare,
  type ResidentProfileResponse,
  type ShareListingResponse,
} from '../../api/residentClient'

const VIOLET = '#a855f7'
const VIOLET_DIM = 'rgba(168,85,247,0.12)'

export default function ResidentHomePage() {
  const { user } = useAuth()
  const [permit, setPermit] = useState<ResidentProfileResponse | null>(null)
  const [listing, setListing] = useState<ShareListingResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toggling, setToggling] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [permits, shares] = await Promise.all([listPermits(), listShares()])
      const myPermit = permits.find((p) => p.user_email === user?.email) || permits[0] || null
      setPermit(myPermit)
      const myListing = myPermit
        ? shares.find((s) => s.resident_profile_id === myPermit.id && s.status === 'active') || null
        : null
      setListing(myListing)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load your slot. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [user?.email])

  useEffect(() => {
    load()
  }, [load])

  const shareMySlot = async () => {
    if (!permit) return
    setToggling(true)
    try {
      await createShare({
        resident_profile_id: permit.id,
        price_per_hour: 40,
        available_from: '09:00',
        available_until: '18:00',
        max_advance_days: 7,
      })
      await load()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not share your slot.')
    } finally {
      setToggling(false)
    }
  }

  const stopSharing = async () => {
    if (!listing) return
    setToggling(true)
    try {
      await cancelShare(listing.id)
      setListing(null)
      await load()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not stop sharing.')
    } finally {
      setToggling(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-[11px] font-mono animate-pulse" style={{ color: VIOLET }}>Loading your slot…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-3">
        <div className="rounded-xl px-4 py-3 text-[12px] font-mono"
          style={{ background: 'rgba(240,64,96,0.08)', border: '1px solid rgba(240,64,96,0.2)', color: '#ff6b6b' }}>
          {error}
        </div>
        <button onClick={load}
          className="text-[11px] font-mono px-3 py-1.5 rounded-lg"
          style={{ color: VIOLET, border: `1px solid ${VIOLET_DIM}` }}>
          Retry
        </button>
      </div>
    )
  }

  if (!permit) {
    return (
      <div className="rounded-2xl p-6 text-center" style={{ background: '#14101f', border: `1px solid ${VIOLET_DIM}` }}>
        <p className="text-sm text-white mb-1">No residential permit found</p>
        <p className="text-[11px] text-dim">Register a home slot to start sharing it with city drivers.</p>
      </div>
    )
  }

  const slotLabel = permit.lot_name
    ? `${permit.lot_name} · Slot ${permit.slot_index}`
    : `Home Slot ${permit.slot_index}`

  return (
    <div className="space-y-4">
      <div className="rounded-2xl p-6" style={{ background: '#14101f', border: `1px solid ${VIOLET_DIM}` }}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xl">🏠</span>
          <h2 className="text-base font-semibold text-white">Your Home Slot</h2>
        </div>
        <p className="text-[11px] text-dim mb-4">{slotLabel}</p>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
            <p className="text-[10px] uppercase tracking-wider text-dim">Monthly rate</p>
            <p className="text-sm font-semibold text-white">₹{permit.monthly_rate.toFixed(2)}</p>
          </div>
          <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
            <p className="text-[10px] uppercase tracking-wider text-dim">Permit</p>
            <p className="text-sm font-semibold text-white capitalize">{permit.permit_type}</p>
          </div>
          <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
            <p className="text-[10px] uppercase tracking-wider text-dim">Vehicle</p>
            <p className="text-sm font-semibold text-white">{permit.registered_vehicle || '—'}</p>
          </div>
          <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
            <p className="text-[10px] uppercase tracking-wider text-dim">Valid until</p>
            <p className="text-sm font-semibold text-white">{permit.end_date}</p>
          </div>
        </div>
      </div>

      <div className="rounded-2xl p-6" style={{ background: '#14101f', border: `1px solid ${VIOLET_DIM}` }}>
        <h3 className="text-sm font-semibold text-white mb-1">Share with drivers</h3>
        <p className="text-[11px] text-dim mb-4">
          When you're at work, your home slot becomes supply for someone else. Toggle sharing to list it on the city map.
        </p>

        {listing ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: '#00c785', boxShadow: '0 0 6px #00c785' }} />
              <span className="text-[12px] font-medium text-white">Currently shared</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
                <p className="text-[10px] uppercase tracking-wider text-dim">Price / hour</p>
                <p className="text-sm font-semibold text-white">₹{listing.price_per_hour.toFixed(2)}</p>
              </div>
              <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
                <p className="text-[10px] uppercase tracking-wider text-dim">Available</p>
                <p className="text-sm font-semibold text-white">
                  {listing.available_from || '—'} – {listing.available_until || '—'}
                </p>
              </div>
            </div>
            <button onClick={stopSharing} disabled={toggling}
              className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-50"
              style={{ background: '#ff4757' }}>
              {toggling ? 'Updating…' : 'Stop sharing this slot'}
            </button>
          </div>
        ) : (
          <button onClick={shareMySlot} disabled={toggling}
            className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-50"
            style={{ background: VIOLET, boxShadow: '0 4px 20px rgba(168,85,247,0.3)' }}>
            {toggling ? 'Sharing…' : 'Share my slot (₹40/hr · 09:00–18:00)'}
          </button>
        )}
      </div>
    </div>
  )
}
