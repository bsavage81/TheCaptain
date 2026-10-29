/* Coastal Craft application portal. The Captain remains the sole database writer. */
const QUESTION_KEYS_ = ['gamertag','country','age','gender','platform','question_1','question_2','question_3','question_4','question_5','rule_1','rule_2','ref_1','ref_2','ref_3'];
const INBOX_HEADERS_ = ['request_id','state','created_at','ticket','answers_json','schema_version','entry_id','detail'];

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index').setTitle('Coastal Craft • Apply')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function settings_() {
  const p = PropertiesService.getScriptProperties();
  const result = {
    source: p.getProperty('APPLICATION_SHEET_ID') || '1ltMnItNgDBk5FhgsC-afi0l17OBnfOTcKPIkcSw9zvE',
    tab: p.getProperty('APPLICATION_TAB') || 'Form Responses 1',
    inbox: p.getProperty('APPLICATION_INBOX_ID'),
    secret: p.getProperty('APPLICATION_WEB_SECRET'),
    enabled: p.getProperty('APPLICATIONS_OPEN') === 'true'
  };
  return result;
}

function digest_(text) {
  return Utilities.base64EncodeWebSafe(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8)).replace(/=+$/, '');
}

function content_() {
  const cfg = settings_();
  const book = SpreadsheetApp.openById(cfg.source);
  const sheet = book.getSheetByName(cfg.tab);
  if (!sheet || book.getSheets()[0].getSheetId() !== sheet.getSheetId()) throw new Error('The application worksheet needs operator attention.');
  const rows = sheet.getRange(1,1,2,21).getDisplayValues();
  const h = rows[1], m = rows[0];
  if (h[0] !== 'entryID' || h[3] !== 'Discord Long ID' || h[19] !== 'Timestamp' || h[20] !== 'Approved?' || h.slice(4,19).some(x => !x.trim())) {
    throw new Error('The application columns have changed. Please contact an OP.');
  }
  return {
    title:m[0], description:m[1], referenceTitle:m[2], referenceDescription:m[3],
    thanksTitle:m[4], thanksDescription:m[5],
    version:digest_(JSON.stringify(rows)),
    sections:[0,1,2].map(i => ({title:(m[6+i] || ['About you','Minecraft','Rules and references'][i]).replace(/\*\*/g,''),
      questions:QUESTION_KEYS_.slice(i*5,i*5+5).map((key,j) => ({key, label:h[4+i*5+j], min:2, max:200}))}))
  };
}

function equal_(a,b) {
  if (typeof a !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i=0;i<a.length;i++) diff |= a.charCodeAt(i)^b.charCodeAt(i);
  return diff === 0;
}

function ticket_(value) {
  const cfg = settings_();
  if (!cfg.enabled || !cfg.inbox || !cfg.secret || cfg.secret.length < 32) throw new Error('Applications are being set up. Please check back soon.');
  if (typeof value !== 'string' || value.length > 2048) throw new Error('Paste your private access code from /applycoastal.');
  const parts = value.trim().split('.');
  if (parts.length !== 2) throw new Error('That access code is invalid. Run /applycoastal for a new code.');
  const signature = Utilities.base64EncodeWebSafe(Utilities.computeHmacSha256Signature('coastal-application-v1.'+parts[0], cfg.secret, Utilities.Charset.UTF_8)).replace(/=+$/, '');
  if (!equal_(parts[1],signature)) throw new Error('That access code is invalid. Run /applycoastal for a new code.');
  let data;
  try { data = JSON.parse(Utilities.newBlob(Utilities.base64DecodeWebSafe(parts[0])).getDataAsString('UTF-8')); }
  catch(e) { throw new Error('That access code is invalid.'); }
  const now = Math.floor(Date.now()/1000);
  if (data.v !== 1 || !/^\d{15,22}$/.test(data.uid) || !/^[a-f0-9]{32}$/.test(data.nonce) || typeof data.name !== 'string' || data.name.length > 100 || typeof data.nick !== 'string' || data.nick.length > 100 || !Number.isInteger(data.exp) || !Number.isInteger(data.iat) || data.iat > now+60 || data.exp < now || data.exp-data.iat !== 86400) {
    throw new Error('Your access code has expired or is invalid. Run /applycoastal for a new code.');
  }
  return data;
}

function inbox_() {
  const cfg = settings_();
  if (cfg.inbox === cfg.source) throw new Error('Use a separate private inbox spreadsheet.');
  const sheet = SpreadsheetApp.openById(cfg.inbox).getSheetByName('Inbox');
  if (!sheet || JSON.stringify(sheet.getRange(1,1,1,8).getValues()[0]) !== JSON.stringify(INBOX_HEADERS_)) throw new Error('The application inbox needs operator attention.');
  return sheet;
}

function find_(sheet, id) {
  if (sheet.getLastRow()<2) return null;
  const cell = sheet.getRange(2,1,sheet.getLastRow()-1,1).createTextFinder(id).matchEntireCell(true).findNext();
  return cell ? sheet.getRange(cell.getRow(),1,1,8).getValues()[0] : null;
}

function receipt_(row) {
  const messages = {
    queued:'Your application is in the inbox. The Captain will collect it shortly. You can close this page.',
    processing:'The Captain is saving your application. Please do not submit again.',
    complete:'Your application was saved and sent to the OP team for review.',
    saved_notification_failed:'Your application was saved, but its review message needs OP attention. Please do not resubmit.',
    needs_attention:'An OP needs to check this submission. Please do not submit again.'
  };
  return {requestId:String(row[0]),state:String(row[1]),entryId:row[6] ? String(row[6]) : '',message:messages[row[1]] || messages.needs_attention};
}

function getApplication(code) {
  const cfg = settings_();
  if (!cfg.enabled || !cfg.inbox || !cfg.secret) return {closed:true,message:'Applications are being set up. Please check back soon.'};
  const content = content_();
  if (!code) return {content};
  const identity = ticket_(code);
  const existing = find_(inbox_(),identity.nonce);
  return {content,identity:{name:identity.name,nick:identity.nick,uid:identity.uid},receipt:existing ? receipt_(existing) : null};
}

function submitApplication(payload) {
  if (!payload || typeof payload !== 'object') throw new Error('Invalid submission.');
  const identity = ticket_(payload.ticket);
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    const sheet = inbox_();
    const existing = find_(sheet,identity.nonce);
    if (existing) return receipt_(existing); // Stable retry after a lost response.
    const content = content_();
    if (payload.version !== content.version) throw new Error('The questions have changed. Reload this page and review your saved answers before submitting.');
    if (!payload.answers || typeof payload.answers !== 'object' || Object.keys(payload.answers).length !== QUESTION_KEYS_.length) throw new Error('Please answer every question.');
    const answers = {};
    QUESTION_KEYS_.forEach(key => {
      const answer = payload.answers[key];
      if (typeof answer !== 'string' || answer.trim().length<2 || answer.trim().length>200) throw new Error('Each answer must contain 2–200 characters.');
      answers[key] = answer.trim();
    });
    const created = new Date().toISOString();
    // No live database writes: all untrusted content is inside a JSON cell.
    const row = [identity.nonce,'queued',created,payload.ticket,JSON.stringify(answers),content.version,'',''];
    sheet.getRange(sheet.getLastRow()+1,1,1,8).setValues([row]);
    SpreadsheetApp.flush();
    return receipt_(row);
  } finally { lock.releaseLock(); }
}

function getReceipt(code) {
  const identity = ticket_(code);
  const row = find_(inbox_(),identity.nonce);
  return row ? receipt_(row) : null;
}

/* Visible editor entry point. In an owner-executed web app, other visitors cannot pass this guard. */
function setupInbox() {
  const active = Session.getActiveUser().getEmail();
  const effective = Session.getEffectiveUser().getEmail();
  if (!active || active !== effective) throw new Error('Run setupInbox from the Apps Script editor while signed in as the deployment owner.');
  return setupInbox_();
}

/* Internal helper. Never edits the live application sheet. */
function setupInbox_() {
  const p = PropertiesService.getScriptProperties();
  if (p.getProperty('APPLICATION_INBOX_ID')) throw new Error('Inbox already configured; refusing to create another.');
  const book = SpreadsheetApp.create('Coastal Craft Application Inbox');
  const sheet = book.getSheets()[0].setName('Inbox');
  sheet.getRange(1,1,1,8).setValues([INBOX_HEADERS_]);
  sheet.setFrozenRows(1);
  p.setProperty('APPLICATION_INBOX_ID',book.getId());
  p.setProperty('APPLICATIONS_OPEN','false');
  console.log('Private inbox created: '+book.getUrl());
}
