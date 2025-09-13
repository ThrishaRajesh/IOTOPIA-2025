/**
 * alert_service.cjs
 * Subscribes to risk/zone and sends SMS + Voice alerts via Twilio.
 */

const mqtt = require("mqtt");
const twilio = require("twilio")

const client = mqtt.connect("mqtt://localhost:1883");
const RISK_TOPIC = "risk/zone";

// Twilio setup – Hard-coded for demo only
const TWILIO_SID        = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx";  
const TWILIO_AUTH_TOKEN = "your_auth_token_here";            
const TWILIO_FROM       = "+15005550006";                    
const TEST_PHONE        = "+91XXXXXXXXXX";   

const twilioClient = twilio(TWILIO_SID, TWILIO_AUTH_TOKEN);

client.on("connect", () => {
  console.log("Alert service connected");
  client.subscribe(RISK_TOPIC);
});

client.on("message", async (_, msg) => {
  const { centroid, riskDetail } = JSON.parse(msg);
  const text = `Disaster Alert! Risk score ${riskDetail.total.toFixed(2)}. 
Possible Flood/Fire/Earthquake. Move to safety immediately.`;

  const sendAlert = async (phone) => {
    try {
      await twilioClient.messages.create({ to: phone, from: TWILIO_FROM, body: text });
      await twilioClient.calls.create({
        to: phone,
        from: TWILIO_FROM,
        twiml: `<Response><Say voice="alice">${text}</Say></Response>`
      });
      console.log("Sending alert to", phone, text);
      console.log(`Alert sent to ${phone}`);
    } catch (err) {
      console.error("Twilio error:", err.message);
    }
  };

  if (TEST_PHONE) await sendAlert(TEST_PHONE);
});
