const $ = id => document.getElementById(id);
async function api(path, data) {
  const response = await fetch('/api/' + path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.error || 'Please sign in to continue.'); error.status=response.status; throw error; }
  return result;
}
function showUser(user) {
  $('login-view').hidden=!!user; $('ask-view').hidden=!user;
  if(user){$('user-name').textContent=user.user_id; $('user-role').textContent=user.role+' · '+user.department;}
}
function clearConversation(){ $('messages').replaceChildren(); $('empty').hidden=false; $('question').value=''; $('ask-error').textContent=''; }
$('login-form').addEventListener('submit',async event=>{
  event.preventDefault(); $('login-button').disabled=true; $('login-error').textContent='';
  try { const result=await api('login',{user_id:$('username').value,password:$('password').value}); clearConversation(); showUser(result.user); $('question').focus(); }
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
api('session').then(result=>showUser(result.user)).catch(()=>showUser(null));
