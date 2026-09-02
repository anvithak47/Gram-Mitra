
function addMessage(text,who){
 const m=document.getElementById("messages"),row=document.createElement("div");row.className="message "+who;
 if(who==="ai")row.innerHTML='<div class="msg-icon">✦</div><div></div>';else row.innerHTML='<div class="msg-icon">You</div><div></div>';
 row.lastElementChild.textContent=text;m.appendChild(row);m.scrollTop=m.scrollHeight;return row;
}
async function send(text){
 addMessage(text,"me");const thinking=addMessage(localStorage.getItem("gramMitraLang")==="kn"?"ಯೋಚಿಸಲಾಗುತ್ತಿದೆ…":"Thinking…","ai");
 try{const r=await fetch("/api/copilot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text,lang:localStorage.getItem("gramMitraLang")||"en"})});const d=await r.json();thinking.lastElementChild.textContent=d.answer}catch(e){thinking.lastElementChild.textContent=localStorage.getItem("gramMitraLang")==="kn"?"ಈಗ ಪ್ರತಿಕ್ರಿಯಿಸಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.":"I couldn't respond right now. Please try again."}
}
document.addEventListener("DOMContentLoaded",()=>{
 document.getElementById("chatForm")?.addEventListener("submit",e=>{e.preventDefault();const i=document.getElementById("chatText");const t=i.value.trim();if(t){i.value="";send(t)}});
 document.querySelectorAll(".suggestions button").forEach(b=>b.addEventListener("click",()=>send(b.textContent)));
});
