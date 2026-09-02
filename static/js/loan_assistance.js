const laFmt = n => "₹ " + Number(n || 0).toLocaleString("en-IN");
function laEscape(s){ const d=document.createElement("div"); d.textContent=s ?? ""; return d.innerHTML; }
function laList(items, cls="") { return (items||[]).map(x=>`<div class="info-row ${cls}">${laEscape(x)}</div>`).join(""); }

function renderLoanAssistance(d){
  const resSection = document.getElementById("loanResult");
  if (resSection) {
    resSection.style.display = "block"; // Overrides style="display: none;" from HTML template
    resSection.classList.remove("hidden");
  }

  document.getElementById("laSchemeName").textContent = d.scheme ? d.scheme.name : "Loan Scheme";
  document.getElementById("laEligibility").textContent = d.eligibility_message || "";
  document.getElementById("laReadiness").textContent = (d.readiness_score || 0) + "%";
  document.getElementById("laCost").textContent = laFmt(d.project_cost);
  document.getElementById("laMargin").textContent = laFmt(d.required_margin);
  document.getElementById("laLoan").textContent = laFmt(d.indicative_finance);
  document.getElementById("laRate").textContent = d.scheme ? d.scheme.beneficiary_rate + "% p.a." : "N/A";
  
  document.getElementById("laChannels").innerHTML = laList(d.scheme ? d.scheme.channels : [], "tag-row");
  document.getElementById("laDocs").innerHTML = laList(d.documents);
  document.getElementById("laBenefits").innerHTML = laList(d.benefits);
  document.getElementById("laMissing").innerHTML = laList(d.missing_guidance);
  
  document.getElementById("laRoadmap").innerHTML = (d.roadmap || []).map((x, i) => 
    `<div class="road-step"><em>${i + 1}</em><div><b>${laEscape(x.title)}</b><p>${laEscape(x.text)}</p></div></div>`
  ).join("");
  
  if (resSection) {
    resSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("loanAssistForm"); 
  if (!form) return;

  // Clear stale cached results on load to keep form view clean
  localStorage.removeItem("gramMitraLoanAssistance");

  form.addEventListener("submit", async e => {
    e.preventDefault();
    const btn = form.querySelector("button[type=submit]"); 
    btn.disabled = true; 
    btn.textContent = "Checking…";

    try {
      const payload = {
        category: document.getElementById("laCategory").value, 
        income: Number(document.getElementById("laIncome").value || 0), 
        woman: document.getElementById("laWoman").checked, 
        pwd: document.getElementById("laPwd").checked, 
        senior: document.getElementById("laSenior").checked, 
        project_cost: Number(document.getElementById("laProjectCost").value || 0), 
        district: document.getElementById("laDistrict").value.trim()
      };
      
      const r = await fetch("/api/loan-assistance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      const d = await r.json(); 
      if (!r.ok) throw new Error(d.error || "Unable to calculate");
      
      renderLoanAssistance(d); 
      localStorage.setItem("gramMitraLoanAssistance", JSON.stringify(d));
    } catch (err) { 
      alert(err.message || "Something went wrong. Please try again."); 
    } finally {
      btn.disabled = false;
      btn.textContent = "Check Loan Assistance →";
    }
  });
});