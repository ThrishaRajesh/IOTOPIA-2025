/**
 * risk_predictor.cjs
 * Calculates disaster risk using 6 factors and publishes a polygon
 * (convex hull + centroid) when threshold exceeded.
 */

const mqtt = require("mqtt");
const BROKER = "mqtt://localhost:1883";
const client = mqtt.connect(BROKER);

const RISK_TOPIC = "risk/zone";
let buffer = [];

client.on("connect", () => {
  console.log("Risk predictor connected");
  client.subscribe("sensors/data");
});

client.on("message", (_, msg) => {
  const d = JSON.parse(msg);

  // Simulated extra factors
  const tremor = Math.random() * 0.6;
  const co2    = 350 + Math.random() * 800;
  const smoke  = Math.random() * 300;
  const temp   = 20 + Math.random() * 40;
  const water  = d.water || 0;
  const rain   = d.rainfall || 0;

  const norm = (x, min, max) => Math.min(1, Math.max(0, (x - min) / (max - min)));

  const risk =
    0.25 * norm(rain, 0, 200) +
    0.20 * norm(water, 0, 5) +
    0.20 * norm(tremor, 0, 0.6) +
    0.15 * norm(co2, 400, 2000) +
    0.10 * norm(smoke, 0, 300) +
    0.10 * norm(temp, 20, 60);

  if (risk > 0.2) {
    buffer.push([d.lat, d.lon, {
      total: risk, rainfall: rain, water, tremor, co2, smoke, temp
    }]);
    if (buffer.length > 100) buffer.shift();
  }
});

setInterval(() => {
  if (!buffer.length) return;
  const points = buffer.map(p => [p[0], p[1]]);
  if (points.length < 3) return; // Need at least 3 for polygon

  const hull = convexHull(points);
  const latest = buffer[buffer.length - 1][2];
  const centroid = hull.reduce(
    (a, b) => [a[0] + b[0], a[1] + b[1]],
    [0, 0]
  ).map(x => x / hull.length);

  client.publish(RISK_TOPIC, JSON.stringify({
    hull,
    centroid,
    ts: Date.now(),
    riskDetail: latest
  }));
}, 10000);

function convexHull(points) {
  points.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) =>
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [], upper = [];
  for (const p of points) {
    while (lower.length >= 2 && cross(lower.at(-2), lower.at(-1), p) <= 0) lower.pop();
    lower.push(p);
  }
  for (let i = points.length - 1; i >= 0; i--) {
    const p = points[i];
    while (upper.length >= 2 && cross(upper.at(-2), upper.at(-1), p) <= 0) upper.pop();
    upper.push(p);
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}
