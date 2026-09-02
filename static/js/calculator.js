const fmt=n=>"₹ "+Number(n||0).toLocaleString("en-IN");
const categoryKn={
 "Retail & Services":"ಚಿಲ್ಲರೆ ವ್ಯಾಪಾರ ಮತ್ತು ಸೇವೆಗಳು","Food Processing":"ಆಹಾರ ಸಂಸ್ಕರಣೆ","Agriculture & Allied":"ಕೃಷಿ ಮತ್ತು ಸಂಬಂಧಿತ ಕ್ಷೇತ್ರಗಳು","Manufacturing & Handicrafts":"ಉತ್ಪಾದನೆ ಮತ್ತು ಕರಕುಶಲ",
 "Tourism & Hospitality":"ಪ್ರವಾಸೋದ್ಯಮ ಮತ್ತು ಆತಿಥ್ಯ","Beauty & Personal Care":"ಸೌಂದರ್ಯ ಮತ್ತು ವೈಯಕ್ತಿಕ ಆರೈಕೆ"
};

async function initCategories(){
 const el=document.getElementById("category"); if(!el)return;
 const res=await fetch("/api/categories"); const data=await res.json();
 const selected=el.value;
 Object.keys(data).forEach(k=>el.add(new Option(localStorage.getItem("gramMitraLang")==="kn"?(categoryKn[k]||k):k,k)));
 if(selected)el.value=selected;
}

function refreshCategoryLabels(){
 const el=document.getElementById("category"); if(!el)return;
 Array.from(el.options).forEach(o=>{if(o.value)o.text=localStorage.getItem("gramMitraLang")==="kn"?(categoryKn[o.value]||o.value):o.value});
}

async function runAnalysis(e){
 e.preventDefault();
 const button=e.target.querySelector("button[type=submit]");button.disabled=true;button.textContent=t("analyzing");
 try{
  const payload={district:district.value,taluk:taluk.value,village:village.value,category:category.value,business_idea:document.getElementById("businessIdea")?.value||"",capital:capital.value,address:address.value,latitude:document.getElementById("latitude")?.value||"",longitude:document.getElementById("longitude")?.value||"",lang:localStorage.getItem("gramMitraLang")||"en"};
  const res=await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  if(!res.ok)throw new Error("Analysis failed");
  const result=await res.json();localStorage.setItem("gramMitraReport",JSON.stringify(result));localStorage.setItem("gramMitraAnalysisInput",JSON.stringify(payload));location.href="/report";
 }catch(err){alert(t("something_wrong"));console.error(err)}
 finally{button.disabled=false;button.textContent=t("generate_analysis")}
}

function li(list,values){list.innerHTML="";(values||[]).forEach(v=>{const x=document.createElement("li");x.textContent=v;list.appendChild(x)})}

function renderEmiAndMoratorium(d) {
 const projectCost = parseFloat(d.project_cost || 0);
 const loanAmount = parseFloat(d.loan_90 || (projectCost * 0.9));
 const isKn = localStorage.getItem("gramMitraLang") === "kn";

 const moratoriumMonths = 6;
 const tenureYears = d.repayment_years || 5;
 const totalQuarters = Math.max(1, ((tenureYears * 12) - moratoriumMonths) / 3);

 const annualRate = (parseFloat(d.interest_rate) || 9.5) / 100;
 const quarterlyRate = annualRate / 4;
 const calculatedEmi = loanAmount > 0 
   ? (loanAmount * quarterlyRate * Math.pow(1 + quarterlyRate, totalQuarters)) / (Math.pow(1 + quarterlyRate, totalQuarters) - 1)
   : 0;

 const finalQuarterlyEmi = d.quarterly_payment || Math.round(calculatedEmi);
 const monthlyOps = Math.round((projectCost * 0.15) / 6);
 const workingCapitalBuffer = d.working_capital || (monthlyOps * 6);

 const elMoratorium = document.getElementById("moratoriumPeriod");
 const elTerm = document.getElementById("repaymentTerm");
 const elEmi = document.getElementById("quarterlyEmiVal");
 const elOps = document.getElementById("monthlyOpsCost");
 const elWc = document.getElementById("workingCapitalBuffer");

 if (elMoratorium) elMoratorium.textContent = isKn ? `${moratoriumMonths} ತಿಂಗಳುಗಳು (ಸವಲತ್ತು ಅವಧಿ)` : `${moratoriumMonths} Months (Grace Period)`;
 if (elTerm) elTerm.textContent = isKn ? `${tenureYears} ವರ್ಷಗಳು (${totalQuarters} ಕಂತುಗಳು)` : `${tenureYears} Years (${totalQuarters} Quarters)`;
 if (elEmi) elEmi.textContent = fmt(finalQuarterlyEmi);
 if (elOps) elOps.textContent = fmt(monthlyOps);
 if (elWc) elWc.textContent = fmt(workingCapitalBuffer);
}

function renderReport(){
 const raw=localStorage.getItem("gramMitraReport");if(!raw)return;
 const d=JSON.parse(raw);document.getElementById("emptyReport")?.classList.add("hidden");document.getElementById("reportContent")?.classList.remove("hidden");
 document.getElementById("reportLocation").textContent=[d.location.district,d.location.taluk,d.location.village].filter(Boolean).join(" · ");
 document.getElementById("viability").textContent=d.viability_score+"/10";document.getElementById("summary").textContent=d.summary;
 projectCost.textContent=fmt(d.project_cost);margin.textContent=fmt(d.required_margin);loan.textContent=fmt(d.loan_90);quarterly.textContent=fmt(d.quarterly_payment);
 marketOpportunity.textContent=d.market_opportunity;competition.textContent=d.competitor_density;season.textContent=d.seasonal_analysis;pricing.textContent=d.pricing;marketReach.textContent=d.market_reach;
 workingCapital.textContent=fmt(d.working_capital)+(localStorage.getItem("gramMitraLang")==="kn"?" ಅನ್ನು ಅಂದಾಜು ಕಾರ್ಯನಿಧಿ ಮೀಸಲಾಗಿ ಶಿಫಾರಸು ಮಾಡಲಾಗಿದೆ.":" recommended as an indicative working-capital buffer.");
 scheme.textContent=localStorage.getItem("gramMitraLang")==="kn" ? d.scheme+" · "+d.interest_rate+"% ವಾರ್ಷಿಕ ಬಡ್ಡಿ ಅಂದಾಜು · "+d.repayment_years+" ವರ್ಷಗಳು." : d.scheme+" · "+d.interest_rate+"% p.a. estimate · "+d.repayment_years+" years.";
 li(bestBusinesses,d.best_businesses);li(threats,d.threats);
 
 // Populate the EMI & Moratorium section
 renderEmiAndMoratorium(d);

 const sg=document.getElementById("swotGrid");sg.className="swot-grid";sg.innerHTML="";
 const swotNames={strengths:"Strengths",weaknesses:"Weaknesses",opportunities:"Opportunities",threats:"Threats"};
 const swotKn={strengths:"ಸಾಮರ್ಥ್ಯಗಳು",weaknesses:"ದೌರ್ಬಲ್ಯಗಳು",opportunities:"ಅವಕಾಶಗಳು",threats:"ಅಪಾಯಗಳು"};
 Object.entries(d.swot||{}).forEach(([k,v])=>{const box=document.createElement("div");box.className="swot-item";box.innerHTML=`<h3>${localStorage.getItem("gramMitraLang")==="kn"?(swotKn[k]||k):(swotNames[k]||k)}</h3>`;const ul=document.createElement("ul");v.forEach(x=>{const l=document.createElement("li");l.textContent=x;ul.appendChild(l)});box.appendChild(ul);sg.appendChild(box)});
 
 document.getElementById("pdfBtn")?.addEventListener("click",async()=>{
   const b=document.getElementById("pdfBtn");b.textContent=t("preparing_pdf");b.disabled=true;
   try{const r=await fetch("/download-report",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...d,lang:localStorage.getItem("gramMitraLang")||"en"})});if(!r.ok)throw Error();const blob=await r.blob();const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="Gram_Mitra_Business_Report.pdf";a.click();URL.revokeObjectURL(a.href)}
   catch(e){alert(t("pdf_error"))}finally{b.textContent=t("download_pdf");b.disabled=false}
 });
}

async function refreshReportForLanguage(){
 const raw=localStorage.getItem("gramMitraReport"), input=localStorage.getItem("gramMitraAnalysisInput");
 if(!raw||!input)return renderReport();
 const d=JSON.parse(raw), lang=localStorage.getItem("gramMitraLang")||"en";
 if(d.lang===lang)return renderReport();
 try{
  const payload={...JSON.parse(input),lang};
  const r=await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  if(r.ok){const result=await r.json();localStorage.setItem("gramMitraReport",JSON.stringify(result));renderReport();return;}
 }catch(e){console.error(e)}
 renderReport();
}

document.addEventListener("DOMContentLoaded",()=>{initCategories();document.getElementById("analysisForm")?.addEventListener("submit",runAnalysis);renderReport();window.addEventListener("languageChanged",()=>{refreshCategoryLabels();if(document.getElementById("reportContent")&&!document.getElementById("reportContent").classList.contains("hidden"))refreshReportForLanguage()})});