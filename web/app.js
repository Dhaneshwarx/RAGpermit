const $ = id => document.getElementById(id);
let questionHistory = [];
let conversationVersion = 0;
let activeUserId = null;
let requestInFlight = false;
function resetChat() {
  questionHistory = [];
  conversationVersion += 1;
  $('messages').replaceChildren();
  $('empty').hidden = false;
  $('question').value = '';
  $('ask-error').textContent = '';
}

async function api(path, data) {
  const response = await fetch('/api/' + path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.error || 'Please sign in to continue.'); error.status=response.status; throw error; }
  return result;
}
const rolePrompts = {
  'CEO': ['What are the company priorities for January to March 2027?', 'What is our annual revenue target?', 'What is the annual marketing budget?'],
  'HR Manager': ['What are the first-day onboarding tasks?', 'When are probation reviews held?', 'What approvals are needed before issuing an offer?'],
  'Engineer': ['What is the production deployment window?', 'What checks are required before a code change is merged?', 'What is the SEV1 incident acknowledgement target?'],
  'Junior Engineer': ['What is the junior engineer development workflow?', 'When are junior engineer weekly updates due?'],
  'Intern': ['What should an intern complete during the first week?', 'When are intern weekly updates due?', 'What should an intern include in a review request?']
};
function showUser(user, admin=false) {
  const nextUserId = user ? user.user_id : null;
  if (activeUserId !== nextUserId) resetChat();
  activeUserId = nextUserId;
  $('admin-panel').hidden=!admin;
  $('users-panel').hidden=!admin;
  $('login-view').hidden=!!user; $('ask-view').hidden=!user;
  $('question-suggestions').replaceChildren();
  $('signed-in-as').textContent=user ? 'Signed in as '+user.user_id+' · '+user.role+' · '+user.department : '';
  if(user){
    $('user-name').textContent=user.user_id;
    $('user-role').textContent=user.role+' · '+user.department;
    $('role-introduction').textContent='Suggested questions for your '+user.role+' role. Answers depend on the documents available to you.';
    const prompts=rolePrompts[user.role] || ['What products does the company offer?', 'How many casual leave days do employees receive?'];
    prompts.forEach(question=>{
      const button=document.createElement('button');
      button.type='button';button.className='suggestion';button.textContent=question;
      button.addEventListener('click',()=>{$('question').value=question;$('question').focus();});
      $('question-suggestions').append(button);
    });
  }
}
function clearConversation(){ resetChat(); accounts=[]; $('user-select').replaceChildren(new Option('New account','')); $('account-id').value=''; $('account-password').value=''; $('users-status').textContent=''; documents=[]; $('doc-select').replaceChildren(new Option('New document','')); $('doc-content').value=''; $('doc-id').value=''; $('doc-file').value=''; $('admin-status').textContent=''; $('messages').replaceChildren(); $('empty').hidden=false; $('question').value=''; $('ask-error').textContent=''; }
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
$('new-conversation').addEventListener('click', () => {
  if (requestInFlight) return;
  resetChat();
  $('question').focus();
});
$('ask-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (requestInFlight || !activeUserId) return;
  const question = $('question').value.trim();
  if (!question) return;
  const version = conversationVersion;
  const owner = activeUserId;
  requestInFlight = true;
  $('ask-button').disabled = true;
  $('logout').disabled = true;
  $('new-conversation').disabled = true;
  $('ask-button').textContent = 'Searching documents...';
  $('ask-error').textContent = '';
  try {
    const result = await api('ask', {
      question, history: [...questionHistory], history_user_id: owner
    });
    if (version !== conversationVersion || owner !== activeUserId) return;
    questionHistory = [...questionHistory, question].slice(-3);
    $('empty').hidden = true;
    const prompt = document.createElement('div');
    prompt.className = 'message question'; prompt.textContent = question;
    const answer = document.createElement('div');
    answer.className = 'message answer'; answer.textContent = result.answer;
    if (result.sources.length) {
      const sources = document.createElement('span');
      sources.className = 'sources'; sources.textContent = 'Sources: ' + result.sources.join(' · ');
      answer.append(sources);
    }
    $('messages').append(prompt, answer);
    $('question').value = '';
    answer.scrollIntoView({behavior:'smooth', block:'nearest'});
  } catch (error) {
    if (version !== conversationVersion || owner !== activeUserId) return;
    if (error.status === 401 || error.status === 409) {
      clearConversation(); showUser(null);
      $('login-error').textContent = 'Your session ended or account changed. Please sign in again.';
    } else {
      $('ask-error').textContent = error.message;
    }
  } finally {
    requestInFlight = false;
    $('ask-button').disabled = false;
    $('logout').disabled = false;
    $('new-conversation').disabled = false;
    $('ask-button').textContent = 'Ask question →';
  }
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
 $('admin-status').textContent='Working… This may take a few minutes.';
 try{await task();}catch(error){$('admin-status').textContent=error.message;}finally{buttons.forEach(b=>b.disabled=false);}
}
$('load-docs').onclick=()=>adminTask(refreshDocuments);
$('doc-select').onchange=()=>{const doc=documents.find(d=>d.header.doc_id===$('doc-select').value);$('doc-id').value=doc?doc.header.doc_id:'';$('doc-content').value=doc?doc.content:template;};
$('doc-file').onchange=async()=>{const file=$('doc-file').files[0];if(!file)return;if(file.size>200000){$('admin-status').textContent='Maximum document size is 200 KB.';return;}$('doc-content').value=await file.text();$('doc-id').value=file.name.replace(/\.md$/i,'');};
$('save-doc').onclick=()=>adminTask(async()=>{await api('admin/documents',{action:'save',doc_id:$('doc-id').value,content:$('doc-content').value});await refreshDocuments();});
$('delete-doc').onclick=()=>{if(confirm('Delete this document? It will become unavailable after rebuilding.'))adminTask(async()=>{await api('admin/documents',{action:'delete',doc_id:$('doc-id').value});$('doc-id').value='';$('doc-content').value=template;await refreshDocuments();});};
$('reindex-docs').onclick=()=>adminTask(async()=>{const result=await api('admin/documents',{action:'reindex'});await refreshDocuments();$('admin-status').textContent='Index rebuilt: '+result.chunks+' chunks. Questions are ready.';});

let accounts=[];
async function refreshUsers(){
 const result=await api('admin/users');accounts=result.users;
 $('user-select').replaceChildren(new Option('New account',''));
 accounts.forEach(user=>$('user-select').add(new Option(user.user_id+' · '+user.role,user.user_id)));
 $('users-status').textContent=accounts.length+' active accounts.';
}
$('refresh-users').onclick=()=>refreshUsers().catch(error=>$('users-status').textContent=error.message);
$('user-select').onchange=()=>{const user=accounts.find(u=>u.user_id===$('user-select').value);$('account-id').value=user?user.user_id:'';$('account-password').value='';if(user){$('account-role').value=user.role;$('account-department').value=user.department;$('account-clearance').value=user.clearance;}};
document.querySelectorAll('[data-user-action]').forEach(button=>button.onclick=async()=>{
 const action=button.dataset.userAction;
 if(!confirm(action+' account '+$('account-id').value+'? Existing sessions for this account will end.'))return;
 const buttons=[...$('users-panel').querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
 $('users-status').textContent='Updating account...';
 try{await api('admin/users',{action,user_id:$('account-id').value,role:$('account-role').value,department:$('account-department').value,clearance:Number($('account-clearance').value),password:$('account-password').value});if($('account-id').value===$('user-name').textContent && ['reset','revoke'].includes(action)){clearConversation();showUser(null);$('login-error').textContent='Your session ended. Sign in again using your current password.';return;}await refreshUsers();$('users-status').textContent='Account operation completed. Affected users must sign in again.';}
 catch(error){$('users-status').textContent=error.message;}
 finally{$('account-password').value='';buttons.forEach(b=>b.disabled=false);}
});
