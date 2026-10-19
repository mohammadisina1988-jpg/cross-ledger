import ast
import hashlib
import itertools
import json
from pathlib import Path
import random
import re
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'contracts/cross_ledger.py'
REPO='mohammadisina1988-jpg/cross-ledger'
CRITERIA=['The described units may be transferred to another holder without issuer approval.',
          'The described units remain valid indefinitely without any expiry deadline.']
CASES={'cross':['open-zero','open-one','buyer-two'],'gap':['open-zero','empty-one','buyer-two'],
       'screen':['blocked-zero','unknown-one','buyer-two']}
DECISIONS={'open-zero':(['PASS','PASS'],[[0],[1]]),'open-one':(['PASS','PASS'],[[1],[0]]),
           'blocked-zero':(['FAIL','PASS'],[[1],[2]]),'unknown-one':(['UNKNOWN','PASS'],[[1],[0]])}

def record(name):
    body=(ROOT/'records'/f'{name}.json').read_bytes()
    return f'https://raw.githubusercontent.com/{REPO}/'+ 'a'*40 +f'/records/{name}.json',hashlib.sha256(body).hexdigest(),body

def args(accounts,case='cross'):
    records=[record(name) for name in CASES[case]]
    return [REPO,'voucher-market',accounts[:3],[6,0 if case=='gap' else 4,0],[0,0,100],CRITERIA,[r[0] for r in records],[r[1] for r in records]]

def assessment(name):
    decisions,anchors=DECISIONS[name]
    return {'decisions':list(decisions),'anchors':[list(a) for a in anchors]}

def mocks(vm,name,answer=None,audit=None,body=None,status=200):
    vm.clear_mocks();url,_,raw=record(name)
    vm.mock_web(re.escape(url),{'status':status,'body':raw if body is None else body})
    vm.mock_llm(r'.*CROSSLEDGER-ASSESS.*',json.dumps(assessment(name) if answer is None else answer))
    vm.mock_llm(r'.*CROSSLEDGER-AUDIT.*',json.dumps({'checks':[True,True]} if audit is None else audit))

def admit(c,vm,case='cross'):
    for i,name in enumerate(CASES[case]):
        if name in DECISIONS:
            mocks(vm,name);c.admit(i);assert vm.run_validator() is True

def place(c,vm,accounts,owner,side,q,p):
    vm.sender=accounts[owner];c.place(side,q,p)

def seal(c,vm,accounts):
    for account in accounts[:3]:vm.sender=account;c.seal()

def conserved(state):
    orders=[o for o in state['orders'] if o['status']=='OPEN']
    assert sum(state['raw'])+sum(state['units'])+sum(o['quantity'] for o in orders if o['side']=='ASK')==sum(state['configuration']['raw_units'])
    assert sum(state['quote'])+sum(o['quantity']*o['limit'] for o in orders if o['side']=='BID')==sum(state['configuration']['quote_credits'])

@pytest.mark.parametrize('case',['cross','gap','screen'])
def test_full_consensus_admission_and_atomic_settlement(direct_deploy,direct_vm,direct_accounts,case):
    c=direct_deploy(str(SOURCE),*args(direct_accounts,case));admit(c,direct_vm,case)
    if case=='cross':
        place(c,direct_vm,direct_accounts,0,'ASK',5,4);place(c,direct_vm,direct_accounts,1,'ASK',4,6);place(c,direct_vm,direct_accounts,2,'BID',7,10)
    elif case=='gap':
        place(c,direct_vm,direct_accounts,0,'ASK',4,9);place(c,direct_vm,direct_accounts,2,'BID',4,7)
    else:
        assert c.get_state()['assessments'][0]['status']=='BLOCKED' and c.get_state()['assessments'][1]['status']=='REVIEW'
        direct_vm.sender=direct_accounts[0]
        with direct_vm.expect_revert('Insufficient admitted inventory'):c.place('ASK',1,1)
        place(c,direct_vm,direct_accounts,2,'BID',5,10)
    conserved(c.get_state());seal(c,direct_vm,direct_accounts);c.clear();s=c.get_state();conserved(s)
    assert s['phase']=='CLEARED' and all(o['status']=='SETTLED' for o in s['orders'])
    if case=='cross':
        assert s['settlement']=={'status':'TRADED','price':6,'volume':7,'imbalance':2,'fills':[[0,5],[1,2],[2,7]],'trades':[{'bid':2,'ask':0,'quantity':5},{'bid':2,'ask':1,'quantity':2}]}
        assert s['quote']==[30,12,58] and s['units']==[1,2,7] and s['raw']==[0,0,0]
        direct_vm.sender=direct_accounts[2];c.transfer_units(0,2);assert c.get_state()['units']==[3,2,5];conserved(c.get_state())
    else:
        assert s['settlement']['status']=='NO_CROSS' and s['settlement']['price']==s['settlement']['volume']==0
        assert s['quote']==[0,0,100]
        assert s['raw']==([6,4,0] if case=='screen' else [0,0,0])

def test_cancellation_refunds_exact_bid_limit_reserve_and_inventory(direct_deploy,direct_vm,direct_accounts):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));admit(c,direct_vm)
    place(c,direct_vm,direct_accounts,0,'ASK',4,9);place(c,direct_vm,direct_accounts,2,'BID',4,7)
    assert c.get_state()['quote']==[0,0,72] and c.get_state()['units']==[2,4,0]
    c.cancel_order(1);direct_vm.sender=direct_accounts[0];c.cancel_order(0)
    assert c.get_state()['quote']==[0,0,100] and c.get_state()['units']==[6,4,0];conserved(c.get_state())
    before=c.get_state()
    with direct_vm.expect_revert('Open order owner only'):c.cancel_order(0)
    assert c.get_state()==before

@pytest.mark.parametrize('sealed_count',[0,1,3])
def test_veto_after_any_number_of_seals_returns_all_escrow(direct_deploy,direct_vm,direct_accounts,sealed_count):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));admit(c,direct_vm)
    place(c,direct_vm,direct_accounts,0,'ASK',5,4);place(c,direct_vm,direct_accounts,2,'BID',7,10)
    for actor in direct_accounts[:sealed_count]:direct_vm.sender=actor;c.seal()
    direct_vm.sender=direct_accounts[1];c.abort();s=c.get_state()
    assert s['phase']=='ABORTED' and s['quote']==[0,0,100] and s['units']==[6,4,0]
    assert all(o['status']=='ABORTED' for o in s['orders']);conserved(s)
    with direct_vm.expect_revert('Market already terminal'):c.abort()

def test_one_side_rule_survives_cancellation(direct_deploy,direct_vm,direct_accounts):
    a=args(direct_accounts);a[4]=[10,0,90];c=direct_deploy(str(SOURCE),*a);admit(c,direct_vm)
    place(c,direct_vm,direct_accounts,0,'ASK',1,1);c.cancel_order(0)
    with direct_vm.expect_revert('One side per participant'):c.place('BID',1,1)

def test_order_owner_and_frozen_seal(direct_deploy,direct_vm,direct_accounts):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));admit(c,direct_vm);place(c,direct_vm,direct_accounts,0,'ASK',1,1)
    direct_vm.sender=direct_accounts[1]
    with direct_vm.expect_revert('Open order owner only'):c.cancel_order(0)
    direct_vm.sender=direct_accounts[0];c.seal();before=c.get_state()
    for method,values in [('place',('ASK',1,1)),('cancel_order',(0,)),('seal',())]:
        with direct_vm.expect_revert('Participant already sealed'):getattr(c,method)(*values)
        assert c.get_state()==before
    with direct_vm.expect_revert('All participants must seal'):c.clear()

def test_twelve_lifetime_order_bound(direct_deploy,direct_vm,direct_accounts):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));admit(c,direct_vm);direct_vm.sender=direct_accounts[0]
    for i in range(12):c.place('ASK',1,1);c.cancel_order(i)
    with direct_vm.expect_revert('Order capacity reached'):c.place('ASK',1,1)
    conserved(c.get_state())

@pytest.mark.parametrize('owner,side,q,p,error',[(0,'ASK',7,1,'Insufficient admitted inventory'),(2,'BID',11,10,'Insufficient quote credits')])
def test_insufficient_reserves_are_atomic(direct_deploy,direct_vm,direct_accounts,owner,side,q,p,error):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));admit(c,direct_vm);before=c.get_state();direct_vm.sender=direct_accounts[owner]
    with direct_vm.expect_revert(error):c.place(side,q,p)
    assert c.get_state()==before

@pytest.mark.parametrize('recipient,quantity',[(0,1),(3,1),(1,0),(1,7)])
def test_native_transfer_bounds_preserve_ownership(direct_deploy,direct_vm,direct_accounts,recipient,quantity):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));admit(c,direct_vm);direct_vm.sender=direct_accounts[0];c.abort();before=c.get_state()
    with direct_vm.expect_revert():c.transfer_units(recipient,quantity)
    assert c.get_state()==before

def test_javascript_ticket_oracle_replays_actual_direct_states(direct_deploy,direct_vm,direct_accounts):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));trace=[];start=c.get_state()
    operations=[(2,'admit',[0]),(2,'admit',[1]),(0,'place',['ASK',5,4]),(1,'place',['ASK',4,6]),(2,'place',['BID',7,10]),
        (2,'cancel_order',[0],'[EXPECTED] Open order owner only'),(0,'seal',[]),(1,'seal',[]),(2,'seal',[]),(2,'clear',[]),(2,'transfer_units',[0,2])]
    for i,op in enumerate(operations):
        owner,method,values,*error=op;direct_vm.sender=direct_accounts[owner];before=c.get_state()
        if method=='admit':mocks(direct_vm,CASES['cross'][values[0]])
        if error:
            with direct_vm.expect_revert(error[0]):getattr(c,method)(*values)
        else:
            getattr(c,method)(*values)
            if method=='admit':assert direct_vm.run_validator() is True
        trace.append({'item':{'label':'direct-'+str(i),'caller':owner,'method':method,'args':values,**({'error':error[0]} if error else {})},'before':before,'after':c.get_state()})
    script="const fs=require('fs'),{initial,replay}=require('./scripts/scenario.cjs'),x=JSON.parse(fs.readFileSync(0,'utf8'));require('assert').deepStrictEqual(x.start,initial('cross','a'.repeat(40),x.accounts));for(const t of x.trace)replay(t.before,t.item,t.after,'cross','a'.repeat(40),x.accounts);"
    result=subprocess.run(['node','-e',script],input=json.dumps({'start':start,'trace':trace,'accounts':start['configuration']['accounts']}),capture_output=True,text=True,cwd=ROOT)
    assert result.returncode==0,result.stderr

@pytest.mark.parametrize('side,q,p',[('BUY',1,1),('BID',0,1),('BID',-1,1),('BID',1,0),('BID',1,101),('BID',True,1),('BID',151,1)])
def test_invalid_order_is_atomic(direct_deploy,direct_vm,direct_accounts,side,q,p):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));direct_vm.sender=direct_accounts[2];before=c.get_state()
    with direct_vm.expect_revert('Invalid limit order'):c.place(side,q,p)
    assert c.get_state()==before

@pytest.mark.parametrize('method,values',[('place',('BID',1,1)),('seal',()),('abort',()),('cancel_order',(0,))])
def test_outsider_cannot_control_participant_book(direct_deploy,direct_vm,direct_accounts,method,values):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));direct_vm.sender=direct_accounts[3]
    with direct_vm.expect_revert('Participant only'):getattr(c,method)(*values)

@pytest.mark.parametrize('index,new_decision',list(itertools.product(range(2),['FAIL','UNKNOWN'])))
def test_validator_compares_each_consequential_decision_exactly(direct_deploy,direct_vm,direct_accounts,index,new_decision):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));mocks(direct_vm,'open-zero');c.admit(0)
    changed=assessment('open-zero');changed['decisions'][index]=new_decision;mocks(direct_vm,'open-zero',answer=changed)
    assert direct_vm.run_validator() is False

@pytest.mark.parametrize('name,lot',[('open-zero',0),('blocked-zero',0),('unknown-one',1)])
def test_validator_audits_positive_negative_and_uncertain_decisions(direct_deploy,direct_vm,direct_accounts,name,lot):
    case='cross' if name=='open-zero' else 'screen';c=direct_deploy(str(SOURCE),*args(direct_accounts,case));mocks(direct_vm,name);c.admit(lot)
    for verdict in [{'checks':[False,True]},{'checks':[True,False]},{'checks':['true',True]},{'checks':[True,True],'extra':True}]:
        mocks(direct_vm,name,audit=verdict);assert direct_vm.run_validator() is False

def test_validator_refetches_full_source(direct_deploy,direct_vm,direct_accounts):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));mocks(direct_vm,'open-zero');c.admit(0)
    mocks(direct_vm,'open-zero',body=b'changed');assert direct_vm.run_validator() is False

@pytest.mark.parametrize('substantively_correct',[True,False])
def test_empty_unknown_anchors_still_require_full_source_audit(direct_deploy,direct_vm,direct_accounts,substantively_correct):
    c=direct_deploy(str(SOURCE),*args(direct_accounts,'screen'))
    answer={'decisions':['UNKNOWN','PASS'],'anchors':[[],[0]]}
    mocks(direct_vm,'unknown-one',answer=answer);c.admit(1)
    mocks(direct_vm,'unknown-one',answer=answer,audit={'checks':[substantively_correct,True]})
    assert direct_vm.run_validator() is substantively_correct
    assert c.get_state()['raw'][1]==4 and c.get_state()['assessments'][1]['status']=='REVIEW'

@pytest.mark.parametrize('change',['extra','missing','enum','anchors','bool','duplicate','empty','wrong-count'])
def test_malformed_model_cannot_convert_raw_inventory(direct_deploy,direct_vm,direct_accounts,change):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));bad=assessment('open-zero');before=c.get_state()
    if change=='extra':bad['extra']=True
    elif change=='missing':bad.pop('anchors')
    elif change=='enum':bad['decisions'][0]='pass'
    elif change=='anchors':bad['anchors'][0]=[99]
    elif change=='bool':bad['anchors'][0]=[True]
    elif change=='duplicate':bad['anchors'][0]=[0,0]
    elif change=='empty':bad['anchors'][0]=[]
    else:bad['decisions'].pop()
    mocks(direct_vm,'open-zero',answer=bad)
    with direct_vm.expect_revert('Invalid lot assessment'):c.admit(0)
    assert c.get_state()==before

@pytest.mark.parametrize('status,body,error',[(503,None,'Document unavailable'),(404,None,'commitment mismatch'),(200,b'changed','commitment mismatch')])
def test_acquisition_failure_is_atomic(direct_deploy,direct_vm,direct_accounts,status,body,error):
    c=direct_deploy(str(SOURCE),*args(direct_accounts));before=c.get_state();mocks(direct_vm,'open-zero',body=body,status=status)
    with direct_vm.expect_revert(error):c.admit(0)
    assert c.get_state()==before

@pytest.mark.parametrize('body',[b'not JSON',b'x'*16001,b'{"market":"voucher-market","lot":0,"lot":0,"clauses":["A sufficiently long document clause."]}',
    b'{"market":"voucher-market","lot":false,"clauses":["A sufficiently long document clause."]}',b'{"market":"other","lot":0,"clauses":["A sufficiently long document clause."]}'])
def test_wrong_committed_document_schema_rejected(direct_deploy,direct_vm,direct_accounts,body):
    a=args(direct_accounts);a[7][0]=hashlib.sha256(body).hexdigest();c=direct_deploy(str(SOURCE),*a);mocks(direct_vm,'open-zero',body=body)
    with direct_vm.expect_revert():c.admit(0)
    assert c.get_state()['raw']==[6,4,0]

@pytest.mark.parametrize('change',['repository','market','duplicate-wallet','zero-wallet','raw-negative','raw-length','zero-quote','criteria','url','hash'])
def test_constructor_rejects_invalid_bounds(direct_deploy,direct_vm,direct_accounts,change):
    a=args(direct_accounts)
    if change=='repository':a[0]='bad'
    elif change=='market':a[1]='bad space'
    elif change=='duplicate-wallet':a[2]=[a[2][0]]*3
    elif change=='zero-wallet':a[2][0]=bytes(20)
    elif change=='raw-negative':a[3][0]=-1
    elif change=='raw-length':a[3].pop()
    elif change=='zero-quote':a[4]=[0,0,0]
    elif change=='criteria':a[5]=['too short']
    elif change=='url':a[6][0]='https://example.com/file'
    else:a[7][0]='bad'
    with direct_vm.expect_revert():direct_deploy(str(SOURCE),*a)

def test_native_address_constructor_encoding(direct_deploy,direct_vm,direct_accounts,monkeypatch):
    from gltest.direct import loader
    original=loader._calldata_roundtrip_args
    def typed(args,kwargs):
        args,kwargs=original(args,kwargs)
        from genlayer import Address
        if len(args)==8:args=(*args[:2],[Address(a) for a in args[2]],*args[3:])
        return args,kwargs
    monkeypatch.setattr(loader,'_calldata_roundtrip_args',typed)
    c=direct_deploy(str(SOURCE),*args(direct_accounts));assert c.get_state()['configuration']['accounts']==['0x'+a.hex() for a in direct_accounts[:3]]

def pure_plan(orders):
    tree=ast.parse(SOURCE.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='clearing_plan')
    scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(SOURCE),'exec'),scope)
    return scope['clearing_plan'](orders)

def exhaustive_oracle(orders):
    active=[o for o in orders if o['status']=='OPEN'];best=None;options=[]
    for price in range(1,max([o['limit'] for o in active if o['side']=='BID'] or [1])+1):
        eligible=[o for o in active if (o['limit']>=price if o['side']=='BID' else o['limit']<=price)]
        demand=sum(o['quantity'] for o in eligible if o['side']=='BID');supply=sum(o['quantity'] for o in eligible if o['side']=='ASK')
        for vector in itertools.product(*(range(o['quantity']+1) for o in eligible)):
            buy=sum(q for o,q in zip(eligible,vector) if o['side']=='BID');sell=sum(q for o,q in zip(eligible,vector) if o['side']=='ASK')
            if not buy or buy!=sell:continue
            score=(-buy,abs(demand-supply),price)
            fill={o['id']:q for o,q in zip(eligible,vector)}
            priority=sorted([o for o in active if o['side']=='BID'],key=lambda o:(-o['limit'],o['id']))+sorted([o for o in active if o['side']=='ASK'],key=lambda o:(o['limit'],o['id']))
            rank=tuple(fill.get(o['id'],0) for o in priority)
            if best is None or score<best:best=score;options=[(rank,fill)]
            elif score==best:options.append((rank,fill))
    fill=max(options,key=lambda item:item[0])[1] if options else {}
    return (best[2] if best else 0,-best[0] if best else 0,[[o['id'],fill.get(o['id'],0)] for o in active])

def check_plan(orders):
    result=pure_plan(orders);price,volume,fills=exhaustive_oracle(orders)
    assert (result['price'],result['volume'],result['fills'])==(price,volume,fills)
    assert sum(t['quantity'] for t in result['trades'])==volume
    for order in orders:
        actual=sum(t['quantity'] for t in result['trades'] if t['bid' if order['side']=='BID' else 'ask']==order['id'])
        assert actual==dict(fills).get(order['id'],0)

def test_every_small_four_order_book_against_exhaustive_feasible_fills():
    for quantities in itertools.product([1,2],repeat=4):
        for prices in itertools.product([1,2,3],repeat=4):
            orders=[{'id':i,'owner':i,'side':'BID' if i<2 else 'ASK','quantity':quantities[i],'limit':prices[i],'status':'OPEN'} for i in range(4)]
            check_plan(orders)

@pytest.mark.parametrize('seed',range(4))
def test_generated_books_with_cancellations_against_exhaustive_oracle(seed):
    rng=random.Random(seed)
    for _ in range(12):
        orders=[{'id':i,'owner':i,'side':'BID' if i<2 else 'ASK','quantity':rng.randint(1,3),'limit':rng.randint(1,5),'status':'CANCELLED' if rng.random()<0.2 else 'OPEN'} for i in range(4)]
        check_plan(orders)
