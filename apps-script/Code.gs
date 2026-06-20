const READ_KEY = "gl3LaUABp8XJpEFi64gyHj4lJGoK7CZ8gDuuAAQa";
const WRITE_KEY = "p3BmQIeswnRyAq0A0I7S2F43Fo6z7oZZsmJddEUo";
const SHEET_NAME = "pensieri";

function doGet(e) {
  const key = e && e.parameter && e.parameter.key;
  if (key !== READ_KEY) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: "unauthorized" }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const rows = sheet.getDataRange().getValues();
  const pensieri = [];

  // Salta la riga 0 (intestazione), considera solo le righe con attivo = TRUE
  for (let i = 1; i < rows.length; i++) {
    const testo = String(rows[i][0]).trim();
    const attivo = String(rows[i][1]).trim().toUpperCase();
    if (testo && attivo === "TRUE") {
      pensieri.push(testo);
    }
  }

  return ContentService
    .createTextOutput(JSON.stringify(pensieri))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const key = e && e.parameter && e.parameter.key;
  if (key !== WRITE_KEY) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, reason: "unauthorized" }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  const testo = e.parameter.testo ? String(e.parameter.testo).trim() : "";
  const categoria = e.parameter.categoria ? String(e.parameter.categoria).trim() : "";

  if (!testo || testo.length < 10 || testo.length > 300) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, reason: "invalid_length" }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  // Normalizza il testo per il confronto anti-duplicazione
  const testoNorm = testo.toLowerCase().replace(/\s+/g, " ");

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const rows = sheet.getDataRange().getValues();

  // Controlla duplicati (salta intestazione)
  for (let i = 1; i < rows.length; i++) {
    const esistente = String(rows[i][0]).trim().toLowerCase().replace(/\s+/g, " ");
    if (esistente === testoNorm) {
      return ContentService
        .createTextOutput(JSON.stringify({ ok: false, reason: "duplicate" }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }

  // Aggiunge la nuova riga
  sheet.appendRow([testo, true, categoria]);

  return ContentService
    .createTextOutput(JSON.stringify({ ok: true }))
    .setMimeType(ContentService.MimeType.JSON);
}
