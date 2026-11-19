"""Contract tests for the optional, same-origin case navigation controller."""
import ast
import json
from pathlib import Path
import shutil
import subprocess

import pytest


SOURCE = Path(__file__).parents[1] / 'src/alfa_document_intelligence/local_intake_app.py'


def _script():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    for item in tree.body:
        if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_CASE_NAVIGATION_SCRIPT' for t in item.targets):
            return ast.literal_eval(item.value)
    raise AssertionError('case navigation script not found')


HARNESS = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {script, scenario} = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const handlers = {}, winHandlers = {}, pending = [];
let edited = false;
const location = {origin:'http://127.0.0.1:7777', pathname:'/', search:'', hash:'', assigned:[],
  assign(path){this.assigned.push(path)}, reload(){this.assigned.push('reload')}, replace(path){this.assigned.push('replace:'+path)},
  get href(){return this.origin+this.pathname+this.search+this.hash}};
const history = {pushes:[], pushState(_,__,path){this.pushes.push(path);location.pathname=path}};
function makeMain(id){return {id, removedScripts:0, focused:false,
  querySelectorAll(s){return s==='script'?[{hasAttribute(name){return id!=='unsupported' && name==='data-ocr2-navigation'},remove(){}}]:[]},
  querySelector(s){return s==='h1'?{setAttribute(){},focus(){}}:null},
  setAttribute(){},removeAttribute(){},replaceWith(other){document.main=other}}}
const document = {main:makeMain('home'), title:'Home',
  addEventListener(name, fn){handlers[name]=fn}, querySelector(s){return s==='main'?this.main:null},
  querySelectorAll(){return scenario==='unsaved-input'||edited?[{type:'text',value:'edited',defaultValue:''}]:[]}};
const window = {addEventListener(name,fn){winHandlers[name]=fn}};
const parser = class {parseFromString(text){return {title:'Page '+text,querySelector(s){return s==='main'?makeMain(text):null}}}};
const fetch = (path, options) => new Promise((resolve,reject)=>pending.push({path,options,resolve,reject}));
const response = (path, body, options={}) => ({ok:options.ok!==false, redirected:!!options.redirected,
  url:options.url||location.origin+path,
  headers:{get(name){return name.toLowerCase()==='content-type'?(options.type||'text/html; charset=utf-8'):(name.toLowerCase()==='content-length'?'120':null)}},
  text:async()=>body});
const flush = () => new Promise(resolve=>setImmediate(resolve));
const click = (href, overrides={}) => {
  const a={getAttribute(n){return n==='href'?href:null},hasAttribute(){return false},target:''};
  const e={target:{closest(){return a}},button:0,defaultPrevented:false,
    preventDefault(){this.defaultPrevented=true},...overrides};
  handlers.click(e); return e;
};
const Controller = scenario==='controller-unavailable' ? undefined : AbortController;
vm.runInNewContext(script,{document,window,location,history,fetch,DOMParser:parser,AbortController:Controller,URL,console});
(async()=>{
  if(scenario==='success'){
    assert.equal(click('/cases').defaultPrevented,true); assert.equal(pending.length,1);
    pending[0].resolve(response('/cases','verified')); await flush(); await flush();
    assert.equal(document.main.id,'verified'); assert.equal(location.pathname,'/cases');
    assert.deepEqual(history.pushes,['/cases']); assert.equal(document.title,'Page verified');
  } else if(scenario==='stale-click'){
    click('/cases'); click('/cases'); assert.equal(pending.length,2);
    assert.equal(pending[0].options.signal.aborted,true);
    pending[1].resolve(response('/cases','new')); await flush(); await flush();
    pending[0].resolve(response('/cases','old')); await flush(); await flush();
    assert.equal(document.main.id,'new'); assert.deepEqual(history.pushes,['/cases']);
  } else if(scenario==='back-during-request'){
    click('/cases'); location.pathname='/cases'; winHandlers.popstate();
    assert.equal(pending.length,1); assert.equal(pending[0].options.signal.aborted,true);
    assert.deepEqual(location.assigned,['replace:http://127.0.0.1:7777/cases']);
    pending[0].resolve(response('/cases','stale')); await flush(); await flush();
    assert.equal(document.main.id,'home'); assert.deepEqual(history.pushes,[]);
  } else if(scenario==='bad-response'){
    click('/cases'); pending[0].resolve(response('/cases','bad',{redirected:true,url:'http://evil.invalid/'}));
    await flush(); await flush(); assert.deepEqual(location.assigned,['/cases']); assert.equal(document.main.id,'home');
  } else if(scenario==='bad-content-type'){
    click('/cases'); pending[0].resolve(response('/cases','bad',{type:'application/json'}));
    await flush(); await flush(); assert.deepEqual(location.assigned,['/cases']); assert.equal(document.main.id,'home');
  } else if(scenario==='unsupported-script'){
    click('/cases'); pending[0].resolve(response('/cases','unsupported'));
    await flush(); await flush(); assert.deepEqual(location.assigned,['/cases']); assert.equal(document.main.id,'home');
  } else if(scenario==='oversized-body'){
    click('/cases'); pending[0].resolve(response('/cases','x'.repeat(4194305)));
    await flush(); await flush(); assert.deepEqual(location.assigned,['/cases']); assert.equal(document.main.id,'home');
  } else if(scenario==='modified-click'){
    assert.equal(click('/cases',{ctrlKey:true}).defaultPrevented,false); assert.equal(pending.length,0);
  } else if(scenario==='unsaved-input'){
    assert.equal(click('/cases').defaultPrevented,false); assert.equal(pending.length,0);
  } else if(scenario==='edit-during-fetch'){
    click('/cases'); edited=true; pending[0].resolve(response('/cases','new'));
    await flush(); await flush(); assert.equal(document.main.id,'home');
    assert.deepEqual(history.pushes,[]); assert.deepEqual(location.assigned,[]);
  } else if(scenario==='edit-during-failed-fetch'){
    click('/cases'); edited=true; pending[0].reject(new Error('network error'));
    await flush(); await flush(); assert.equal(document.main.id,'home');
    assert.deepEqual(history.pushes,[]); assert.deepEqual(location.assigned,[]);
  } else if(scenario==='history-query'){
    click('/cases'); location.pathname='/cases'; location.hash='#details'; winHandlers.popstate();
    assert.equal(pending[0].options.signal.aborted,true);
    assert.equal(pending.length,1); assert.deepEqual(location.assigned,['replace:http://127.0.0.1:7777/cases#details']);
    pending[0].resolve(response('/cases','stale')); await flush(); await flush();
    assert.equal(document.main.id,'home');
  } else if(scenario==='controller-unavailable'){
    click('/cases'); await flush(); assert.deepEqual(location.assigned,['/cases']);
    assert.equal(pending.length,0); assert.equal(document.main.id,'home');
  } else throw Error('unknown scenario');
})().catch(e=>{console.error(e);process.exitCode=1});
'''


@pytest.mark.parametrize('scenario', ['success', 'stale-click', 'back-during-request', 'bad-response', 'bad-content-type', 'unsupported-script', 'oversized-body', 'modified-click', 'history-query', 'controller-unavailable', 'unsaved-input', 'edit-during-fetch', 'edit-during-failed-fetch'])
def test_case_navigation_contract(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable')
    result = subprocess.run([node, '-e', HARNESS], input=json.dumps({'script': _script(), 'scenario': scenario}),
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr or result.stdout
