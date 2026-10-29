/* Offline Apps Script service doubles. No Google requests and no real responses. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const crypto=require('node:crypto');
const path=require('node:path');
const secret='offline-test-secret-32-characters-only';
const keys=['gamertag','country','age','gender','platform','question_1','question_2','question_3','question_4','question_5','rule_1','rule_2','ref_1','ref_2','ref_3'];
const metadata=['Coastal Craft S10 Application','Welcome','Process','References','Thank you','Please wait','About you','Minecraft','Rules'];
const headers=['entryID','Discord Name','Discord Nickname','Discord Long ID',...keys.map(k=>'Question '+k),'Timestamp','Approved?'];
function setup(){
  const props={APPLICATIONS_OPEN:'true',APPLICATION_INBOX_ID:'private-inbox',APPLICATION_WEB_SECRET:secret};
  const source=[metadata.concat(Array(12).fill('')),[...headers]];
  const rows=[['request_id','state','created_at','ticket','answers_json','schema_version','entry_id','detail']];
  let held=false;
  const session={active:'',effective:'owner@example.invalid'};
  const inbox={getLastRow:()=>rows.length,getRange:(r,c,n,m)=>({getValues:()=>rows.slice(r-1,r-1+n).map(row=>row.slice(c-1,c-1+m)),setValues:values=>{assert(held);values.forEach((row,i)=>{rows[r-1+i]=row;});},createTextFinder:id=>({matchEntireCell:()=>({findNext:()=>{const index=rows.findIndex(row=>row[0]===id);return index<0?null:{getRow:()=>index+1};}})})})};
  const app={getSheetId:()=>1,getRange:()=>({getDisplayValues:()=>source})};
  const context=vm.createContext({console,Date,JSON,Number,Error,Session:{getActiveUser:()=>({getEmail:()=>session.active}),getEffectiveUser:()=>({getEmail:()=>session.effective})},PropertiesService:{getScriptProperties:()=>({getProperty:k=>props[k]||null})},
    Utilities:{DigestAlgorithm:{SHA_256:'sha256'},Charset:{UTF_8:'utf8'},computeDigest:(_,text)=>crypto.createHash('sha256').update(text).digest(),computeHmacSha256Signature:(text,key)=>crypto.createHmac('sha256',key).update(text).digest(),base64EncodeWebSafe:bytes=>Buffer.from(bytes).toString('base64url'),base64DecodeWebSafe:text=>Buffer.from(text,'base64url'),newBlob:bytes=>({getDataAsString:()=>Buffer.from(bytes).toString()})},
    SpreadsheetApp:{openById:id=>id==='private-inbox'?{getSheetByName:()=>inbox}:{getSheets:()=>[app],getSheetByName:()=>app},flush:()=>{}},
    LockService:{getScriptLock:()=>({waitLock:()=>{assert(!held);held=true;},releaseLock:()=>{held=false;}})}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'Code.gs'),'utf8'),context);
  function ticket(overrides={}){const now=Math.floor(Date.now()/1000);const claims={v:1,uid:'123456789012345678',name:'Test User',nick:'Synthetic',iat:now,exp:now+86400,nonce:'a'.repeat(32),...overrides};const encoded=Buffer.from(JSON.stringify(claims)).toString('base64url');return encoded+'.'+crypto.createHmac('sha256',secret).update('coastal-application-v1.'+encoded).digest('base64url');}
  return {context,props,source,rows,ticket,session,held:()=>held,payload:()=>({ticket:ticket(),version:context.getApplication('').content.version,answers:Object.fromEntries(keys.map(k=>[k,'Synthetic answer']))})};
}
test('closed by default and no secret leakage',()=>{const s=setup();delete s.props.APPLICATIONS_OPEN;const result=s.context.getApplication('');assert.equal(result.closed,true);assert(!JSON.stringify(result).includes(secret));});
test('reads all 15 question labels in original order',()=>{const s=setup(),r=s.context.getApplication('');assert.equal(r.content.sections.flatMap(x=>x.questions).length,15);assert.equal(r.content.sections[2].questions[4].key,'ref_3');});
test('authentic signed identity; modified and expired tickets rejected',()=>{const s=setup();assert.equal(s.context.getApplication(s.ticket()).identity.uid,'123456789012345678');assert.throws(()=>s.context.getApplication(s.ticket()+'x'),/invalid/);const now=Math.floor(Date.now()/1000);assert.throws(()=>s.context.getApplication(s.ticket({iat:now-90000,exp:now-3600})),/expired/);});
test('retries produce one inbox row and stable receipt, never a live row',()=>{const s=setup(),p=s.payload();const r=s.context.submitApplication(p);assert.equal(r.state,'queued');assert.equal(s.context.submitApplication(p).requestId,r.requestId);assert.equal(s.rows.length,2);assert.equal(s.source.length,2);assert.equal(s.held(),false);});
test('wrong schema or stale question version cannot submit',()=>{const s=setup(),p=s.payload();s.source[1][4]='Changed question';assert.throws(()=>s.context.submitApplication(p),/questions have changed/);assert.equal(s.rows.length,1);assert.equal(s.held(),false);s.source[1][20]='Changed status';assert.throws(()=>s.context.getApplication(''),/columns have changed/);});
test('missing, whitespace-only, overlong and extra answers rejected',()=>{for(const mutate of [a=>delete a.age,a=>a.age=' ',a=>a.age='x'.repeat(201),a=>a.extra='unknown']){const s=setup(),p=s.payload();mutate(p.answers);assert.throws(()=>s.context.submitApplication(p));assert.equal(s.rows.length,1);assert(!s.held());}});
test('formula-looking answers stay inside JSON and receipts contain no answers',()=>{const s=setup(),p=s.payload();p.answers.age='=IMPORTXML("https://example.invalid","x")';s.context.submitApplication(p);assert(s.rows[1][4].startsWith('{'));const r=s.context.getApplication(p.ticket);assert(!JSON.stringify(r).includes('IMPORTXML'));assert(!JSON.stringify(s.context.getReceipt(p.ticket)).includes('answers'));});
test('same spreadsheet cannot be configured as inbox',()=>{const s=setup();s.props.APPLICATION_INBOX_ID='1ltMnItNgDBk5FhgsC-afi0l17OBnfOTcKPIkcSw9zvE';assert.throws(()=>s.context.getApplication(s.ticket()),/separate private/);});
test('configuration helpers are private; setup has a visible guarded entry point',()=>{const source=fs.readFileSync(path.join(__dirname,'Code.gs'),'utf8');const names=[...source.matchAll(/^function (\w+)\(/gm)].map(m=>m[1]).filter(n=>!n.endsWith('_'));assert.deepEqual(names,['doGet','getApplication','submitApplication','getReceipt','setupInbox']);});
test('setup rejects anonymous visitors and users other than the execution owner',()=>{const s=setup();assert.throws(()=>s.context.setupInbox(),/from the Apps Script editor/);s.session.active='applicant@example.invalid';assert.throws(()=>s.context.setupInbox(),/from the Apps Script editor/);});
test('setup accepts the editor user and keeps existing-inbox protection',()=>{const s=setup();s.session.active=s.session.effective;assert.throws(()=>s.context.setupInbox(),/Inbox already configured/);});
