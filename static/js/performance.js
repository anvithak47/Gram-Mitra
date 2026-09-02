const PERFORMANCE_KEY = "gramMitraPerformanceV1";
const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtMoney = n => "₹" + Number(n || 0).toLocaleString("en-IN", {maximumFractionDigits:0});

function blankRows(){ 
    return months.map(month => ({month, revenue:0, expenses:0, emi:0})); 
}

function loadRows(){
  try {
    const raw = localStorage.getItem(PERFORMANCE_KEY);
    if (!raw) return blankRows();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length !== 12) return blankRows();
    return parsed.map((r,i)=>({
        month: months[i], 
        revenue: Number(r.revenue) || 0, 
        expenses: Number(r.expenses) || 0, 
        emi: Number(r.emi) || 0
    }));
  } catch(e){ 
    return blankRows(); 
  }
}

let rows = loadRows();

function saveRowsToStorage() {
    localStorage.setItem(PERFORMANCE_KEY, JSON.stringify(rows));
}

function createInput(value, field, index){
  const input = document.createElement("input");
  input.type = "number"; 
  input.min = "0"; 
  input.step = "100"; 
  input.value = value || "";
  input.placeholder = "0"; 
  input.dataset.field = field; 
  input.dataset.index = index;
  
  input.addEventListener("input", e => { 
    rows[index][field] = Math.max(0, Number(e.target.value) || 0); 
    updateRowCells(index);
    recalc();
    saveRowsToStorage(); // Auto-save changes immediately
  });
  
  return input;
}

function updateRowCells(index) {
  const tbody = document.getElementById("performanceRows");
  if (!tbody) return;
  const tr = tbody.children[index];
  if (!tr) return;

  const r = rows[index];
  const profit = r.revenue - r.expenses;
  const cash = profit - r.emi;
  const margin = r.revenue > 0 ? (profit / r.revenue) * 100 : 0;

  const p = tr.querySelector(".cell-profit");
  if (p) {
    p.className = "cell-profit " + (profit < 0 ? "negative" : "positive");
    p.textContent = fmtMoney(profit);
  }

  const c = tr.querySelector(".cell-cash");
  if (c) {
    c.className = "cell-cash " + (cash < 0 ? "negative" : "positive");
    c.textContent = fmtMoney(cash);
  }

  const m = tr.querySelector(".cell-margin");
  if (m) {
    m.textContent = r.revenue ? margin.toFixed(1) + "%" : "—";
  }
}

function renderRows(){
  const tbody = document.getElementById("performanceRows"); 
  if (!tbody) return;
  tbody.innerHTML = "";
  
  rows.forEach((r, i) => {
    const profit = r.revenue - r.expenses;
    const cash = profit - r.emi;
    const margin = r.revenue > 0 ? (profit / r.revenue) * 100 : 0;
    
    const tr = document.createElement("tr");
    
    const month = document.createElement("td"); 
    month.innerHTML = `<strong>${r.month}</strong>`; 
    tr.appendChild(month);
    
    ["revenue", "expenses", "emi"].forEach(field => {
        const td = document.createElement("td");
        td.appendChild(createInput(r[field], field, i));
        tr.appendChild(td);
    });
    
    const p = document.createElement("td"); 
    p.className = "cell-profit " + (profit < 0 ? "negative" : "positive"); 
    p.textContent = fmtMoney(profit); 
    tr.appendChild(p);
    
    const c = document.createElement("td"); 
    c.className = "cell-cash " + (cash < 0 ? "negative" : "positive"); 
    c.textContent = fmtMoney(cash); 
    tr.appendChild(c);
    
    const m = document.createElement("td"); 
    m.className = "cell-margin";
    m.textContent = r.revenue ? margin.toFixed(1) + "%" : "—"; 
    tr.appendChild(m);
    
    tbody.appendChild(tr);
  });
}

function recalc(){
  const totalRevenue = rows.reduce((s,r) => s + r.revenue, 0);
  const totalExpenses = rows.reduce((s,r) => s + r.expenses, 0);
  const totalEmi = rows.reduce((s,r) => s + r.emi, 0);
  const totalProfit = totalRevenue - totalExpenses;
  const totalCash = totalProfit - totalEmi;

  const revElem = document.getElementById("annualRevenue");
  const expElem = document.getElementById("annualExpenses");
  const profElem = document.getElementById("annualProfit");
  const cashElem = document.getElementById("annualCash");
  
  if (revElem) revElem.textContent = fmtMoney(totalRevenue);
  if (expElem) expElem.textContent = fmtMoney(totalExpenses);
  if (profElem) profElem.textContent = fmtMoney(totalProfit);
  if (cashElem) cashElem.textContent = fmtMoney(totalCash);
  
  const active = rows.filter(r => r.revenue > 0 || r.expenses > 0 || r.emi > 0);
  const trendElem = document.getElementById("revenueTrend");
  if (trendElem) {
    trendElem.textContent = active.length 
        ? `${active.length} month${active.length === 1 ? '' : 's'} entered` 
        : "Enter monthly figures";
  }

  renderChart(); 
  renderInsight(totalRevenue, totalExpenses, totalEmi, totalProfit, totalCash, active.length);
}

function renderChart(){
  const chart = document.getElementById("performanceChart"); 
  if (!chart) return;
  chart.innerHTML = "";
  
  const max = Math.max(1, ...rows.map(r => Math.max(r.revenue, r.revenue - r.expenses)));
  
  rows.forEach(r => {
    const col = document.createElement("div"); 
    col.className = "chart-col";
    
    const rev = document.createElement("div"); 
    rev.className = "chart-bar revenue"; 
    rev.style.height = ((r.revenue / max) * 100) + "%"; 
    rev.title = `${r.month}: Revenue ${fmtMoney(r.revenue)}`;
    
    const profit = document.createElement("div"); 
    profit.className = "chart-bar profit"; 
    profit.style.height = ((Math.max(0, r.revenue - r.expenses) / max) * 100) + "%"; 
    profit.title = `${r.month}: Profit ${fmtMoney(r.revenue - r.expenses)}`;
    
    const bars = document.createElement("div"); 
    bars.className = "chart-bars"; 
    bars.append(rev, profit);
    
    const label = document.createElement("span"); 
    label.textContent = r.month; 
    
    col.append(bars, label); 
    chart.appendChild(col);
  });
}

function renderInsight(revenue, expenses, emi, profit, cash, active){
  const title = document.getElementById("insightTitle");
  const text = document.getElementById("insightText");
  if (!title || !text) return;

  if(!active){
    title.textContent = "Add your monthly figures to begin.";
    text.textContent = "Once you enter revenue, expenses and EMI, this section will summarize profitability, cash flow and repayment pressure.";
    return;
  }
  if(revenue <= 0){
    title.textContent = "Revenue is not recorded yet.";
    text.textContent = "Enter actual sales/revenue for the months you want to track.";
    return;
  }

  const margin = (profit / revenue) * 100;
  const emiPressure = profit > 0 ? (emi / profit) * 100 : 100;

  if(cash < 0){
    title.textContent = "⚠️ Cash flow needs attention.";
    text.textContent = `Your recorded figures show ${fmtMoney(Math.abs(cash))} of negative cash after EMI across the entered period. Review expenses, pricing and repayment terms before taking on additional debt.`;
  } else if(emiPressure > 40){
    title.textContent = "🟡 Monitor repayment pressure.";
    text.textContent = `EMI uses about ${emiPressure.toFixed(1)}% of profit before EMI across the entered period. Keep a working-capital buffer and monitor monthly cash flow.`;
  } else if(margin >= 20){
    title.textContent = "🟢 Healthy operating margin in the entered data.";
    text.textContent = `Your recorded operating profit margin is ${margin.toFixed(1)}%. Continue tracking monthly revenue and expenses to identify seasonal changes.`;
  } else {
    title.textContent = "🟡 Profitability can be improved.";
    text.textContent = `Your recorded operating profit margin is ${margin.toFixed(1)}%. Gram Mitra suggests reviewing pricing, variable costs and monthly sales volume.`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderRows();
  recalc();

  const saveBtn = document.getElementById("savePerformanceBtn");
  if (saveBtn) {
    saveBtn.addEventListener("click", () => {
      saveRowsToStorage();
      saveBtn.textContent = "Saved ✓";
      setTimeout(() => saveBtn.textContent = "Save performance", 1200);
    });
  }

  const clearBtn = document.getElementById("clearPerformanceBtn");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if(confirm("Clear all monthly performance figures?")){
        rows = blankRows();
        localStorage.removeItem(PERFORMANCE_KEY);
        renderRows();
        recalc();
      }
    });
  }

  const loadBtn = document.getElementById("loadAnalysisBtn");
  if (loadBtn) {
    loadBtn.addEventListener("click", () => {
      try{
        const report = JSON.parse(localStorage.getItem("gramMitraReport") || "null");
        if(!report || !report.quarterly_payment){
            alert("Run Business Analysis first to get an indicative repayment estimate.");
            return;
        }
        const monthly = Number(report.quarterly_payment) / 3;
        rows.forEach(r => { if(r.emi === 0) r.emi = Math.round(monthly); });
        saveRowsToStorage();
        renderRows();
        recalc();
      } catch(e){
        alert("The latest analysis could not be read.");
      }
    });
  }
});