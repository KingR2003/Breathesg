import React, { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'
import { TrendingUp, AlertTriangle, CheckCircle, Clock, Database } from 'lucide-react'
import { summaryAPI } from '../lib/api'

const SCOPE_COLORS = {
  SCOPE_1: '#f97316',
  SCOPE_2: '#3b82f6',
  SCOPE_3: '#8b5cf6',
}

const SOURCE_COLORS = {
  SAP_FUEL: '#f97316',
  UTILITY_ELEC: '#3b82f6',
  TRAVEL_FLIGHT: '#8b5cf6',
  TRAVEL_HOTEL: '#a78bfa',
  TRAVEL_GROUND: '#c4b5fd',
  SAP_PROCUREMENT: '#fb923c',
}

function Tile({ label, value, unit, accent, icon: Icon }) {
  return (
    <div className="tile" style={{ '--tile-accent': accent }}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {unit && <div className="tile-unit">{unit}</div>}
      {Icon && (
        <div className="tile-icon">
          <Icon size={48} color={accent} />
        </div>
      )}
    </div>
  )
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: 'var(--bg-elevated)', border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)', padding: '10px 14px', fontSize: '0.8125rem'
    }}>
      <div style={{ color: 'var(--text-primary)', fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>
          {p.name}: {Number(p.value).toFixed(2)} t CO₂e
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    summaryAPI.get().then(r => {
      setSummary(r.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="loading-dots">
      <div className="loading-dot" />
      <div className="loading-dot" />
      <div className="loading-dot" />
    </div>
  )

  if (!summary) return (
    <div className="empty-state">
      <h3>No data yet</h3>
      <p>Upload some data files to get started.</p>
    </div>
  )

  const scopeData = (summary.by_scope || []).map(s => ({
    name: s.scope === 'SCOPE_1' ? 'Scope 1' : s.scope === 'SCOPE_2' ? 'Scope 2' : 'Scope 3',
    value: parseFloat(s.co2e_kg || 0) / 1000,
    fill: SCOPE_COLORS[s.scope] || '#6b7280',
  }))

  const sourceData = (summary.by_source_type || []).map(s => ({
    name: s.source_label?.replace(' — ', '\n') || s.source_type,
    co2e: parseFloat(s.co2e_kg || 0) / 1000,
    fill: SOURCE_COLORS[s.source_type] || '#6b7280',
  }))

  const totalTonnes = parseFloat(summary.total_co2e_tonnes || 0)

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Overview of emissions data across all sources</p>
        </div>
      </div>

      {/* Summary tiles */}
      <div className="tiles-grid">
        <Tile
          label="Total Emissions"
          value={totalTonnes.toLocaleString('en-US', { maximumFractionDigits: 1 })}
          unit="metric tonnes CO₂e"
          accent="var(--brand-500)"
          icon={TrendingUp}
        />
        <Tile
          label="Pending Review"
          value={summary.pending_count?.toLocaleString()}
          unit="records awaiting review"
          accent="var(--status-pending)"
          icon={Clock}
        />
        <Tile
          label="Flagged"
          value={summary.flagged_count?.toLocaleString()}
          unit="records need attention"
          accent="var(--status-flagged)"
          icon={AlertTriangle}
        />
        <Tile
          label="Approved"
          value={summary.approved_count?.toLocaleString()}
          unit="records signed off"
          accent="var(--status-approved)"
          icon={CheckCircle}
        />
        <Tile
          label="Total Records"
          value={summary.total_records?.toLocaleString()}
          unit="emission records ingested"
          accent="var(--scope-2)"
          icon={Database}
        />
      </div>

      {/* Charts */}
      <div className="charts-row">
        {/* Scope breakdown pie */}
        <div className="card">
          <div className="card-title">Emissions by Scope</div>
          {scopeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={scopeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={70}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  nameKey="name"
                >
                  {scopeData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Legend
                  iconType="circle"
                  formatter={(value) => (
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>
                      {value}
                    </span>
                  )}
                />
                <Tooltip
                  formatter={(v) => [`${v.toFixed(2)} tCO₂e`, '']}
                  contentStyle={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.8125rem',
                    color: 'var(--text-primary)',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
              <p>No scope data yet</p>
            </div>
          )}
        </div>

        {/* Source type bar chart */}
        <div className="card">
          <div className="card-title">Emissions by Source</div>
          {sourceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={sourceData} margin={{ top: 0, right: 0, bottom: 40, left: 0 }}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                  angle={-30}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis
                  tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                  tickFormatter={v => `${v}t`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="co2e" name="CO₂e" radius={[4, 4, 0, 0]}>
                  {sourceData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
              <p>No source data yet</p>
            </div>
          )}
        </div>
      </div>

      {/* Review status breakdown */}
      <div className="card">
        <div className="card-title">Review Status Breakdown</div>
        <div style={{ display: 'flex', gap: 'var(--space-6)', flexWrap: 'wrap' }}>
          {[
            { label: 'Pending', count: summary.pending_count, cls: 'badge-pending' },
            { label: 'Flagged', count: summary.flagged_count, cls: 'badge-flagged' },
            { label: 'Approved', count: summary.approved_count, cls: 'badge-approved' },
            { label: 'Rejected', count: summary.rejected_count, cls: 'badge-rejected' },
          ].map(({ label, count, cls }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <span className={`badge ${cls}`}>{label}</span>
              <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {count?.toLocaleString() || 0}
              </span>
            </div>
          ))}
        </div>

        {/* Progress bar */}
        {summary.total_records > 0 && (
          <div style={{ marginTop: 'var(--space-4)' }}>
            <div style={{ height: 8, borderRadius: 4, overflow: 'hidden', background: 'var(--bg-elevated)', display: 'flex' }}>
              <div style={{ width: `${(summary.approved_count / summary.total_records) * 100}%`, background: 'var(--status-approved)' }} />
              <div style={{ width: `${(summary.pending_count / summary.total_records) * 100}%`, background: 'var(--status-pending)', opacity: 0.7 }} />
              <div style={{ width: `${(summary.flagged_count / summary.total_records) * 100}%`, background: 'var(--status-flagged)' }} />
              <div style={{ width: `${(summary.rejected_count / summary.total_records) * 100}%`, background: 'var(--status-rejected)' }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              <span>{Math.round((summary.approved_count / summary.total_records) * 100)}% approved</span>
              <span>{summary.total_records} total records</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
