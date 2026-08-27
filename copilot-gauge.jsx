import { css } from "uebersicht";
import { WIDGET_DIR } from "./local.config";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
// WIDGET_DIR comes from local.config.js (gitignored — see
// local.config.example.js). Copy that file to local.config.js and set the
// absolute path of this widget folder before the widget will work.
// ---------------------------------------------------------------------------
const PYTHON = `${WIDGET_DIR}/../.venv/bin/python`;

// The Python script is executed by Übersicht on every refresh.
export const command = `'${PYTHON}' '${WIDGET_DIR}/copilot_usage.py'`;

// Refresh every 5 minutes (milliseconds).  Keep this value in sync with
// refresh_frequency_ms in config.json — config.json is read by the Python
// script only; this value controls Übersicht's refresh cadence.
export const refreshFrequency = 5 * 60 * 1000;

// ---------------------------------------------------------------------------
// Widget positioning — override these to suit your desktop layout.
// ---------------------------------------------------------------------------
export const className = css`
  top: 40px;
  right: 40px;
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
`;

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const card = css`
  width: 180px;
  padding: 18px 18px 16px;
  border-radius: 18px;
  background: rgba(20, 20, 22, 0.72);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  color: white;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
`;

const gaugeSvg = css`
  width: 150px;
  height: 120px;
  margin: -8px auto 0;
  display: block;
`;

const titleStyle = css`
  font-size: 12px;
  opacity: 0.65;
  margin-top: 6px;
  letter-spacing: 0.03em;
`;

const amountStyle = css`
  font-size: 13px;
  margin-top: 4px;
  opacity: 0.9;
`;

const errorStyle = css`
  font-size: 12px;
  opacity: 0.7;
  padding: 8px 0;
`;

const paceBarTrack = css`
  width: 88%;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.12);
  margin: 10px auto 0;
  overflow: hidden;
`;

const paceBarFill = (color, width) => css`
  width: ${width}%;
  height: 100%;
  background: ${color};
  border-radius: 2px;
`;

const paceVerdictStyle = (color) => css`
  font-size: 11px;
  font-weight: 600;
  margin-top: 6px;
  color: ${color};
  line-height: 1.3;
`;

const paceProjectedStyle = css`
  font-size: 11px;
  opacity: 0.65;
  margin-top: 2px;
  line-height: 1.3;
`;

// ---------------------------------------------------------------------------
// Pace helpers
// ---------------------------------------------------------------------------
const PACE_COLORS = {
  over: "#ff453a",
  under: "#30d158",
  on_track: "#ffd60a",
};

const PACE_VERDICTS = {
  over: "Pacing above budget",
  under: "Pacing below budget",
  on_track: "On track",
};

function renderPace(pace) {
  if (!pace) return null;
  const color = PACE_COLORS[pace.status] || "#ffffff";
  const verdict = PACE_VERDICTS[pace.status] || "";
  // Bar fill = today's actual daily average usage relative to the daily budget.
  const barWidth = Math.max(0, Math.min(100, (pace.daily_budget > 0
    ? pace.actual_daily_average / pace.daily_budget
    : 0) * 100));

  return (
    <div>
      <div className={paceBarTrack}>
        <div className={paceBarFill(color, barWidth)} />
      </div>
      <div className={paceVerdictStyle(color)}>{verdict}</div>
      <div className={paceProjectedStyle}>Projected {pace.projected_total}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gauge geometry
// ---------------------------------------------------------------------------
const GAUGE_MIN_ANGLE = 180;
const GAUGE_MAX_ANGLE = 0;

function clampPercentage(percentage) {
  return Math.max(0, Math.min(100, Number(percentage) || 0));
}

function polarToCartesian(cx, cy, radius, angleDegrees) {
  const angleRadians = (angleDegrees * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(angleRadians),
    y: cy - radius * Math.sin(angleRadians),
  };
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------
export const render = ({ output, error }) => {
  // Handle execution errors reported by Übersicht.
  if (error) {
    return (
      <div className={card}>
        <div className={errorStyle}>⚠ Widget error</div>
        <div className={titleStyle}>GitHub AI Credits</div>
      </div>
    );
  }

  if (!output || !output.trim()) {
    return (
      <div className={card}>
        <div className={errorStyle}>Loading…</div>
        <div className={titleStyle}>GitHub AI Credits</div>
      </div>
    );
  }

  let data;
  try {
    data = JSON.parse(output);
  } catch {
    return (
      <div className={card}>
        <div className={errorStyle}>Invalid data</div>
        <div className={titleStyle}>GitHub AI Credits</div>
      </div>
    );
  }

  // If the Python script printed an error JSON object.
  if (data.error) {
    return (
      <div className={card}>
        <div className={errorStyle}>⚠ {data.error}</div>
        <div className={titleStyle}>GitHub AI Credits</div>
      </div>
    );
  }

  const percentage = clampPercentage(data.percentage);
  const needleAngle = GAUGE_MIN_ANGLE - (percentage / 100) * (GAUGE_MIN_ANGLE - GAUGE_MAX_ANGLE);
  const needleTip = polarToCartesian(75, 78, 46, needleAngle);

  return (
    <div className={card}>
      <svg className={gaugeSvg} viewBox="0 0 150 120">
        <path
          d="M 25 78 A 50 50 0 0 1 125 78"
          fill="none"
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="14"
          strokeLinecap="butt"
        />

        <path
          d="M 25 78 A 50 50 0 0 1 125 78"
          pathLength="180"
          fill="none"
          stroke="#30d158"
          strokeWidth="14"
          strokeDasharray="60 120"
          strokeDashoffset="0"
        />
        <path
          d="M 25 78 A 50 50 0 0 1 125 78"
          pathLength="180"
          fill="none"
          stroke="#ffd60a"
          strokeWidth="14"
          strokeDasharray="60 120"
          strokeDashoffset="-60"
        />
        <path
          d="M 25 78 A 50 50 0 0 1 125 78"
          pathLength="180"
          fill="none"
          stroke="#ff453a"
          strokeWidth="14"
          strokeDasharray="60 120"
          strokeDashoffset="-120"
        />

        <line
          x1="75"
          y1="78"
          x2={needleTip.x}
          y2={needleTip.y}
          stroke="white"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx="75" cy="78" r="6" fill="white" />
        <circle cx="75" cy="78" r="2.5" fill="rgba(20,20,22,0.9)" />

        {/* Percentage label */}
        <text
          x="75"
          y="112"
          textAnchor="middle"
          fill="white"
          fontSize="18"
          fontWeight="600"
        >
          {percentage}%
        </text>
      </svg>

      <div className={amountStyle}>
        {data.used} / {data.limit}
      </div>

      {renderPace(data.pace)}

      <div className={titleStyle}>GitHub AI Credits</div>
    </div>
  );
};
