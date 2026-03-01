import React, { useState, useEffect } from 'react';

const AmbulanceHistory = ({ isOpen, onClose, refreshTrigger }) => {
  const [history, setHistory] = useState([]);
  const [sortBy, setSortBy] = useState('newest');

  // Load history from localStorage on mount AND when refreshTrigger changes
  useEffect(() => {
    if (isOpen) {
      loadHistory();
    }
  }, [isOpen, refreshTrigger]); // Added refreshTrigger dependency

  const loadHistory = () => {
    try {
      const savedHistory = localStorage.getItem('ambulance_history');
      if (savedHistory) {
        const parsed = JSON.parse(savedHistory);
        setHistory(parsed);
      }
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  };

  const clearHistory = () => {
    if (window.confirm('Are you sure you want to clear all history?')) {
      localStorage.removeItem('ambulance_history');
      setHistory([]);
    }
  };

  const deleteEntry = (id) => {
    const updated = history.filter(item => item.id !== id);
    localStorage.setItem('ambulance_history', JSON.stringify(updated));
    setHistory(updated);
  };

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };

  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const getSortedHistory = () => {
    const sorted = [...history];
    switch (sortBy) {
      case 'oldest':
        return sorted.sort((a, b) => a.startTime - b.startTime);
      case 'fastest':
        return sorted.sort((a, b) => a.travelTime - b.travelTime);
      case 'slowest':
        return sorted.sort((a, b) => b.travelTime - a.travelTime);
      case 'newest':
      default:
        return sorted.sort((a, b) => b.startTime - a.startTime);
    }
  };

  const getAverageTime = () => {
    if (history.length === 0) return 0;
    const total = history.reduce((sum, item) => sum + item.travelTime, 0);
    return (total / history.length).toFixed(1);
  };

  const getGreenCorridorCount = () => {
    return history.filter(item => item.mode === 'green_corridor').length;
  };

  if (!isOpen) return null;

  const sortedHistory = getSortedHistory();

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.5)',
      zIndex: 10000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      animation: 'fadeIn 0.2s ease-in'
    }}>
      <div style={{
        background: 'white',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '900px',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
        animation: 'slideUp 0.3s ease-out'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 25px',
          borderBottom: '2px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          borderRadius: '12px 12px 0 0'
        }}>
          <h2 style={{ margin: 0, fontSize: '22px', fontWeight: '700' }}>
            🚑 Ambulance History
          </h2>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255,255,255,0.2)',
              border: 'none',
              color: 'white',
              fontSize: '24px',
              cursor: 'pointer',
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.3s'
            }}
            onMouseEnter={(e) => e.target.style.background = 'rgba(255,255,255,0.3)'}
            onMouseLeave={(e) => e.target.style.background = 'rgba(255,255,255,0.2)'}
          >
            ×
          </button>
        </div>

        {/* Statistics Bar */}
        <div style={{
          padding: '15px 25px',
          background: '#f8f9fa',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          gap: '20px',
          flexWrap: 'wrap'
        }}>
          <div style={{ flex: 1, minWidth: '150px' }}>
            <div style={{ fontSize: '11px', color: '#6b7280', fontWeight: '600' }}>TOTAL TRIPS</div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: '#667eea' }}>{history.length}</div>
          </div>
          <div style={{ flex: 1, minWidth: '150px' }}>
            <div style={{ fontSize: '11px', color: '#6b7280', fontWeight: '600' }}>AVG TIME</div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: '#10b981' }}>
              {history.length > 0 ? formatDuration(getAverageTime()) : '0m 0s'}
            </div>
          </div>
          <div style={{ flex: 1, minWidth: '150px' }}>
            <div style={{ fontSize: '11px', color: '#6b7280', fontWeight: '600' }}>GREEN CORRIDOR</div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: '#10b981' }}>{getGreenCorridorCount()}</div>
          </div>
          <div style={{ flex: 1, minWidth: '150px' }}>
            <div style={{ fontSize: '11px', color: '#6b7280', fontWeight: '600' }}>NORMAL MODE</div>
            <div style={{ fontSize: '24px', fontWeight: '700', color: '#ef4444' }}>{history.length - getGreenCorridorCount()}</div>
          </div>
        </div>

        {/* Controls */}
        <div style={{
          padding: '15px 25px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '15px',
          flexWrap: 'wrap'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '13px', fontWeight: '600', color: '#4a5568' }}>Sort by:</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              style={{
                padding: '6px 12px',
                border: '2px solid #e2e8f0',
                borderRadius: '6px',
                fontSize: '13px',
                cursor: 'pointer',
                background: 'white'
              }}
            >
              <option value="newest">Newest First</option>
              <option value="oldest">Oldest First</option>
              <option value="fastest">Fastest First</option>
              <option value="slowest">Slowest First</option>
            </select>
          </div>
          <button
            onClick={clearHistory}
            disabled={history.length === 0}
            style={{
              padding: '8px 16px',
              background: history.length === 0 ? '#9ca3af' : '#ef4444',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: '600',
              cursor: history.length === 0 ? 'not-allowed' : 'pointer',
              transition: 'all 0.3s',
              opacity: history.length === 0 ? 0.5 : 1
            }}
            onMouseEnter={(e) => {
              if (history.length > 0) e.target.style.background = '#dc2626';
            }}
            onMouseLeave={(e) => {
              if (history.length > 0) e.target.style.background = '#ef4444';
            }}
          >
            🗑️ Clear All
          </button>
        </div>

        {/* History List */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 25px'
        }}>
          {sortedHistory.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '60px 20px',
              color: '#9ca3af'
            }}>
              <div style={{ fontSize: '48px', marginBottom: '15px' }}>📋</div>
              <div style={{ fontSize: '16px', fontWeight: '600' }}>No History Yet</div>
              <div style={{ fontSize: '13px', marginTop: '8px' }}>
                Spawn an ambulance to start tracking history
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {sortedHistory.map((entry, index) => (
                <div
                  key={entry.id}
                  style={{
                    background: 'white',
                    border: '2px solid #e2e8f0',
                    borderRadius: '10px',
                    padding: '16px',
                    borderLeft: `5px solid ${entry.mode === 'green_corridor' ? '#10b981' : '#ef4444'}`,
                    transition: 'all 0.3s',
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                    e.currentTarget.style.transform = 'translateX(5px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.boxShadow = 'none';
                    e.currentTarget.style.transform = 'translateX(0)';
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                        <span style={{ fontSize: '20px' }}>
                          {entry.mode === 'green_corridor' ? '🟢' : '🔴'}
                        </span>
                        <span style={{ fontSize: '13px', fontWeight: '700', color: '#2d3748' }}>
                          Trip #{sortedHistory.length - index}
                        </span>
                        <span style={{
                          fontSize: '10px',
                          padding: '3px 8px',
                          borderRadius: '12px',
                          background: entry.mode === 'green_corridor' ? '#d1fae5' : '#fee2e2',
                          color: entry.mode === 'green_corridor' ? '#065f46' : '#991b1b',
                          fontWeight: '600',
                          textTransform: 'uppercase'
                        }}>
                          {entry.mode === 'green_corridor' ? 'Green Corridor' : 'Normal'}
                        </span>
                      </div>

                      <div style={{ fontSize: '13px', color: '#4a5568', marginBottom: '10px' }}>
                        <div style={{ marginBottom: '4px' }}>
                          <strong>Route:</strong> {entry.source} → {entry.destination}
                        </div>
                        <div style={{ marginBottom: '4px' }}>
                          <strong>Started:</strong> {formatDate(entry.startTime)}
                        </div>
                        <div>
                          <strong>Duration:</strong> <span style={{ 
                            color: entry.mode === 'green_corridor' ? '#10b981' : '#ef4444',
                            fontWeight: '700'
                          }}>
                            {formatDuration(entry.travelTime)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteEntry(entry.id);
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#ef4444',
                        fontSize: '20px',
                        cursor: 'pointer',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        transition: 'all 0.3s'
                      }}
                      onMouseEnter={(e) => e.target.style.background = '#fee2e2'}
                      onMouseLeave={(e) => e.target.style.background = 'transparent'}
                      title="Delete entry"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AmbulanceHistory;
