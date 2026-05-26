import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle, XCircle, Flag, Lock, Edit2, Check, X, Shield } from 'lucide-react'
import { recordAPI } from '../lib/api'
import useToastStore from '../store/useToastStore'

function StatusBadge({ status }) {
  const map = {
    APPROVED: 'badge-approved',
    REJECTED: 'badge-rejected',
    FLAGGED:  'badge-flagged',
    PENDING:  'badge-pending',
  }
  const labels = {
    APPROVED: 'Approved', REJECTED: 'Rejected', FLAGGED: 'Flagged', PENDING: 'Pending'
  }
  return <span className={`badge ${map[status] || 'badge-pending'}`}>{labels[status] || status}</span>
}

export default function RecordDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { add: toast } = useToastStore()

  const [record, setRecord] = useState(null)
  const [auditLogs, setAuditLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionNotes, setActionNotes] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState('')
  const [editReason, setEditReason] = useState('')

  const load = async () => {
    try {
      setLoading(true)
      const [recRes, auditRes] = await Promise.all([recordAPI.get(id), recordAPI.audit(id)])
      setRecord(recRes.data)
      setAuditLogs(auditRes.data)
      setEditValue(recRes.data.activity_value)
    } catch {
      toast('Failed to load record', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const handleAction = async (action) => {
    try {
      if (action === 'approve') await recordAPI.approve(id, { notes: actionNotes })
      else if (action === 'reject') await recordAPI.reject(id, { notes: actionNotes })
      else await recordAPI.flag(id, { notes: actionNotes })
      toast(`Record ${action}d`, 'success')
      setActionNotes('')
      load()
    } catch (err) {
      toast(err.response?.data?.error || `Failed to ${action}`, 'error')
    }
  }

  const handleUpdate = async () => {
    if (!editReason.trim()) { toast('Please provide an edit reason', 'error'); return }
    try {
      await recordAPI.update(id, { activity_value: parseFloat(editValue), edit_reason: editReason })
      toast('Value updated', 'success')
      setIsEditing(false)
      setEditReason('')
      load()
    } catch (err) {
      toast(err.response?.data?.error || 'Update failed', 'error')
    }
  }

  if (loading) return (
    <div className="loading-dots"><div className="loading-dot" /><div className="loading-dot" /><div className="loading-dot" /></div>
  )
  if (!record) return (
    <div className="empty-state">
      <h3>Record not found</h3>
      <button className="btn btn-secondary mt-4" onClick={() => navigate('/records')}>Back to Records</button>
    </div>
  )

  return (
    <div className="fade-in">
      {/* Back link */}
      <button
        onClick={() => navigate('/records')}
        className="btn btn-secondary btn-sm mb-6"
        style={{ display: 'inline-flex' }}
      >
        <ArrowLeft size={14} /> Back to Records
      </button>

      {/* Header card */}
      <div className="card mb-6">
        <div className="flex items-center justify-between">
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: 4 }}>
              ID: {record.id}
            </div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
              {record.activity_description || record.source_id || 'Emission Record'}
            </h1>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Tenant: <span style={{ color: 'var(--brand-400)' }}>{record.tenant_name || record.tenant}</span>
              &nbsp;·&nbsp;Source: {record.source_type}
            </div>
          </div>
          <div className="flex gap-3" style={{ alignItems: 'center' }}>
            <StatusBadge status={record.review_status} />
            {record.is_locked && (
              <span className="badge badge-rejected"><Lock size={11} /> Locked</span>
            )}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 'var(--space-6)' }}>
        {/* Left column */}
        <div>
          {/* Emission computation */}
          <div className="card mb-6">
            <div className="card-title">Emission Computation</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-6)', alignItems: 'start' }}>

              {/* Activity value */}
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Activity Value</div>
                {isEditing ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <input
                      type="number"
                      value={editValue}
                      onChange={e => setEditValue(e.target.value)}
                      className="form-control"
                      style={{ fontSize: '0.875rem' }}
                    />
                    <input
                      type="text"
                      placeholder="Reason for change…"
                      value={editReason}
                      onChange={e => setEditReason(e.target.value)}
                      className="form-control"
                      style={{ fontSize: '0.8125rem' }}
                    />
                    <div className="flex gap-2">
                      <button onClick={handleUpdate} className="btn btn-approve btn-sm btn-icon"><Check size={14} /></button>
                      <button onClick={() => { setIsEditing(false); setEditValue(record.activity_value) }} className="btn btn-secondary btn-sm btn-icon"><X size={14} /></button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <span style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      {parseFloat(record.activity_value).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                    </span>
                    <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginLeft: 6 }}>{record.activity_unit}</span>
                    {!record.is_locked && (
                      <button
                        onClick={() => setIsEditing(true)}
                        className="btn btn-secondary btn-sm btn-icon"
                        style={{ marginLeft: 8, verticalAlign: 'middle' }}
                      >
                        <Edit2 size={12} />
                      </button>
                    )}
                    {record.is_edited && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--status-pending)', marginTop: 4 }}>
                        Edited · orig: {parseFloat(record.original_activity_value).toLocaleString()} {record.activity_unit}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Emission factor */}
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Emission Factor</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {parseFloat(record.emission_factor).toLocaleString(undefined, { maximumFractionDigits: 6 })}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                  {record.emission_factor_source}<br />({record.emission_factor_year})
                </div>
              </div>

              {/* CO2e result */}
              <div style={{
                background: 'rgba(16,185,129,0.07)',
                border: '1px solid rgba(16,185,129,0.2)',
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-4)',
              }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--brand-400)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6, fontWeight: 600 }}>Total Emissions</div>
                <div style={{ fontSize: '1.75rem', fontWeight: 900, color: 'var(--brand-300)' }}>
                  {parseFloat(record.co2e_kg).toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--brand-400)', fontWeight: 600 }}>kg CO₂e</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                  ≈ {(parseFloat(record.co2e_kg) / 1000).toFixed(3)} metric tons
                </div>
              </div>
            </div>
          </div>

          {/* Attributes grid */}
          <div className="card mb-6">
            <div className="card-title">Record Attributes</div>
            <div className="detail-grid">
              {[
                ['GHG Scope', `Scope ${record.scope?.replace('SCOPE_', '')}`],
                ['GHG Category', `${record.ghg_category} (${record.ghg_category_code})`],
                ['Source Type', record.source_type],
                ['Source Reference', record.source_id || '—'],
                ['Period Start', record.source_period_start || '—'],
                ['Period End', record.source_period_end || '—'],
                ['Country', record.country_code || '—'],
                ['Region', record.region || '—'],
                ['Facility / Cost Center', record.facility_id || '—'],
                ['Created At', new Date(record.created_at).toLocaleString()],
              ].map(([label, value]) => (
                <div key={label} className="detail-field">
                  <div className="detail-field-label">{label}</div>
                  <div className="detail-field-value">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Raw data */}
          {record.raw_record_data && (
            <div className="card">
              <div className="card-title">Raw Ingested Data</div>
              <pre style={{
                background: 'rgba(0,0,0,0.4)',
                borderRadius: 'var(--radius-md)',
                padding: 'var(--space-4)',
                overflowX: 'auto',
                fontSize: '0.75rem',
                color: 'var(--brand-300)',
                maxHeight: 300,
                overflowY: 'auto',
              }}>
                {JSON.stringify(record.raw_record_data, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          {/* Analyst actions */}
          {!record.is_locked && (
            <div className="card">
              <div className="card-title">
                <Shield size={14} style={{ display: 'inline', marginRight: 6, color: 'var(--brand-400)' }} />
                Analyst Action
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 'var(--space-3)' }}>
                Approve, flag, or reject this record. Approved records are locked for audit.
              </p>
              <textarea
                value={actionNotes}
                onChange={e => setActionNotes(e.target.value)}
                placeholder="Review notes (optional)…"
                className="form-control mb-4"
                style={{ height: 80, resize: 'vertical' }}
              />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-2)' }}>
                <button
                  id={`approve-${record.id}`}
                  onClick={() => handleAction('approve')}
                  className="btn btn-approve btn-sm"
                  style={{ flexDirection: 'column', height: 64, gap: 4, justifyContent: 'center' }}
                >
                  <CheckCircle size={16} />
                  <span style={{ fontSize: '0.75rem' }}>Approve</span>
                </button>
                <button
                  id={`flag-${record.id}`}
                  onClick={() => handleAction('flag')}
                  className="btn btn-secondary btn-sm"
                  style={{ flexDirection: 'column', height: 64, gap: 4, justifyContent: 'center', color: 'var(--status-pending)', borderColor: 'rgba(245,158,11,0.3)' }}
                >
                  <Flag size={16} />
                  <span style={{ fontSize: '0.75rem' }}>Flag</span>
                </button>
                <button
                  id={`reject-${record.id}`}
                  onClick={() => handleAction('reject')}
                  className="btn btn-danger btn-sm"
                  style={{ flexDirection: 'column', height: 64, gap: 4, justifyContent: 'center' }}
                >
                  <XCircle size={16} />
                  <span style={{ fontSize: '0.75rem' }}>Reject</span>
                </button>
              </div>
            </div>
          )}

          {/* Audit log */}
          <div className="card">
            <div className="card-title">Audit History</div>
            {auditLogs.length === 0 ? (
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>No audit events yet.</p>
            ) : (
              <div className="audit-timeline">
                {auditLogs.map(log => (
                  <div key={log.id} className="audit-event">
                    <div className="audit-dot" />
                    <div className="audit-event-action">{log.action}</div>
                    <div className="audit-event-meta">
                      {log.actor_name || 'System'} · {new Date(log.timestamp).toLocaleString()}
                    </div>
                    {log.before_state && (
                      <pre style={{
                        background: 'rgba(0,0,0,0.3)',
                        borderRadius: 4,
                        padding: '6px 8px',
                        fontSize: '0.7rem',
                        color: 'var(--text-muted)',
                        marginTop: 6,
                        maxHeight: 80,
                        overflowY: 'auto',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all',
                      }}>
                        {JSON.stringify({ before: log.before_state, after: log.after_state }, null, 1)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
