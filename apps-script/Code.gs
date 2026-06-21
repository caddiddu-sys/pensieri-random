const READ_KEY  = "gl3LaUABp8XJpEFi64gyHj4lJGoK7CZ8gDuuAAQa";
const WRITE_KEY = "p3BmQIeswnRyAq0A0I7S2F43Fo6z7oZZsmJddEUo";
const SHEET_NAME = "pensieri";

const CONFIG_DEFAULTS = {
  paused: "false",
  window_start: "08:00",
  window_end: "22:30",
  min_per_day: "2",
  max_per_day: "4",
  min_gap_minutes: "90"
};

function getConfig_() {
  const props = PropertiesService.getScriptProperties();
  return {
    paused:           props.getProperty('paused')           === 'true',
    window_start:     props.getProperty('window_start')     || CONFIG_DEFAULTS.window_start,
    window_end:       props.getProperty('window_end')       || CONFIG_DEFAULTS.window_end,
    min_per_day:      parseInt(props.getProperty('min_per_day')      || CONFIG_DEFAULTS.min_per_day),
    max_per_day:      parseInt(props.getProperty('max_per_day')      || CONFIG_DEFAULTS.max_per_day),
    min_gap_minutes:  parseInt(props.getProperty('min_gap_minutes')  || CONFIG_DEFAULTS.min_gap_minutes)
  };
}

function unauthorized_() {
  return ContentService
    .createTextOutput(JSON.stringify({ error: "unauthorized" }))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  const key    = e && e.parameter && e.parameter.key;
  const action = (e && e.parameter && e.parameter.action) || 'list';

  // getConfig è accessibile con entrambe le chiavi (web app usa WRITE_KEY, notifier usa READ_KEY)
  if (action === 'getConfig') {
    if (key !== READ_KEY && key !== WRITE_KEY) return unauthorized_();
    return ContentService
      .createTextOutput(JSON.stringify(getConfig_()))
      .setMimeType(ContentService.MimeType.JSON);
  }

  // list richiede READ_KEY
  if (key !== READ_KEY) return unauthorized_();

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const rows  = sheet.getDataRange().getValues();
  const pensieri = [];
  for (let i = 1; i < rows.length; i++) {
    const testo  = String(rows[i][0]).trim();
    const attivo = String(rows[i][1]).trim().toUpperCase();
    if (testo && attivo === "TRUE") pensieri.push(testo);
  }
  return ContentService
    .createTextOutput(JSON.stringify(pensieri))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const key    = e && e.parameter && e.parameter.key;
  const action = (e && e.parameter && e.parameter.action) || 'addPensiero';

  if (key !== WRITE_KEY) return unauthorized_();

  if (action === 'setConfig') {
    const props   = PropertiesService.getScriptProperties();
    const allowed = ['paused', 'window_start', 'window_end', 'min_per_day', 'max_per_day', 'min_gap_minutes'];
    allowed.forEach(k => {
      if (e.parameter[k] !== undefined) props.setProperty(k, String(e.parameter[k]));
    });
    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  // addPensiero (default)
  const testo     = e.parameter.testo     ? String(e.parameter.testo).trim()     : "";
  const categoria = e.parameter.categoria ? String(e.parameter.categoria).trim() : "";

  if (!testo || testo.length < 10 || testo.length > 300) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, reason: "invalid_length" }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  const testoNorm = testo.toLowerCase().replace(/\s+/g, " ");
  const sheet     = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  const rows      = sheet.getDataRange().getValues();

  for (let i = 1; i < rows.length; i++) {
    const esistente = String(rows[i][0]).trim().toLowerCase().replace(/\s+/g, " ");
    if (esistente === testoNorm) {
      return ContentService
        .createTextOutput(JSON.stringify({ ok: false, reason: "duplicate" }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }

  sheet.appendRow([testo, true, categoria]);
  return ContentService
    .createTextOutput(JSON.stringify({ ok: true }))
    .setMimeType(ContentService.MimeType.JSON);
}
