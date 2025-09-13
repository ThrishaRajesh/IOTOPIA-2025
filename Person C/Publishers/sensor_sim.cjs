/**
 * sensor_sim.js
 * Simulated IoT grid broadcasting rainfall + water-level sensors.
 */
const mqtt = require("mqtt");

const BROKER_URL = "mqtt://localhost:1883";
const TOPIC = "sensors/data";
const GRID_SIZE = 50;
const CENTER = { lat: 12.9716, lon: 77.5946 };
const JITTER = 0.05;          // ≈5 km
const INTERVAL = 2000;

const client = mqtt.connect(BROKER_URL);
client.on("connect", () =>
  console.log(`Sensor simulator connected → ${BROKER_URL}`)
);
client.on("error", e => { console.error(e); process.exit(1); });

const nodes = Array.from({ length: GRID_SIZE }, (_, i) => ({
  id: i + 1,
  lat: CENTER.lat + (Math.random() - 0.5) * JITTER,
  lon: CENTER.lon + (Math.random() - 0.5) * JITTER
}));

function pushData() {
  nodes.forEach(n => {
    const payload = {
      id: n.id,
      lat: n.lat,
      lon: n.lon,
      rainfall: +(Math.random() * 100).toFixed(1), // mm/hr
      water: +(Math.random() * 3).toFixed(2)       // meters
    };
    client.publish(TOPIC, JSON.stringify(payload));
  });
  console.log("Sensor grid data broadcast");
}

setInterval(pushData, INTERVAL);
console.log("IoT Sensor simulation started…");
