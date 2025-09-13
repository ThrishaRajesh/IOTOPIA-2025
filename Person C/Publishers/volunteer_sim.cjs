/**
 * volunteer_sim.js
 * Simulates 4 volunteers walking randomly around Bengaluru.
 * Publishes GPS + speed every 2 seconds.
 */
const mqtt = require("mqtt");

const BROKER_URL = "mqtt://localhost:1883";
const TOPIC = "volunteers/gps";
const PUBLISH_MS = 2000;
const MOVE_RANGE = 0.0007;            // ~70m jitter per step
const BASE = { lat: 12.9716, lon: 77.5946 };

const volunteers = [
  { id: 1, lat: BASE.lat, lon: BASE.lon },
  { id: 2, lat: BASE.lat + 0.001, lon: BASE.lon + 0.001 },
  { id: 3, lat: BASE.lat - 0.001, lon: BASE.lon - 0.001 },
  { id: 4, lat: BASE.lat + 0.002, lon: BASE.lon - 0.001 }
];

const client = mqtt.connect(BROKER_URL);
client.on("connect", () =>
  console.log(`Volunteer simulator connected → ${BROKER_URL}`)
);
client.on("error", err => { console.error(err); process.exit(1); });

const randomStep = v => v + (Math.random() - 0.5) * MOVE_RANGE;

function publishPositions() {
  volunteers.forEach(v => {
    const prev = { lat: v.lat, lon: v.lon, t: v.t || Date.now() };
    v.lat = randomStep(v.lat);
    v.lon = randomStep(v.lon);
    v.t = Date.now();

    // speed (m/s)
    const dist = haversine(prev.lat, prev.lon, v.lat, v.lon);
    const speed = dist / ((v.t - prev.t) / 1000);

    client.publish(
      TOPIC,
      JSON.stringify({
        id: v.id,
        lat: +v.lat.toFixed(6),
        lon: +v.lon.toFixed(6),
        speed: +speed.toFixed(2),
        timestamp: v.t
      })
    );
  });
  console.log("Volunteer positions broadcast");
}

function haversine(aLat, aLon, bLat, bLon) {
  const R = 6371e3;
  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(bLat - aLat);
  const dLon = toRad(bLon - aLon);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

setInterval(publishPositions, PUBLISH_MS);
console.log("Volunteer simulation started…");
