const fs=require('node:fs'),path=require('node:path');
const {root,assert,equal,digest,rpc,read,receiptSummary,save}=require('./transport.cjs');
const {decodeReceipt}=require('./receipt-calldata.cjs');
const {cases,args,initial,plan,replay}=require('./scenario.cjs');
const load=name=>JSON.parse(fs.readFileSync(path.join(root,'proofs',name+'.json')));
async function main(){
 const offline=process.argv.includes('--offline'),suite=load('suite'),journal=load('transactions'),code=fs.readFileSync(path.join(root,'contracts/cross_ledger.py'));
 const revision=fs.readFileSync(path.join(root,'config/fixture-revision.txt'),'utf8').trim();
 const selected=process.env.CROSS_SCENARIO||'all';assert(selected==='all'||Object.hasOwn(cases,selected),'Unknown verification scope');
 const ids=selected==='all'?Object.keys(cases):[selected];
 assert(suite.length===ids.length&&journal.source_sha256===digest(code),'Complete source-bound suite');if(!offline)assert(await rpc('eth_chainId',[])==='0xf22f','StudioNet only');
 const hashes=new Set(),summary={scope:selected,mode:offline?'offline-artifact':'fresh-rpc-and-state',verified_at:new Date().toISOString(),source_sha256:digest(code),instances:[],transactions:[]};
 async function verify(label,hash,d,caller,expected,error){
  const saved=load(label+'-receipt'),r=offline?saved:await rpc('eth_getTransactionByHash',[hash]),s=receiptSummary(r),recorded=Object.keys(r.consensus_data.votes).length;
  assert(!hashes.has(hash)&&journal.hashes[label]===hash,'Unique journaled transaction');hashes.add(hash);
  assert(s.hash===hash&&s.status==='FINALIZED'&&s.result==='MAJORITY_AGREE'&&s.agree>recorded/2&&recorded===s.agree+s.disagree+s.idle&&recorded===r.consensus_data.validators.length+1,'Complete final vote set and strict consensus majority');
  assert((r.to_address||r.recipient).toLowerCase()===d.contract.toLowerCase()&&(r.from_address||r.sender).toLowerCase()===d.accounts[caller],'Actual participant signer and target');
  assert(equal(saved.data,r.data)&&equal(saved.consensus_data.votes,r.consensus_data.votes)&&equal(await decodeReceipt(r),expected),'Actual decoded calldata and preserved votes');
  assert(error?s.execution==='ERROR':['SUCCESS','FINISHED_WITH_RETURN'].includes(s.execution),'Expected execution result');
  if(label.endsWith('-deployment'))assert(code.equals(Buffer.from(r.data.contract_code,'base64')),'Exact deployment source');
  if(error){const raw=Buffer.from(r.consensus_data.leader_receipt[0].result,'base64');assert(raw[0]===1&&raw.subarray(1).toString('utf8')===error,'Exact rejection bytes');}
  summary.transactions.push({label,...s,recorded_voters:recorded,rotation_count:r.rotation_count,round_count:r.num_of_rounds});
 }
 for(let i=0;i<suite.length;i++){
  const d=suite[i],id=ids[i];assert(d.id===id&&d.network==='studionet'&&d.chain_id===61999&&d.fixture_revision===revision&&d.source_sha256===digest(code)&&d.accounts.length===3&&new Set(d.accounts).size===3&&equal(d.args,args(id,revision,d.accounts)),'Fixed deployment and participants');
  await verify(id+'-deployment',d.deployment,d,0,{args:d.args});let previous=load(id+'-initial-state');assert(equal(previous,initial(id,revision,d.accounts)),'Exact native endowment');
  const trace=load(id+'-trace'),items=plan(id,d.accounts);assert(trace.length===items.length,'Complete interaction plan');
  for(let j=0;j<items.length;j++){
   const item=items[j],p=trace[j];assert(Object.keys(item).every(k=>equal(p[k],item[k]))&&equal(p.state_before,previous),'Signed trace linkage');
   await verify(item.label,p.transaction,d,item.caller,{method:item.method,args:item.args},item.error);replay(previous,item,p.state,id,revision,d.accounts);previous=p.state;
  }
  assert(equal(previous,load(id+'-final-state')),'Exact final title ledger');
  if(!offline){assert(code.equals(Buffer.from(await rpc('gen_getContractCode',[d.contract]),'base64')),'Fresh live source');assert(equal(previous,await read(id+'-fresh-final',['call',d.contract,'get_state'])),'Fresh full native-right state');}
  summary.instances.push({id,contract:d.contract,phase:previous.phase,raw:previous.raw,units:previous.units,quote:previous.quote,settlement:previous.settlement,transfers:previous.transfers});
 }
 const expectedCount=suite.reduce((total,d)=>total+1+plan(d.id,d.accounts).length,0);
 assert(hashes.size===expectedCount&&Object.keys(journal.hashes).length===expectedCount&&(selected!=='all'||expectedCount===29),'Exactly the planned receipt set');summary.transaction_calldata_checked=true;summary.rejection_bytes_checked=true;
 if(!offline){summary.live_state_match=true;save(selected==='all'?'verification':'verification-'+selected,summary);}console.log(JSON.stringify(summary,null,2));
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
