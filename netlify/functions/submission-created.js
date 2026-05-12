// Triggered automatically da Netlify quando arriva una form submission.
// Compone email HTML brand-coerente e la invia via Resend API.

const RESEND_API = "https://api.resend.com/emails";

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildHtml(data) {
  const Nome = escapeHtml(data.Nome || "");
  const Cognome = escapeHtml(data.Cognome || "");
  const Email = escapeHtml(data.Email || "");
  const Oggetto = escapeHtml(data.Oggetto || "Non specificato");
  const Messaggio = escapeHtml(data.Messaggio || "").replace(/\n/g, "<br>");
  const ts = new Date().toLocaleString("it-IT", { dateStyle: "long", timeStyle: "short", timeZone: "Europe/Rome" });

  return `<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nuovo messaggio dal sito</title>
</head>
<body style="margin:0;padding:0;background:#f5f3ee;font-family:Georgia,'Times New Roman',serif;color:#1a1a1a;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f5f3ee;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width:600px;background:#fdfcf9;border:1px solid #e5e3dc;">
          <!-- HEADER -->
          <tr>
            <td style="background:#0e0d0c;padding:32px 40px;text-align:center;">
              <p style="margin:0 0 6px;font-family:-apple-system,BlinkMacSystemFont,Arial,sans-serif;font-size:9px;letter-spacing:5px;color:rgba(255,255,255,0.5);text-transform:uppercase;">PIEMME · Paola Maccioni</p>
              <h1 style="margin:0;font-size:22px;font-weight:300;color:#e8e3db;letter-spacing:0.5px;">Nuovo messaggio dal sito</h1>
              <div style="width:32px;height:1px;background:#7a7570;margin:18px auto 0;"></div>
            </td>
          </tr>

          <!-- META -->
          <tr>
            <td style="padding:24px 40px 0;">
              <p style="margin:0;font-size:11px;letter-spacing:2px;color:#999;text-transform:uppercase;font-family:-apple-system,Arial,sans-serif;">${escapeHtml(ts)}</p>
            </td>
          </tr>

          <!-- CONTENT -->
          <tr>
            <td style="padding:16px 40px 24px;">
              <h2 style="margin:0 0 6px;font-size:24px;font-weight:300;color:#1a1a1a;">${Nome} ${Cognome}</h2>
              <p style="margin:0;font-size:14px;color:#555;font-style:italic;">
                <a href="mailto:${Email}" style="color:#555;text-decoration:none;border-bottom:1px solid #d4d0c8;">${Email}</a>
              </p>
            </td>
          </tr>

          <!-- OGGETTO -->
          <tr>
            <td style="padding:0 40px 16px;">
              <table cellspacing="0" cellpadding="0" border="0" width="100%">
                <tr>
                  <td style="border-top:1px solid #e5e3dc;padding-top:18px;">
                    <p style="margin:0 0 4px;font-size:9px;letter-spacing:3px;color:#999;text-transform:uppercase;font-family:-apple-system,Arial,sans-serif;">Oggetto</p>
                    <p style="margin:0;font-size:15px;color:#1a1a1a;">${Oggetto}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- MESSAGGIO -->
          <tr>
            <td style="padding:8px 40px 32px;">
              <p style="margin:0 0 8px;font-size:9px;letter-spacing:3px;color:#999;text-transform:uppercase;font-family:-apple-system,Arial,sans-serif;">Messaggio</p>
              <div style="font-size:15px;line-height:1.75;color:#1a1a1a;font-style:italic;border-left:2px solid #c8c5be;padding-left:18px;">${Messaggio}</div>
            </td>
          </tr>

          <!-- CTA -->
          <tr>
            <td style="padding:0 40px 32px;">
              <a href="mailto:${Email}?subject=Re:%20${encodeURIComponent(Oggetto)}" style="display:inline-block;background:#0e0d0c;color:#e8e3db;padding:14px 28px;text-decoration:none;font-family:-apple-system,Arial,sans-serif;font-size:10px;letter-spacing:4px;text-transform:uppercase;">Rispondi a ${Nome} →</a>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:#f0eeea;padding:18px 40px;border-top:1px solid #e5e3dc;">
              <p style="margin:0;font-size:10px;color:#999;font-family:-apple-system,Arial,sans-serif;letter-spacing:1px;line-height:1.7;">
                Messaggio ricevuto tramite paolamaccioni.com<br>
                © 2023 PIEMME di Paola Maccioni · C.F. MCCPLA80R64B354E
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;
}

exports.handler = async (event) => {
  try {
    const payload = JSON.parse(event.body || "{}");
    const submission = payload.payload || payload;
    const data = submission.data || submission.human_fields || {};
    const formName = submission.form_name || "";

    if (formName !== "contatti") {
      return { statusCode: 200, body: "skip" };
    }

    const apiKey = process.env.RESEND_API_KEY;
    const fromEmail = process.env.RESEND_FROM || "onboarding@resend.dev";
    const toEmail = process.env.NOTIFY_TO || "infopiemmeart@gmail.com";
    if (!apiKey) {
      console.error("RESEND_API_KEY mancante");
      return { statusCode: 500, body: "API key missing" };
    }

    const html = buildHtml(data);
    const nome = (data.Nome || "Visitatore") + " " + (data.Cognome || "");
    const subject = `${data.Oggetto || "Messaggio"} — da ${nome.trim()}`;

    const res = await fetch(RESEND_API, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: `Paola Maccioni Site <${fromEmail}>`,
        to: [toEmail],
        reply_to: data.Email,
        subject,
        html,
      }),
    });

    if (!res.ok) {
      const txt = await res.text();
      console.error("Resend error:", res.status, txt);
      return { statusCode: 502, body: "Email send failed" };
    }

    return { statusCode: 200, body: "ok" };
  } catch (err) {
    console.error(err);
    return { statusCode: 500, body: String(err) };
  }
};
