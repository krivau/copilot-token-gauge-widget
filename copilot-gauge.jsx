import { css } from "uebersicht";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
// ⚠  REQUIRED: Update WIDGET_DIR to the absolute path of this widget folder
//    before the widget will work.  Example:
//      /Users/alice/Library/Application Support/Übersicht/widgets/copilot-token-gauge-widget
// ---------------------------------------------------------------------------
const WIDGET_DIR = "/Users/YOUR_USER/Library/Application Support/Übersicht/widgets/copilot-token-gauge-widget";

// The Python script is executed by Übersicht on every refresh.
export const command = `python3 '${WIDGET_DIR}/copilot_usage.py'`;

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
  width: 160px;
  padding: 18px;
  border-radius: 18px;
  background: rgba(20, 20, 22, 0.72);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  color: white;
  text-align: center;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
`;

const gaugeSvg = css`
  width: 120px;
  height: 120px;
  margin: auto;
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

// ---------------------------------------------------------------------------
// Gauge colour — green → amber → red based on usage percentage
// ---------------------------------------------------------------------------
function gaugeColour(percentage) {
  if (percentage >= 90) return "#ff453a"; // red
  if (percentage >= 70) return "#ff9f0a"; // amber
  return "#30d158";                       // green
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

  const radius = 48;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - data.percentage / 100);
  const colour = gaugeColour(data.percentage);

  return (
    <div className={card}>
      <svg className={gaugeSvg} viewBox="0 0 120 120">
        {/* Background track */}
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.12)"
          strokeWidth="9"
        />

        {/* Progress arc */}
        <circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          stroke={colour}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          transform="rotate(-90 60 60)"
        />

        {/* Percentage label */}
        <text
          x="60"
          y="57"
          textAnchor="middle"
          fill="white"
          fontSize="22"
          fontWeight="600"
        >
          {data.percentage}%
        </text>

        {/* Sub-label */}
        <text
          x="60"
          y="76"
          textAnchor="middle"
          fill="rgba(255,255,255,0.6)"
          fontSize="9"
          letterSpacing="1"
        >
          USED
        </text>
      </svg>

      <div className={amountStyle}>
        {data.used} / {data.limit}
      </div>

      <div className={titleStyle}>GitHub AI Credits</div>
    </div>
  );
};
