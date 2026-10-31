const $ = id => document.getElementById(id);
async function api(path, data) {
  const response = await fetch('/api/' + path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.error || 'Please sign in to continue.'); error.status=response.status; throw error; }
  return result;
}
function showUser(user, admin=false) {
  $('admin-panel').hidden=!admin;
  $('login-view').hidden=!!user; $('ask-view').hidden=!user;
  if(user){$('user-name').textContent=user.user_id; $('user-role').textContent=user.role+' · '+user.department;}
}
function clearConversation(){ documents=[]; $('doc-select').replaceChildren(new Option('New document','')); $('doc-content').value=''; $('doc-id').value=''; $('doc-file').value=''; $('admin-status').textContent=''; $('messages').replaceChildren(); $('empty').hidden=false; $('question').value=''; $('ask-error').textContent=''; }
$('login-form').addEventListener('submit',async event=>{
  event.preventDefault(); $('login-button').disabled=true; $('login-error').textContent='';
  try { const result=await api('login',{user_id:$('username').value,password:$('password').value}); clearConversation(); showUser(result.user, result.is_admin); $('question').focus(); }
  catch(error){$('login-error').textContent=error.message;}
  finally{$('password').value=''; $('login-button').disabled=false;}
});
$('logout').addEventListener('click',async()=>{
  try{await api('logout',{}); clearConversation(); showUser(null); $('username').focus();}
  catch(error){$('ask-error').textContent='Sign out failed. Please try again.';}
});
document.querySelectorAll('.suggestion').forEach(button=>button.addEventListener('click',()=>{$('question').value=button.textContent; $('question').focus();}));
$('ask-form').addEventListener('submit',async event=>{
  event.preventDefault(); const question=$('question').value.trim(); if(!question)return;
  $('ask-button').disabled=true; $('logout').disabled=true; $('ask-button').textContent='Searching documents…'; $('ask-error').textContent='';
  try{
    const result=await api('ask',{question}); $('empty').hidden=true;
    const prompt=document.createElement('div'); prompt.className='message question'; prompt.textContent=question;
    const answer=document.createElement('div'); answer.className='message answer'; answer.textContent=result.answer;
    if(result.sources.length){const sources=document.createElement('span'); sources.className='sources'; sources.textContent='Sources: '+result.sources.join(' · '); answer.append(sources);}
    $('messages').append(prompt,answer); $('question').value=''; answer.scrollIntoView({behavior:'smooth',block:'nearest'});
  }catch(error){if(error.status===401){clearConversation();showUser(null);$('login-error').textContent='Your session ended. Please sign in again.';}else{$('ask-error').textContent=error.message;}}
  finally{$('ask-button').disabled=false; $('logout').disabled=false; $('ask-button').textContent='Ask question →';}
});
api('session').then(result=>showUser(result.user, result.is_admin)).catch(()=>showUser(null));

let documents=[];
const template = `---
doc_id: new-document
title: New document
department: Executive
clearance: 3
allowed_roles: []
---

## Overview

Write your document here.
`;
$('doc-content').value=template;
async function refreshDocuments(){
 const result=await api('admin/documents'); documents=result.documents;
 $('doc-select').replaceChildren(new Option('New document',''));
 documents.forEach(doc=>$('doc-select').add(new Option(doc.header.title,doc.header.doc_id)));
 $('admin-status').textContent=result.needs_indexing?'Changes pending: rebuild the index before asking questions.':documents.length+' documents. No pending web changes.';
}
async function adminTask(task){
 const buttons=[...$('admin-panel').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
 $('admin-status').textContent='Working� This may take a few minutes.';
 try{await task();}catch(error){$('admin-status').textContent=error.message;}finally{buttons.forEach(b=>b.disabled=false);}
}
$('load-docs').onclick=()=>adminTask(refreshDocuments);
$('doc-select').onchange=()=>{const doc=documents.find(d=>d.header.doc_id===$('doc-select').value);$('doc-id').value=doc?doc.header.doc_id:'';$('doc-content').value=doc?doc.content:template;};
$('doc-file').onchange=async()=>{const file=$('doc-file').files[0];if(!file)return;if(file.size>200000){$('admin-status').textContent='Maximum document size is 200 KB.';return;}$('doc-content').value=await file.text();$('doc-id').value=file.name.replace(/\.md$/i,'');};
$('save-doc').onclick=()=>adminTask(async()=>{await api('admin/documents',{action:'save',doc_id:$('doc-id').value,content:$('doc-content').value});await refreshDocuments();});
$('delete-doc').onclick=()=>{if(confirm('Delete this document? It will become unavailable after rebuilding.'))adminTask(async()=>{await api('admin/documents',{action:'delete',doc_id:$('doc-id').value});$('doc-id').value='';$('doc-content').value=template;await refreshDocuments();});};
$('reindex-docs').onclick=()=>adminTask(async()=>{const result=await api('admin/documents',{action:'reindex'});await refreshDocuments();$('admin-status').textContent='Index rebuilt: '+result.chunks+' chunks. Questions are ready.';});
