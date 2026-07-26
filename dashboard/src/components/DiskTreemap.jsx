import React from 'react';
import './DiskTreemap.css';

const DiskTreemap = ({ categories, onSelectCategory, selectedCategories }) => {
  if (!categories) return null;

  const validCategories = Object.entries(categories).filter(
    ([key, data]) => key !== 'disk_info' && key !== 'drive' && data.total_size > 0
  );

  const grandTotalSize = validCategories.reduce((acc, [_, data]) => acc + (data.total_size || 0), 0);

  if (grandTotalSize === 0) {
    return (
      <div className="treemap-empty">
        <p>No hay datos suficientes para generar el gráfico Treemap.</p>
      </div>
    );
  }

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const getCategoryColor = (riskLevel) => {
    switch (riskLevel?.toLowerCase()) {
      case 'low':
        return 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
      case 'medium':
        return 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
      case 'high':
        return 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
      default:
        return 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)';
    }
  };

  return (
    <div className="treemap-container">
      <div className="treemap-header">
        <h4>🗺️ Mapa de Distribución de Espacio (Treemap Interactivo)</h4>
        <span className="treemap-hint">Haz clic en un bloque para seleccionar la categoría</span>
      </div>

      <div className="treemap-grid">
        {validCategories.map(([catKey, catData]) => {
          const percent = ((catData.total_size / grandTotalSize) * 100).toFixed(1);
          const isSelected = selectedCategories?.includes(catKey);

          return (
            <div
              key={catKey}
              className={`treemap-tile ${isSelected ? 'selected' : ''}`}
              style={{
                flexGrow: Math.max(catData.total_size, 1000),
                background: getCategoryColor(catData.risk_level)
              }}
              onClick={() => onSelectCategory && onSelectCategory(catKey)}
              title={`${catData.display_name}: ${formatBytes(catData.total_size)} (${percent}%)`}
            >
              <div className="tile-content">
                <span className="tile-title">{catData.display_name}</span>
                <span className="tile-size">{formatBytes(catData.total_size)} ({percent}%)</span>
                <span className="tile-files">{catData.file_count} archivos</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default DiskTreemap;
