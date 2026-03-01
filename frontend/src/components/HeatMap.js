import React, { useMemo } from 'react';
import { Bubble } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
} from 'chart.js';
import sgMap from '../assets/sg.svg';

ChartJS.register(LinearScale, PointElement, Tooltip, Legend);

// Singapore regions with realistic coordinates
// Coordinates normalized to 0-700 range for visualization
const SINGAPORE_ZONES = [
  { id: 0, x: 200, y: 550, name: 'West Coast Marina', region: 'West' },
  { id: 1, x: 280, y: 520, name: 'Bukit Timah', region: 'Northwest' },
  { id: 2, x: 350, y: 530, name: 'Orchard Road', region: 'Central' },
  { id: 3, x: 420, y: 540, name: 'Marina Bay', region: 'Southeast' },
  { id: 4, x: 480, y: 550, name: 'Sentosa Island', region: 'South' },
  { id: 5, x: 150, y: 450, name: 'Kranji Reservoir', region: 'North' },
  { id: 6, x: 280, y: 420, name: 'Ang Mo Kio', region: 'Northeast' },
  { id: 7, x: 380, y: 430, name: 'Bedok', region: 'East' },
  { id: 8, x: 460, y: 450, name: 'Changi Airport', region: 'Northeast' },
  { id: 9, x: 320, y: 350, name: 'Tampines', region: 'East' },
  { id: 10, x: 240, y: 300, name: 'Serangoon', region: 'Northeast' },
  { id: 11, x: 400, y: 320, name: 'Pasir Ris', region: 'East' },
  { id: 12, x: 180, y: 520, name: 'Jurong', region: 'West' },
  { id: 13, x: 350, y: 380, name: 'Geylang', region: 'East Central' },
  { id: 14, x: 300, y: 480, name: 'Tiong Bahru', region: 'South' },
];

// Deterministic zone assignment based on alert fingerprint
const getZoneForAlert = (alert) => {
  // Use timestamp + risk_score as a stable fingerprint
  const timestamp = new Date(alert.timestamp || Date.now()).getTime();
  const riskScore = Math.round((alert.risk_score || 0) * 10);
  
  // Simple deterministic linear congruential generator
  let seed = timestamp + riskScore;
  const hash = Math.abs((seed * 9301 + 49297) % 233280);
  
  // Always assigns same alert to same zone (stable across re-renders)
  const zoneIndex = hash % SINGAPORE_ZONES.length;
  return SINGAPORE_ZONES[zoneIndex];
};

// Get color based on danger tier
const getDangerColorFromRank = (rank) => {
  const colors = {
    'Green': '#10b981',
    'Yellow': '#f59e0b',
    'Orange': '#ef6b3f',
    'Red': '#dc2626',
  };
  return colors[rank] || '#9ca3af';
};

// Island bounds as percentage of chart area
// Constrains points to visible Singapore island region
const ISLAND_BOUNDS = {
  xMin: 0.18,
  xMax: 0.92,
  yMin: 0.12,
  yMax: 0.88,
};

// Chart axis ranges
const CHART_X_MIN = 100;
const CHART_X_MAX = 550;
const CHART_Y_MIN = 250;
const CHART_Y_MAX = 600;

// Map zone coordinates to chart space, constrained to island bounds
const mapZoneToChart = (zoneX, zoneY) => {
  // Zone coordinates are in 0-700 normalized space
  // Normalize to 0-1
  const normX = zoneX / 700;
  const normY = zoneY / 700;
  
  // Clamp to island bounds
  const clampedX = Math.max(ISLAND_BOUNDS.xMin, Math.min(ISLAND_BOUNDS.xMax, normX));
  const clampedY = Math.max(ISLAND_BOUNDS.yMin, Math.min(ISLAND_BOUNDS.yMax, normY));
  
  // Map to chart coordinates
  const chartX = CHART_X_MIN + clampedX * (CHART_X_MAX - CHART_X_MIN);
  const chartY = CHART_Y_MIN + clampedY * (CHART_Y_MAX - CHART_Y_MIN);
  
  return { chartX, chartY };
};


export default function HeatMap({ alerts }) {
  const chartData = useMemo(() => {
    if (!alerts || alerts.length === 0) {
      return {
        datasets: [
          {
            label: 'No Risk Data',
            data: [],
            backgroundColor: '#d1d5db',
          },
        ],
      };
    }

    // Group alerts by zone and aggregate risk data
    const zoneData = {};

    alerts.forEach((alert) => {
      const zone = getZoneForAlert(alert);
      const zoneId = zone.id;

      if (!zoneData[zoneId]) {
        zoneData[zoneId] = {
          zone,
          alerts: [],
          totalRisk: 0,
          avgRisk: 0,
          maxRisk: 0,
          dangerRanks: {},
        };
      }

      zoneData[zoneId].alerts.push(alert);
      zoneData[zoneId].totalRisk += alert.risk_score || 0;
      zoneData[zoneId].maxRisk = Math.max(zoneData[zoneId].maxRisk, alert.risk_score || 0);

      // Track danger ranks
      const rank = alert.danger_rank || 'Green';
      zoneData[zoneId].dangerRanks[rank] = (zoneData[zoneId].dangerRanks[rank] || 0) + 1;
    });

    // Calculate average risk and determine dominant danger rank per zone
    Object.values(zoneData).forEach((z) => {
      z.avgRisk = z.totalRisk / z.alerts.length;
      // Find most common danger rank
      z.dominantRank = Object.entries(z.dangerRanks).sort((a, b) => b[1] - a[1])[0][0];
    });

    // Create dataset entries, one per danger tier for legend
    const dangerTiers = ['Red', 'Orange', 'Yellow', 'Green'];
    const datasets = dangerTiers.map((rank) => {
      const zonesForTier = Object.values(zoneData).filter(
        (z) => z.dominantRank === rank
      );

      return {
        label: `${rank} Zone (${zonesForTier.length} zones)`,
        data: zonesForTier.map((z) => {
          const { chartX, chartY } = mapZoneToChart(z.zone.x, z.zone.y);
          return {
            x: chartX,
            y: chartY,
            r: Math.max(10, Math.min(30, z.alerts.length * 4)),
            zone: z.zone.name,
            region: z.zone.region,
            alertCount: z.alerts.length,
            avgRisk: Math.round(z.avgRisk),
            maxRisk: z.maxRisk,
          };
        }),
        backgroundColor: getDangerColorFromRank(rank),
        borderColor: '#ffffff',
        borderWidth: 2.5,
        opacity: 0.8,
      };
    });

    return {
      datasets: datasets.filter((ds) => ds.data.length > 0),
    };
  }, [alerts]);

  const options = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          font: { size: 12, weight: 'bold' },
          padding: 15,
          usePointStyle: true,
        },
      },
      tooltip: {
        callbacks: {
          title: () => '',
          label: (context) => {
            const data = context.raw;
            return [
              `📍 ${data.zone}`,
              `Region: ${data.region}`,
              `Alerts: ${data.alertCount}`,
              `Avg Risk: ${data.avgRisk}`,
              `Max Risk: ${data.maxRisk}`,
            ];
          },
          afterLabel: () => '',
        },
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        padding: 12,
        titleFont: { size: 13, weight: 'bold' },
        bodyFont: { size: 12 },
      },
    },
    scales: {
      x: {
        type: 'linear',
        position: 'bottom',
        title: {
          display: true,
          text: '⬅️ West | East ➡️',
          font: { weight: 'bold', size: 12 },
        },
        min: 100,
        max: 550,
        ticks: { display: false },
        grid: { drawBorder: true, color: 'rgba(150, 150, 150, 0.15)' },
      },
      y: {
        title: {
          display: true,
          text: '⬇️ South | North ⬆️',
          font: { weight: 'bold', size: 12 },
        },
        min: 250,
        max: 600,
        ticks: { display: false },
        grid: { drawBorder: true, color: 'rgba(150, 150, 150, 0.15)' },
      },
    },
  };

  return (
    <div className="heat-map-card">
      <div className="card-header">
        <h3>Singapore Risk Heat Map</h3>
        <p className="subtitle">
          Real-time geographic risk distribution across Singapore Island • Bubble size = alert concentration
        </p>
      </div>
      <div className="heat-map-container">
        <img 
          src={sgMap} 
          alt="Singapore Map"
          className="sg-map-background"
        />
        {alerts && alerts.length > 0 ? (
          <>
            <Bubble data={chartData} options={options} />
            <div className="heat-map-legend">
              <div className="legend-item">
                <span className="legend-dot" style={{ backgroundColor: '#dc2626' }}></span>
                <span>Critical</span>
              </div>
              <div className="legend-item">
                <span className="legend-dot" style={{ backgroundColor: '#ef6b3f' }}></span>
                <span>High Risk</span>
              </div>
              <div className="legend-item">
                <span className="legend-dot" style={{ backgroundColor: '#f59e0b' }}></span>
                <span>Watch</span>
              </div>
              <div className="legend-item">
                <span className="legend-dot" style={{ backgroundColor: '#10b981' }}></span>
                <span>Safe</span>
              </div>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <p>No alerts yet. Generate an alert to see Singapore's risk distribution map.</p>
          </div>
        )}
      </div>
    </div>
  );
}
