import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, RefreshCw, FileText } from 'lucide-react'
import { ingestAPI } from '../lib/api'
import useToastStore from '../store/useToastStore'

const SOURCE_TYPES = [
  {
    id: 'sap',
    label: 'SAP Data',
    sub: 'Material documents (Scope 1 / Scope 3)',
    hint: 'Supports German ALV headers: Posting Date, Material Group, Quantity, Unit of Measure. German decimal format (e.g. 1.234,56) is handled automatically.'
  },
  {
    id: 'utility',
    label: 'Utility Bill',
    sub: 'Electricity portal CSVs (Scope 2)',
    hint: 'Green Button CSV layout: Account Number, Meter ID, Billing Period Start, Billing Period End, Consumption kWh. Billing periods that straddle months are split proportionally.'
  },
  {
    id: 'travel',
    label: 'Travel Expense',
    sub: 'Concur travel logs (Scope 3, Cat 6)',
    hint: 'Concur Expense layout: Expense Type, Origin Airport IATA, Destination Airport IATA, Cabin Class, Hotel Check-In, Hotel Check-Out, Ground Distance Miles.'
  }
]

export default function UploadPage() {
  const navigate = useNavigate()
  const { add: toast } = useToastStore()
  const [selectedFile, setSelectedFile] = useState(null)
  const [sourceType, setSourceType] = useState('sap')
  const [isUploading, setIsUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(e.type === 'dragenter' || e.type === 'dragover')
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const f = e.dataTransfer.files?.[0]
    if (f) setSelectedFile(f)
  }

  const handleFileChange = (e) => {
    const f = e.target.files?.[0]
    if (f) setSelectedFile(f)
  }

  const handleUpload = async (e) => {
    e.preventDefault()
    if (!selectedFile) { toast('Please select a file', 'error'); return }

    try {
      setIsUploading(true)
      let response
      if (sourceType === 'sap')          response = await ingestAPI.uploadSAP(selectedFile)
      else if (sourceType === 'utility') response = await ingestAPI.uploadUtility(selectedFile)
      else                               response = await ingestAPI.uploadTravel(selectedFile)

      toast(`Batch created — ${response.data.record_count ?? response.data.row_count ?? 0} records processed`, 'success')
      navigate('/batches')
    } catch (err) {
      toast(err.response?.data?.error || err.response?.data?.detail || 'Upload failed', 'error')
    } finally {
      setIsUploading(false)
    }
  }

  const activeSource = SOURCE_TYPES.find(s => s.id === sourceType)

  return (
    <div className="fade-in" style={{ maxWidth: 760, margin: '0 auto' }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">Ingest Emissions Data</h1>
          <p className="page-subtitle">Upload raw enterprise files to normalize, scope-classify and queue for analyst review.</p>
        </div>
      </div>

      <form onSubmit={handleUpload}>
        {/* Source type selector */}
        <div className="card mb-6">
          <div className="card-title">Select Data Source Type</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 'var(--space-3)' }}>
            {SOURCE_TYPES.map(src => (
              <button
                key={src.id}
                type="button"
                onClick={() => setSourceType(src.id)}
                style={{
                  background: sourceType === src.id ? 'rgba(16,185,129,0.1)' : 'var(--bg-elevated)',
                  border: `1px solid ${sourceType === src.id ? 'rgba(16,185,129,0.4)' : 'var(--border-default)'}`,
                  borderRadius: 'var(--radius-md)',
                  padding: 'var(--space-4)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all var(--transition-fast)',
                  color: sourceType === src.id ? 'var(--brand-400)' : 'var(--text-secondary)',
                }}
              >
                <FileText size={20} style={{ marginBottom: 'var(--space-2)', display: 'block' }} />
                <div style={{ fontWeight: 600, fontSize: '0.875rem', color: sourceType === src.id ? 'var(--brand-300)' : 'var(--text-primary)' }}>{src.label}</div>
                <div style={{ fontSize: '0.75rem', marginTop: 4, color: 'var(--text-muted)' }}>{src.sub}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Drop zone */}
        <div
          className={`upload-zone mb-6 ${dragActive ? 'drag-over' : ''}`}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input').click()}
          style={{ position: 'relative', cursor: 'pointer' }}
        >
          <input
            id="file-input"
            type="file"
            accept=".csv,.txt,.xlsx"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          <div className="upload-zone-icon">
            <Upload size={40} />
          </div>
          {selectedFile ? (
            <div>
              <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-primary)', marginBottom: 6 }}>
                {selectedFile.name}
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                {(selectedFile.size / 1024).toFixed(1)} KB · Click to choose a different file
              </div>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setSelectedFile(null) }}
                style={{ marginTop: 8, fontSize: '0.75rem', color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer' }}
              >
                Remove
              </button>
            </div>
          ) : (
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.9375rem', color: 'var(--text-primary)', marginBottom: 6 }}>
                Drag &amp; drop your file here, or click to browse
              </div>
              <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                Supports CSV, TXT, XLSX files
              </div>
            </div>
          )}
        </div>

        {/* Hint box */}
        {activeSource && (
          <div className="card mb-6" style={{ padding: 'var(--space-4)' }}>
            <div className="card-title" style={{ marginBottom: 'var(--space-2)' }}>Expected Column Format — {activeSource.label}</div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{activeSource.hint}</p>
          </div>
        )}

        {/* Submit */}
        <button
          id="upload-submit-btn"
          type="submit"
          disabled={isUploading || !selectedFile}
          className="btn btn-primary w-full"
          style={{ padding: 'var(--space-3)', justifyContent: 'center' }}
        >
          {isUploading
            ? <><RefreshCw size={16} className="animate-spin" /> Processing &amp; Normalizing…</>
            : <><Upload size={16} /> Upload &amp; Process File</>
          }
        </button>
      </form>
    </div>
  )
}
