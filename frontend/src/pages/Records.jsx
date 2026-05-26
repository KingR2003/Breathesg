import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, CheckCircle, XCircle, Flag, ChevronUp, ChevronDown } from 'lucide-react'
import { recordAPI } from '../lib/api'
import useToastStore from '../store/useToastStore'
import ReviewModal from '../components/ReviewModal'

const SCOPE_BADGE = {
  SCOPE_1: 'badge-scope-1',
  SCOPE_2: 'badge-scope-2',
  SCOPE_3: 'badge-scope-3',
}

const STATUS_BADGE = {
  PENDING: 'badge-pending',
  FLAGGED: 'badge-flagged',
  APPROVED: 'badge-approved',
  REJECTED: 'badge-rejected',
}

const SCOPE_LABELS = {
  SCOPE_1: 'Scope 1', SCOPE_2: 'Scope 2', SCOPE_3: 'Scope 3'
}

function fmtCO2(kg) {
  const t = parseFloat(kg || 0) / 1000
  if (t >= 1) return `${t.toFixed(2)} t`
  return `${parseFloat(kg || 0).toFixed(1)} kg`
}

export default function Records() {
  const navigate = useNavigate()
  const { add: toast } = useToastStore()
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [selected, setSelected] = useState([])
  const [modal, setModal] = useState(null) // { type: 'approve'|'reject'|'flag', ids: [] }

  const [filters, setFilters] = useState({
    scope: '',
    source_type: '',
    review_status: '',
    search: '',
  })
  const [ordering, setOrdering] = useState('-source_period_end')

  const fetchRecords = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        page,
        ordering,
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
      }
      const res = await recordAPI.list(params)
      setRecords(res.data.results || res.data)
      setTotal(res.data.count || (res.data.results || res.data).length)
    } catch (e) {
      toast('Failed to load records', 'error')
    } finally {
      setLoading(false)
    }
  }, [filters, page, ordering])

  useEffect(() => { fetchRecords() }, [fetchRecords])

  const toggleSelect = (id) => {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])
  }

  const toggleAll = () => {
    setSelected(s => s.length === records.length ? [] : records.map(r => r.id))
  }

  const handleSort = (field) => {
    setOrdering(o => o === field ? `-${field}` : field)
  }

  const SortIcon = ({ field }) => {
    if (ordering === field) return <ChevronUp size={12} style={{ display: 'inline' }} />
    if (ordering === `-${field}`) return <ChevronDown size={12} style={{ display: 'inline' }} />
    return null
  }

  const handleBulkAction = async (action, notes) => {
    const ids = selected.length > 0 ? selected : modal?.ids || []
    if (!ids.length) return
    try {
      await recordAPI.bulkAction(ids, action, notes)
      toast(`${ids.length} record(s) ${action}d`, 'success')
      setSelected([])
      setModal(null)
      fetchRecords()
    } catch (e) {
      toast('Action failed', 'error')
    }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Emission Records</h1>
          <p className="page-subtitle">{total.toLocaleString()} records · Review and sign off before audit</p>
        </div>
        {selected.length > 0 && (
          <div className="flex gap-2">
            <button
              id="bulk-approve-btn"
              className="btn btn-approve btn-sm"
              onClick={() => setModal({ type: 'approve', ids: selected })}
            >
              <CheckCircle size={14} /> Approve {selected.length}
            </button>
            <button
              id="bulk-reject-btn"
              className="btn btn-secondary btn-sm"
              onClick={() => handleBulkAction('reject', '')}
            >
              <XCircle size={14} /> Reject {selected.length}
            </button>
            <button
              id="bulk-flag-btn"
              className="btn btn-danger btn-sm"
              onClick={() => setModal({ type: 'flag', ids: selected })}
            >
              <Flag size={14} /> Flag {selected.length}
            </button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="filters-bar">
        <div className="search-input-wrap">
          <Search className="search-icon" />
          <input
            id="record-search"
            className="form-control"
            placeholder="Search records…"
            value={filters.search}
            onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
          />
        </div>
        <select
          id="filter-scope"
          className="form-control"
          value={filters.scope}
          onChange={e => setFilters(f => ({ ...f, scope: e.target.value }))}
        >
          <option value="">All Scopes</option>
          <option value="SCOPE_1">Scope 1</option>
          <option value="SCOPE_2">Scope 2</option>
          <option value="SCOPE_3">Scope 3</option>
        </select>
        <select
          id="filter-source"
          className="form-control"
          value={filters.source_type}
          onChange={e => setFilters(f => ({ ...f, source_type: e.target.value }))}
        >
          <option value="">All Sources</option>
          <option value="SAP_FUEL">SAP — Fuel</option>
          <option value="UTILITY_ELEC">Utility — Electricity</option>
          <option value="TRAVEL_FLIGHT">Travel — Flight</option>
          <option value="TRAVEL_HOTEL">Travel — Hotel</option>
          <option value="TRAVEL_GROUND">Travel — Ground</option>
        </select>
        <select
          id="filter-status"
          className="form-control"
          value={filters.review_status}
          onChange={e => setFilters(f => ({ ...f, review_status: e.target.value }))}
        >
          <option value="">All Statuses</option>
          <option value="PENDING">Pending</option>
          <option value="FLAGGED">Flagged</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
        </select>
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => setFilters({ scope: '', source_type: '', review_status: '', search: '' })}
        >
          Clear
        </button>
      </div>

      {/* Table */}
      <div className="table-container">
        {loading ? (
          <div className="loading-dots">
            <div className="loading-dot" /><div className="loading-dot" /><div className="loading-dot" />
          </div>
        ) : records.length === 0 ? (
          <div className="empty-state">
            <h3>No records found</h3>
            <p>Try adjusting your filters or uploading some data.</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input
                    id="select-all"
                    type="checkbox"
                    checked={selected.length === records.length && records.length > 0}
                    onChange={toggleAll}
                  />
                </th>
                <th onClick={() => handleSort('scope')}>
                  Scope <SortIcon field="scope" />
                </th>
                <th onClick={() => handleSort('source_type')}>
                  Source <SortIcon field="source_type" />
                </th>
                <th onClick={() => handleSort('source_period_end')}>
                  Period <SortIcon field="source_period_end" />
                </th>
                <th>Description</th>
                <th onClick={() => handleSort('activity_value')}>
                  Activity <SortIcon field="activity_value" />
                </th>
                <th onClick={() => handleSort('co2e_kg')}>
                  CO₂e <SortIcon field="co2e_kg" />
                </th>
                <th onClick={() => handleSort('review_status')}>
                  Status <SortIcon field="review_status" />
                </th>
                <th style={{ width: 110 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec) => (
                <tr
                  key={rec.id}
                  className={selected.includes(rec.id) ? 'selected' : ''}
                  onClick={() => navigate(`/records/${rec.id}`)}
                >
                  <td onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.includes(rec.id)}
                      onChange={() => toggleSelect(rec.id)}
                      id={`sel-${rec.id}`}
                    />
                  </td>
                  <td>
                    <span className={`badge ${SCOPE_BADGE[rec.scope] || ''}`}>
                      {SCOPE_LABELS[rec.scope] || rec.scope}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    {rec.source_type_display}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
                    {rec.source_period_start || '—'}
                  </td>
                  <td>
                    <span className="truncate" title={rec.activity_description}>
                      {rec.activity_description || rec.source_id || '—'}
                    </span>
                    {rec.flag_reasons?.length > 0 && (
                      <span title={rec.flag_reasons.join('; ')} style={{ marginLeft: 6, color: 'var(--status-flagged)' }}>
                        <Flag size={12} style={{ display: 'inline' }} />
                      </span>
                    )}
                  </td>
                  <td className="num">
                    {parseFloat(rec.activity_value || 0).toLocaleString('en-US', { maximumFractionDigits: 2 })}
                    <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>{rec.activity_unit}</span>
                  </td>
                  <td className="num" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                    {fmtCO2(rec.co2e_kg)}
                  </td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[rec.review_status] || ''}`}>
                      {rec.review_status_display || rec.review_status}
                    </span>
                    {rec.is_locked && (
                      <span style={{ marginLeft: 4, fontSize: '0.75rem', color: 'var(--text-muted)' }}>🔒</span>
                    )}
                  </td>
                  <td onClick={e => e.stopPropagation()}>
                    <div className="flex gap-2">
                      {!rec.is_locked && rec.review_status !== 'APPROVED' && (
                        <button
                          id={`approve-${rec.id}`}
                          className="btn btn-approve btn-sm btn-icon"
                          title="Approve"
                          onClick={() => setModal({ type: 'approve', ids: [rec.id] })}
                        >
                          <CheckCircle size={13} />
                        </button>
                      )}
                      {!rec.is_locked && rec.review_status !== 'REJECTED' && (
                        <button
                          id={`reject-${rec.id}`}
                          className="btn btn-danger btn-sm btn-icon"
                          title="Reject"
                          onClick={async () => {
                            await recordAPI.reject(rec.id, {})
                            toast('Record rejected', 'success')
                            fetchRecords()
                          }}
                        >
                          <XCircle size={13} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {total > pageSize && (
        <div className="pagination">
          <span className="pagination-info">
            Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total.toLocaleString()}
          </span>
          <div className="pagination-controls">
            <button
              id="prev-page"
              className="btn btn-secondary btn-sm"
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
            >
              Previous
            </button>
            <span style={{ padding: '4px 12px', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
              {page} / {totalPages}
            </span>
            <button
              id="next-page"
              className="btn btn-secondary btn-sm"
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Review modal */}
      {modal && (
        <ReviewModal
          type={modal.type}
          count={modal.ids?.length || 0}
          onConfirm={(notes, lock) => {
            if (modal.type === 'approve') handleBulkAction('approve', notes)
            else if (modal.type === 'flag') handleBulkAction('flag', notes)
            else handleBulkAction('reject', notes)
          }}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  )
}
