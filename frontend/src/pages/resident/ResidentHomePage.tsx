import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../../context/AuthContext'
import {
  listPermits,
  listShares,
  createHomeSlot,
  createShare,
  cancelShare,
  type ResidentProfileResponse,
  type ShareListingResponse,
} from '../../api/residentClient'

const VIOLET = '#a855f7'
const VIOLET_DIM = 'rgba(168,85,247,0.12)'

const HOME_LOCATIONS = [
  { label: 'Bandra West, Mumbai', latitude: 19.0596, longitude: 72.8295 },
  { label: 'Powai, Mumbai', latitude: 19.1176, longitude: 72.9060 },
  { label: 'Dadar, Mumbai', latitude: 19.0178, longitude: 72.8478 },
  { label: 'Andheri East, Mumbai', latitude: 19.1197, longitude: 72.8468 },
  { label: 'Colaba, Mumbai', latitude: 18.9067, longitude: 72.8147 },
]

export default function ResidentHomePage() {
  const { user } = useAuth()
  const [permit, setPermit] = useState<ResidentProfileResponse | null>(null)
  const [listing, setListing] = useState<ShareListingResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toggling, setToggling] = useState(false)
  const [locationIndex, setLocationIndex] = useState(0)
  const [vehicle, setVehicle] = useState('')
  const [registering, setRegistering] = useState(false)

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

  const signalAvailability = async () => {
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
      setError(err?.response?.data?.detail || 'Could not signal slot availability.')
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

  const registerHomeSlot = async () => {
    const location = HOME_LOCATIONS[locationIndex]
    setRegistering(true)
    setError(null)
    try {
      await createHomeSlot({
        location_label: location.label,
        latitude: location.latitude,
        longitude: location.longitude,
        registered_vehicle: vehicle.trim() || undefined,
      })
      await load()
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Could not register your home slot.')
    } finally {
      setRegistering(false)
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
      <div className="max-w-xl rounded-2xl p-6 space-y-5" style={{ background: '#14101f', border: `1px solid ${VIOLET_DIM}` }}>
        <div>
          <p className="text-[10px] font-mono tracking-[3px] uppercase mb-2" style={{ color: VIOLET }}>Home parking</p>
          <h2 className="text-lg font-semibold text-white">Register your home slot</h2>
          <p className="text-[11px] text-dim mt-1">Choose an approximate neighborhood. Your home slot appears on the city map only when you share it.</p>
        </div>
        <label className="block">
          <span className="text-[10px] font-mono uppercase tracking-wider text-dim">Location</span>
          <select value={locationIndex} onChange={(e) => setLocationIndex(Number(e.target.value))}
            className="mt-1.5 w-full rounded-xl px-3 py-3 text-sm text-white outline-none"
            style={{ background: 'rgba(0,0,0,0.28)', border: `1px solid ${VIOLET_DIM}` }}>
            {HOME_LOCATIONS.map((location, index) => <option key={location.label} value={index}>{location.label}</option>)}
          </select>
          <span className="block mt-1.5 text-[10px] font-mono" style={{ color: VIOLET }}>
            ● {HOME_LOCATIONS[locationIndex].latitude.toFixed(4)}, {HOME_LOCATIONS[locationIndex].longitude.toFixed(4)} · Greater Mumbai
          </span>
        </label>
        <label className="block">
          <span className="text-[10px] font-mono uppercase tracking-wider text-dim">Vehicle plate <span className="normal-case tracking-normal">(optional)</span></span>
          <input value={vehicle} onChange={(e) => setVehicle(e.target.value.toUpperCase())} placeholder="MH01AB1234"
            className="mt-1.5 w-full rounded-xl px-3 py-3 text-sm text-white placeholder:text-[#5a5570] outline-none"
            style={{ background: 'rgba(0,0,0,0.28)', border: `1px solid ${VIOLET_DIM}` }} />
        </label>
        <div className="grid grid-cols-2 gap-3 text-[11px]">
          <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.22)' }}><span className="block text-dim">Resident permit</span><span className="text-white">₹50.00 / month</span></div>
          <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.22)' }}><span className="block text-dim">Sharing</span><span className="text-white">You control when it is listed</span></div>
        </div>
        <button onClick={registerHomeSlot} disabled={registering}
          className="w-full py-3 rounded-xl text-sm font-semibold text-white disabled:opacity-50"
          style={{ background: VIOLET, boxShadow: '0 4px 20px rgba(168,85,247,0.3)' }}>
          {registering ? 'Registering your home slot…' : 'Register home slot'}
        </button>
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
        <h3 className="text-sm font-semibold text-white mb-1">Availability signal</h3>
        <p className="text-[11px] text-dim mb-4">
          Tell Pragma when your home slot is free. The availability model combines this signal with observed demand and current bookings before presenting it to drivers.
        </p>

        {listing ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: '#00c785', boxShadow: '0 0 6px #00c785' }} />
              <span className="text-[12px] font-medium text-white">Availability signal active</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
                <p className="text-[10px] uppercase tracking-wider text-dim">Price / hour</p>
                <p className="text-sm font-semibold text-white">System managed</p>
              </div>
              <div className="rounded-xl p-3" style={{ background: 'rgba(0,0,0,0.25)' }}>
                <p className="text-[10px] uppercase tracking-wider text-dim">Available</p>
                <p className="text-sm font-semibold text-white">Modelled continuously</p>
              </div>
            </div>
            <button onClick={stopSharing} disabled={toggling}
              className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-50"
              style={{ background: '#ff4757' }}>
              {toggling ? 'Updating…' : 'Mark my slot unavailable'}
            </button>
          </div>
        ) : (
          <button onClick={signalAvailability} disabled={toggling}
            className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-50"
            style={{ background: VIOLET, boxShadow: '0 4px 20px rgba(168,85,247,0.3)' }}>
            {toggling ? 'Sending availability signal…' : 'My slot is available'}
          </button>
        )}
      </div>
    </div>
  )
}
