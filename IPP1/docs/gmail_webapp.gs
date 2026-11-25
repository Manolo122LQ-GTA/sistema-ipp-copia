/**
 * Web App de Gmail para el Sistema IPP-IUTAG.
 *
 * Pasos:
 * 1. Entra en https://script.google.com con la cuenta de Gmail desde la que
 *    quieres enviar (por ejemplo, coelloirving2026@gmail.com).
 * 2. Crea un proyecto nuevo y pega este código en Code.gs.
 * 3. Implementar > Nueva implementación > Aplicación web.
 *    - Ejecutar como: Yo
 *    - Quién tiene acceso: Cualquier persona
 * 4. Copia la URL que termina en /exec y pégala en GMAIL_WEBAPP_URL.
 * 5. Copia el token de abajo y pégalo en GMAIL_WEBAPP_TOKEN.
 *
 * El token evita que cualquiera que descubra la URL pueda enviar correos.
 * No compartas la URL ni el token.
 */

var TOKEN = '__TOKEN__';

function doGet() {
  return json({ok: true, servicio: 'IPP Gmail WebApp'});
}

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return json({ok: false, error: 'Solicitud vacía'});
    }

    var data = JSON.parse(e.postData.contents);
    if (String(data.token) !== String(TOKEN)) {
      return json({ok: false, error: 'No autorizado'});
    }

    var opciones = {};
    if (data.html) opciones.htmlBody = data.html;
    if (data.fromName) opciones.name = data.fromName;
    if (data.cc && data.cc.length) opciones.cc = data.cc.join(',');
    if (data.bcc && data.bcc.length) opciones.bcc = data.bcc.join(',');

    GmailApp.sendEmail(
      (data.to || []).join(','),
      data.subject || '(Sin asunto)',
      data.text || '',
      opciones
    );

    return json({ok: true});
  } catch (err) {
    return json({ok: false, error: String(err)});
  }
}

function json(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
