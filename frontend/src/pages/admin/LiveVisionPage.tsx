import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchCvOccupancy,
  fetchCvStatus,
  getMjpegUrl,
  saveCalibration,
  suggestGrid,
  type OccupancyResponse,
  type SlotDef,
  type StatusResponse,
} from '../../api/cvClient'

type ConnState = 'idle' | 'connected' | 'error'

export function LiveVisionPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [conn, setConn] = useState<ConnState>('idle')
  const [lots, setLots] = useState<string[]>([])
  const [lotId, setLotId] = useState<string>('')
  const [occ, setOcc] = useState<OccupancyResponse | null>(null)
  const [mjpegUrl, setMjpegUrl] = useState<string>(getMjpegUrl())

  // Calibration state
  const [calibrating, setCalibrating] = useState(false)
  const [rows, setRows] = useState(4)
  const [cols, setCols] = useState(6)
  const [calSlots, setCalSlots] = useState<SlotDef[]>([])
  const [calMsg, setCalMsg] = useState<string>('')
  const [saving, setSaving] = useState(false)

  const pollRef = useRef<number | null>(null)

  const refreshStatus = useCallback(async () => {
    try {
      const s = await fetchCvStatus()
      setStatus(s)
      setConn('connected')
      if (s.lots.length && !lotId) setLotId(s.lots[0])
      setLots(s.lots)
    } catch {
      setConn('error')
    }
  }, [lotId])

  useEffect(() => {
    refreshStatus()
  }, [refreshStatus])

  // Poll occupancy for the selected lot.
  useEffect(() => {
    if (!lotId) return
    const tick = async () => {
      try {
        const o = await fetchCvOccupancy(lotId)
        setOcc(o)
        setConn('connected')
      } catch {
        setConn('error')
      }
    }
    tick()
    pollRef.current = window.setInterval(tick, 2000)
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [lotId])

  const occupiedCount = occ ? occ.occupancy.filter((o) => o.occupied).length : 0
  const totalSlots = occ ? occ.occupancy.length : 0

  const handleGenerate = async () => {
    setCalMsg('')
    try {
      const [w, h] = occ?.frame_size ?? status?.camera.frame_size ?? [1280, 720]
      const slots = await suggestGrid(w, h, rows, cols)
      setCalSlots(slots)
      setCalibrating(true)
    } catch (e) {
      setCalMsg(`Grid suggest failed: ${(e as Error).message}`)
    }
  }

  const handleSave = async () => {
    if (!lotId) {
      setCalMsg('Select a lot first.')
      return
    }
    setSaving(true)
    setCalMsg('')
    try {
      await saveCalibration(lotId, calSlots)
      setCalMsg(`Saved ${calSlots.length} slot ROIs for ${lotId}.`)
      setCalibrating(false)
      // Reload MJPEG so the new polygons draw.
      setMjpegUrl(getMjpegUrl())
      await refreshStatus()
    } catch (e) {
      setCalMsg(`Save failed: ${(e as Error).message}`)
    } finally {
      setSaving(false)
    }
  }

  const connColor = conn === 'connected' ? '#60d4a0' : conn === 'error' ? '#ff6b6b' : '#f0c040'

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono tracking-[4px] uppercase"
              style={{ color: '#40d4f0' }}>01 · IoT / Observe</span>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse-glow"
              style={{ backgroundColor: connColor }} />
          </div>
          <h1 className="text-2xl font-heading font-bold text-white tracking-tight">Live Vision</h1>
          <p className="text-xs text-dim mt-1 max-w-xl">
            Real YOLOv8 vehicle detection from the local CV agent. Occupancy is fused onto
            per-lot slot ROIs and pushed to the backend as the sensor signal.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="px-3 py-2 rounded-lg text-xs font-mono"
            style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
            Agent: <span style={{ color: connColor }}>{conn === 'connected' ? 'ONLINE' : conn === 'error' ? 'OFFLINE' : '…'}</span>
          </div>
          {lotId && (
            <div className="px-3 py-2 rounded-lg text-xs font-mono"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              {totalSlots ? `${occupiedCount}/${totalSlots} occupied` : 'no slots'}
            </div>
          )}
        </div>
      </div>

      {conn === 'error' && (
        <div className="mb-6 px-4 py-3 rounded-lg text-sm"
          style={{ background: 'rgba(255,107,107,0.08)', border: '1px solid rgba(255,107,107,0.25)', color: '#ff9b9b' }}>
          CV agent unreachable at <code className="font-mono">http://localhost:8777</code>. Start it with
          {' '}<code className="font-mono">python -m src.cv.cli</code> on the machine with the camera.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live feed */}
        <div className="lg:col-span-2">
          <div className="rounded-2xl overflow-hidden"
            style={{ background: '#04040a', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.05]">
              <span className="text-xs font-mono uppercase tracking-wider text-dim">Camera Feed</span>
              <span className="text-[10px] font-mono"
                style={{ color: status?.camera.available ? '#60d4a0' : '#f0c040' }}>
                {status?.camera.available ? 'REAL CAMERA' : 'SYNTHETIC FALLBACK'}
              </span>
            </div>
            <div className="relative aspect-video bg-black flex items-center justify-center">
              <img
                src={mjpegUrl}
                alt="Live CV feed"
                className="w-full h-full object-contain"
                onError={() => setConn('error')}
              />
            </div>
          </div>

          {/* Occupancy grid */}
          <div className="mt-6 rounded-2xl p-5"
            style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-heading font-semibold text-white">Per-Slot Occupancy</h2>
              <select
                value={lotId}
                onChange={(e) => setLotId(e.target.value)}
                className="bg-[#0c0c20] text-white text-xs rounded-lg px-3 py-1.5 border border-white/10 focus:outline-none"
              >
                {lots.length === 0 && <option value="">no lots calibrated</option>}
                {lots.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </div>
            {occ && occ.occupancy.length > 0 ? (
              <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-10 gap-2">
                {occ.occupancy.map((s) => (
                  <div
                    key={s.slot_id}
                    title={`Slot ${s.slot_id} — ${s.occupied ? 'occupied' : 'free'}`}
                    className="aspect-square rounded-md flex items-center justify-center text-[10px] font-mono"
                    style={{
                      background: s.occupied ? 'rgba(112,112,224,0.18)' : 'rgba(96,212,160,0.14)',
                      border: `1px solid ${s.occupied ? 'rgba(112,112,224,0.5)' : 'rgba(96,212,160,0.4)'}`,
                      color: s.occupied ? '#a9a9ff' : '#60d4a0',
                    }}
                  >
                    {s.slot_id}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-dim">
                No slot ROIs calibrated for this lot. Use the calibration panel on the right to
                generate and save a slot grid.
              </p>
            )}
          </div>
        </div>

        {/* Calibration panel */}
        <div className="rounded-2xl p-5 h-fit"
          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <h2 className="text-sm font-heading font-semibold text-white mb-1">Calibration</h2>
          <p className="text-[11px] text-dim mb-4 leading-relaxed">
            UI-assisted slot layout — no auto-discovery. Generate a starting grid, then save the
            ROIs so detection maps onto real physical slots.
          </p>

          <label className="block text-[11px] text-dim mb-1">Lot ID</label>
          <input
            value={lotId}
            onChange={(e) => setLotId(e.target.value)}
            placeholder="e.g. A1"
            className="w-full bg-[#0c0c20] text-white text-xs rounded-lg px-3 py-2 border border-white/10 focus:outline-none mb-3"
          />

          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="block text-[11px] text-dim mb-1">Rows</label>
              <input
                type="number" min={1} max={20} value={rows}
                onChange={(e) => setRows(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full bg-[#0c0c20] text-white text-xs rounded-lg px-3 py-2 border border-white/10 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-[11px] text-dim mb-1">Cols</label>
              <input
                type="number" min={1} max={20} value={cols}
                onChange={(e) => setCols(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full bg-[#0c0c20] text-white text-xs rounded-lg px-3 py-2 border border-white/10 focus:outline-none"
              />
            </div>
          </div>

          <button
            onClick={handleGenerate}
            className="w-full text-xs font-semibold text-white py-2 rounded-lg mb-2 transition-colors"
            style={{ background: 'rgba(64,212,240,0.15)', border: '1px solid rgba(64,212,240,0.3)' }}
          >
            Generate Grid
          </button>
          <button
            onClick={handleSave}
            disabled={saving || calSlots.length === 0}
            className="w-full text-xs font-semibold py-2 rounded-lg transition-colors disabled:opacity-40"
            style={{ background: '#f0c040', color: '#04040a' }}
          >
            {saving ? 'Saving…' : `Save ${calSlots.length || ''} Slots`.trim()}
          </button>

          {calibrating && calSlots.length > 0 && (
            <div className="mt-3 max-h-40 overflow-auto rounded-lg p-2 text-[10px] font-mono text-dim"
              style={{ background: '#04040a' }}>
              {calSlots.length} slot(s) ready — adjust corners on the agent if needed, then Save.
            </div>
          )}

          {calMsg && (
            <p className="mt-3 text-[11px] font-mono"
              style={{ color: calMsg.startsWith('Saved') ? '#60d4a0' : '#ff9b9b' }}>
              {calMsg}
            </p>
          )}

          <div className="mt-4 pt-4 border-t border-white/[0.05]">
            <p className="text-[10px] text-dim leading-relaxed">
              Camera: {status?.camera.available ? 'real device' : 'synthetic fallback (no camera / torch)'}.
              Pushes use the per-sensor <code className="font-mono">X-Sensor-Key</code> bound to this lot.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
