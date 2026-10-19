const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),repo='mohammadisina1988-jpg/cross-ledger';
const criteria=['The described units may be transferred to another holder without issuer approval.','The described units remain valid indefinitely without any expiry deadline.'];
const cases={cross:['open-zero','open-one','buyer-two'],gap:['open-zero','empty-one','buyer-two'],screen:['blocked-zero','unknown-one','buyer-two']};
const decisions={'open-zero':['PASS','PASS'],'open-one':['PASS','PASS'],'blocked-zero':['FAIL','PASS'],'unknown-one':['UNKNOWN','PASS']};
const canonical=x=>Array.isArray(x)?x.map(canonical):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,canonical(x[k])])):x;
const equal=(a,b)=>JSON.stringify(canonical(a))===JSON.stringify(canonical(b));
const clone=x=>JSON.parse(JSON.stringify(x));
function assert(ok,message){if(!ok)throw Error(message);}
function args(id,revision,accounts){
 const documents=cases[id].map(name=>({url:`https://raw.githubusercontent.com/${repo}/${revision}/records/${name}.json`,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'records',name+'.json'))).digest('hex')}));
 return [repo,'voucher-market',accounts,[6,id==='gap'?0:4,0],[0,0,100],criteria,documents.map(d=>d.url),documents.map(d=>d.sha256)];
}
function configuration(a){return {repository:a[0],market:a[1],accounts:a[2],raw_units:a[3],quote_credits:a[4],criteria:a[5],documents:a[6].map((url,lot)=>({lot,url,sha256:a[7][lot]}))};}
function initial(id,revision,accounts){const c=configuration(args(id,revision,accounts));return {configuration:c,phase:'OPEN',raw:c.raw_units,units:[0,0,0],quote:c.quote_credits,seals:[false,false,false],assessments:[null,null,null],orders:[],settlement:{},transfers:[]};}
function oracle(orders){
 // Independently expand eligible orders to per-unit tickets, then pair ticket streams.
 const open=orders.filter(o=>o.status==='OPEN'),table=[];
 for(let p=1;p<=100;p++){
  const buys=open.filter(o=>o.side==='BID'&&o.limit>=p).sort((a,b)=>b.limit-a.limit||a.id-b.id).flatMap(o=>Array(o.quantity).fill(o.id));
  const sells=open.filter(o=>o.side==='ASK'&&o.limit<=p).sort((a,b)=>a.limit-b.limit||a.id-b.id).flatMap(o=>Array(o.quantity).fill(o.id));
  if(buys.length&&sells.length)table.push({p,volume:Math.min(buys.length,sells.length),imbalance:Math.abs(buys.length-sells.length),buys,sells});
 }
 table.sort((a,b)=>b.volume-a.volume||a.imbalance-b.imbalance||a.p-b.p);
 const best=table[0],filled=Object.fromEntries(open.map(o=>[o.id,0])),trades=[];
 if(best)for(let i=0;i<best.volume;i++){
  const bid=best.buys[i],ask=best.sells[i];filled[bid]++;filled[ask]++;
  const last=trades.at(-1);if(last&&last.bid===bid&&last.ask===ask)last.quantity++;else trades.push({bid,ask,quantity:1});
 }
 return {status:best?'TRADED':'NO_CROSS',price:best?.p||0,volume:best?.volume||0,imbalance:best?.imbalance||0,fills:open.map(o=>[o.id,filled[o.id]]),trades};
}
function check(s,id,revision,accounts){
 const config=configuration(args(id,revision,accounts));assert(equal(s.configuration,config),'Exact immutable market configuration');
 assert(Object.keys(s).sort().join(',')==='assessments,configuration,orders,phase,quote,raw,seals,settlement,transfers,units','Exact complete ledger schema');
 for(const values of [s.raw,s.units,s.quote])assert(values.length===3&&values.every(n=>Number.isSafeInteger(n)&&n>=0),'Nonnegative bounded balances');
 const open=s.orders.filter(o=>o.status==='OPEN');
 assert(s.raw.reduce((a,b)=>a+b,0)+s.units.reduce((a,b)=>a+b,0)+open.filter(o=>o.side==='ASK').reduce((a,o)=>a+o.quantity,0)===config.raw_units.reduce((a,b)=>a+b,0),'Total native inventory conserved');
 assert(s.quote.reduce((a,b)=>a+b,0)+open.filter(o=>o.side==='BID').reduce((a,o)=>a+o.quantity*o.limit,0)===100,'Quote credits and escrow conserved');
 assert(s.assessments.length===3&&s.seals.length===3&&s.seals.every(x=>typeof x==='boolean'),'Participant records');
 s.assessments.forEach((record,i)=>{
  if(record===null)return;
  const name=cases[id][i],source=JSON.parse(fs.readFileSync(path.join(root,'records',name+'.json'))),expected=decisions[name];
  assert(expected&&Object.keys(record).sort().join(',')==='assessment,lot,sha256,source,status,url'&&record.lot===i&&record.url===config.documents[i].url&&record.sha256===config.documents[i].sha256&&equal(record.source,source),'Full committed source and lot binding');
  const a=record.assessment;assert(Object.keys(a).sort().join(',')==='anchors,decisions'&&equal(a.decisions,expected),'Every substantive criterion result');
  assert(Array.isArray(a.anchors)&&a.anchors.length===2&&a.anchors.every((indices,j)=>Array.isArray(indices)&&indices.length<=3&&(expected[j]==='UNKNOWN'||indices.length>0)&&indices.every(k=>Number.isInteger(k)&&k>=0&&k<source.clauses.length)&&equal(indices,[...new Set(indices)].sort((x,y)=>x-y))),'All source anchors');
  assert(record.status===(expected.includes('FAIL')?'BLOCKED':expected.includes('UNKNOWN')?'REVIEW':'ADMITTED'),'Exact admission boundary');
  assert(s.raw[i]===(record.status==='ADMITTED'?0:config.raw_units[i]),'Only admitted raw units convert');
 });
}
function plan(id){
 const p=[];const add=(label,caller,method,args=[],error)=>p.push({label:id+'-'+label,caller,method,args,...(error?{error}:{})});
 add('admit-0',2,'admit',[0]);if(id!=='gap')add('admit-1',2,'admit',[1]);
 if(id==='cross'){
  add('ask-0',0,'place',['ASK',5,4]);add('ask-1',1,'place',['ASK',4,6]);add('bid',2,'place',['BID',7,10]);
  add('unauthorized-cancel',2,'cancel_order',[0],'[EXPECTED] Open order owner only');
 }else if(id==='gap'){
  add('ask-0',0,'place',['ASK',4,9]);add('bid',2,'place',['BID',4,7]);
 }else{
  add('blocked-ask',0,'place',['ASK',1,1],'[EXPECTED] Insufficient admitted inventory');add('bid',2,'place',['BID',5,10]);
 }
 for(let i=0;i<3;i++)add('seal-'+i,i,'seal');add('clear',2,'clear');
 if(id==='cross')add('transfer',2,'transfer_units',[0,2]);
 return p;
}
function replay(before,item,after,id,revision,accounts){
 check(before,id,revision,accounts);check(after,id,revision,accounts);
 const s=clone(before),owner=item.caller,a=item.args;
 if(item.error){
  assert(item.method==='cancel_order'?s.orders[a[0]].owner!==owner:item.method==='place'&&a[0]==='ASK'&&s.units[owner]<a[1],'Actual negative precondition');
  assert(equal(before,after),'Rejected operation preserves complete state');return;
 }
 if(item.method==='admit'){
  const lot=a[0];assert(s.phase==='OPEN'&&!s.assessments[lot]&&!s.seals[lot]&&s.raw[lot]>0,'Assessment precondition');
  s.assessments[lot]=clone(after.assessments[lot]);assert(s.assessments[lot],'Recorded full assessment');
  if(s.assessments[lot].status==='ADMITTED'){s.units[lot]+=s.raw[lot];s.raw[lot]=0;}
 }else if(item.method==='place'){
  assert(s.phase==='OPEN'&&!s.seals[owner],'Unsealed signed order');const [side,quantity,limit]=a;
  assert(s.orders.every(o=>o.owner!==owner||o.side===side),'No self-crossing sides');
  if(side==='ASK'){assert(s.units[owner]>=quantity,'Inventory reserve');s.units[owner]-=quantity;}else{assert(s.quote[owner]>=quantity*limit,'Quote reserve');s.quote[owner]-=quantity*limit;}
  s.orders.push({id:s.orders.length,owner,side,quantity,limit,status:'OPEN',filled:0});
 }else if(item.method==='seal'){
  assert(s.phase==='OPEN'&&!s.seals[owner],'Own seal exactly once');s.seals[owner]=true;if(s.seals.every(Boolean))s.phase='READY';
 }else if(item.method==='clear'){
  assert(s.phase==='READY'&&s.seals.every(Boolean),'All actual participant seals');const result=oracle(s.orders),fills=Object.fromEntries(result.fills);
  for(const o of s.orders){if(o.status!=='OPEN')continue;const fill=fills[o.id];if(o.side==='ASK'){s.units[o.owner]+=o.quantity-fill;s.quote[o.owner]+=result.price*fill;}else{s.quote[o.owner]+=o.quantity*o.limit-result.price*fill;s.units[o.owner]+=fill;}o.status='SETTLED';o.filled=fill;}
  s.phase='CLEARED';s.settlement=result;
 }else if(item.method==='transfer_units'){
  assert(['CLEARED','ABORTED'].includes(s.phase)&&s.units[owner]>=a[1]&&owner!==a[0],'Native holder transfer');s.units[owner]-=a[1];s.units[a[0]]+=a[1];s.transfers.push({from:owner,to:a[0],quantity:a[1]});
 }else throw Error('Unknown planned operation');
 assert(equal(s,after),'Exact independent escrow, settlement and balance transition: '+item.label);
}
module.exports={cases,args,initial,plan,replay,oracle,check};
