import React, { useEffect, useState } from 'react'
import { RefreshCw, CheckCircle, AlertCircle, Database } from 'lucide-react'
import { batchAPI } from '../lib/api'
import useToastStore from '../store/useToastStore'

function StatusBadge({ status }) {
  if (status === 'DONE')
    return <span className="badge badge-approved"><CheckCircle size={11} /> Done</span>
  if (status === 'FAILED')
    return <span className="badge badge-flagged"><AlertCircle size={11} /> Failed</span>
  if (status === 'PROCESSING')
    return <span className="badge badge-pending"><RefreshCw size={11} /> Processing</span>
  return <span className="badge badge-rejected">Pending</span>
}

export default function Batches() {
  const { add: toast } = useToastStore()
  const [batches, setBatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const fetchBatches = async () => {
    try {
      setRefreshing(true)
      const res = await batchAPI.list()
      setBatches(Array.isArray(res.data) ? res.data : res.data.results || [])
    } catch {
      toast('Failed to load batches', 'error')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { fetchBatches() }, [])

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">Ingestion Batches</h1>
          <p className="page-subtitle">Track uploaded files, processing status, row counts, and parse errors.</p>
        </div>
        <button
          onClick={fetchBatches}
          disabled={refreshing}
          className="btn btn-secondary btn-sm"
        >
          <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="loading-dots">
          <div className="loading-dot" /><div className="loading-dot" /><div className="loading-dot" />
        </div>
      ) : batches.length === 0 ? (
        <div className="empty-state">
          <Database size={40} style={{ margin: '0 auto var(--space-4)', color: 'var(--text-muted)', display: 'block' }} />
          <h3>No batches yet</h3>
          <p>Upload a file from the <strong>Upload Data</strong> page to get started.</p>
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Batch ID</th>
                <th>Source Type</th>
                <th>Filename</th>
                <th>Uploaded By</th>
                <th>Status</th>
                <th className="num">Rows</th>
                <th className="num">Errors</th>
                <th>Uploaded At</th>
              </tr>
            </thead>
            <tbody>
              {batches.map(batch => (
                <tr key={batch.id} style={{ cursor: 'default' }}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    {batch.id.slice(0, 8)}…
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.875rem' }}>
                      {batch.source_type_display || batch.source_type}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-secondary)' }}>{batch.filename}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>{batch.uploaded_by_name || '—'}</td>
                  <td><StatusBadge status={batch.status} /></td>
                  <td className="num">{batch.row_count ?? '—'}</td>
                  <td className="num">
                    {batch.error_count > 0
                      ? <span style={{ color: 'var(--status-flagged)', fontWeight: 600 }}>{batch.error_count}</span>
                      : <span style={{ color: 'var(--text-muted)' }}>0</span>
                    }
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                    {new Date(batch.uploaded_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
