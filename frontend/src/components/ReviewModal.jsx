import React, { useState } from 'react'
import { X } from 'lucide-react'

export default function ReviewModal({ type, count, onConfirm, onClose }) {
  const [notes, setNotes] = useState('')

  const actionLabel = type === 'approve' ? 'Approve' : type === 'flag' ? 'Flag' : 'Reject'
  const actionClass = type === 'approve' ? 'btn-approve' : type === 'flag' ? 'btn-secondary' : 'btn-danger'

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="modal-title" style={{ margin: 0 }}>
            {actionLabel} {count} {count === 1 ? 'Record' : 'Records'}
          </h2>
          <button onClick={onClose} className="btn btn-secondary btn-sm btn-icon">
            <X size={14} />
          </button>
        </div>

        <div className="form-group mb-6">
          <label className="form-label">Review Notes / Reason</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Add context for this review action…"
            className="form-control"
            style={{ height: 100, resize: 'vertical' }}
          />
        </div>

        <div className="flex gap-3 justify-end">
          <button onClick={onClose} className="btn btn-secondary">Cancel</button>
          <button
            onClick={() => onConfirm(notes)}
            className={`btn ${actionClass}`}
          >
            Confirm {actionLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
