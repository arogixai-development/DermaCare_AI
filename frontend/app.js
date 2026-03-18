// Removed module import to allow native offline file:// execution
// We safely rely on storage.js being loaded alongside app.js natively.

class AppController {
  constructor() {
    this.currentScreen = 'screen-dashboard';
    this.currentCasePayload = null;
    this.rawAIResponse = "";
    this.currentDrugAnalysis = "";

    // List of valid screens to prevent invalid navigation
    this.validScreens = [
      'screen-dashboard',
      'screen-intake',
      'screen-assessment',
      'screen-diagnosis',
      'screen-treatment',
      'screen-soap',
      'screen-history',
      'screen-case-details',
      'screen-drug-checker',
      'screen-settings'
    ];
    
    this.historyCache = [];
    this.currentViewCaseId = null;

    // Initialize metrics on load
    this.updateDashboardMetrics();
    this.initNetworkMonitoring();
  }

  initNetworkMonitoring() {
    const el = document.getElementById('network-status');
    const updateStatus = async () => {
      if (!el) return;
      
      // First check navigator.onLine for browser connectivity
      if (!navigator.onLine) {
        el.innerHTML = 'Status: 🔴 Network Offline';
        el.style.color = 'var(--error-text)';
        return;
      }
      
      // Then check backend reachability
      try {
        const hostname = window.location.hostname || "127.0.0.1";
        const ping = await fetch(`http://${hostname}:8000/health`, { method: 'GET', signal: AbortSignal.timeout(2000) });
        if (ping.ok) {
          el.innerHTML = 'Status: 🟢 Online (AI Ready)';
          el.style.color = '';
        } else {
          throw new Error('Backend error');
        }
      } catch (err) {
        el.innerHTML = 'Status: 🟠 AI Backend Offline';
        el.style.color = '#f59e0b';
      }
    };
    
    window.addEventListener('online', updateStatus);
    window.addEventListener('offline', updateStatus);
    
    // Heartbeat every 10 seconds
    setInterval(updateStatus, 10000);
    updateStatus();
  }

  // --- HTML DOM Navigation (Core Logic) ---
  showScreen(targetId, e) {
    const event = e || window.event;
    if (event && event.type === 'click') {
      // Prevent hashtag jumping or form triggers
      if (typeof event.preventDefault === 'function') event.preventDefault();
      if (typeof event.stopPropagation === 'function') event.stopPropagation();
    }
    if (!this.validScreens.includes(targetId)) {
      console.warn(`Invalid screen ID ignored: ${targetId}`);
      return; 
    }

    const previousActive = document.querySelector('.screen.active');
    const targetEl = document.getElementById(targetId);
    
    if (targetEl) {
      targetEl.classList.add('active');
      if (previousActive && previousActive !== targetEl) {
        previousActive.classList.remove('active');
      }
    }
    
    this.currentScreen = targetId;

    if (targetId === 'screen-intake') {
      this.clearForms();
    }

    this.updateSidebarActive(targetId);
    this.updateStepper(targetId);
    
    if (targetId === 'screen-dashboard') {
      this.updateDashboardMetrics();
    }
  }

  updateStepper(screenId) {
    const stepper = document.getElementById('workflow-stepper');
    const steps = ['screen-intake', 'screen-assessment', 'screen-diagnosis', 'screen-treatment', 'screen-soap'];
    
    if (steps.includes(screenId)) {
      stepper.style.display = 'flex';
      const currentIndex = steps.indexOf(screenId);
      
      steps.forEach((s, i) => {
        const stepEl = document.getElementById(`step-${i + 1}`);
        stepEl.classList.remove('active', 'completed');
        if (i < currentIndex) stepEl.classList.add('completed');
        if (i === currentIndex) stepEl.classList.add('active');
      });
    } else {
      stepper.style.display = 'none';
    }
  }

  startNewDiagnosis(e) {
    const event = e || window.event;
    if (event && typeof event.preventDefault === 'function') event.preventDefault();
    this.currentCasePayload = null;
    this.rawAIResponse = "";
    this.showScreen('screen-intake');
  }

  async runDemoCase(e) {
    const event = e || window.event;
    if (event && event.preventDefault) event.preventDefault();

    // Start fresh
    this.startNewDiagnosis();

    // Fill Step 1: Intake
    await new Promise(r => setTimeout(r, 600)); // Cinematic delay
    document.getElementById('patient_age').value = "42";
    document.getElementById('geographic_region').value = "South India";
    document.getElementById('skin_phototype').value = "Type IV";
    document.getElementById('occupation').value = "Software Engineer";

    // Fill Step 2: Assessment
    this.showScreen('screen-assessment');
    await new Promise(r => setTimeout(r, 600));
    document.getElementById('complaint').value = "Chronic scaling plaque on elbows";
    document.getElementById('lesion').value = "Symmetrical erythematous plaques with silvery scales, sharply demarcated, 5cm diameters.";
    document.getElementById('symptoms').value = "Mild itch, Auspitz sign positive when scales removed.";
    document.getElementById('tests').value = "Dermoscopy shows uniform red dots (tortuous capillaries).";

    // Trigger AI
    await new Promise(r => setTimeout(r, 800));
    this.analyzeCase();
  }

  updateSidebarActive(screenId) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    
    if (screenId === 'screen-dashboard') {
      document.getElementById('nav-dashboard')?.classList.add('active');
    } else if (['screen-intake', 'screen-assessment', 'screen-diagnosis', 'screen-treatment', 'screen-soap'].includes(screenId)) {
      document.getElementById('nav-new')?.classList.add('active');
    } else if (['screen-history', 'screen-case-details'].includes(screenId)) {
      document.getElementById('nav-history')?.classList.add('active');
    } else if (screenId === 'screen-drug-checker') {
      document.getElementById('nav-drug')?.classList.add('active');
    } else if (screenId === 'screen-settings') {
      document.getElementById('nav-settings')?.classList.add('active');
    } else if (screenId === 'nav-demo') {
      document.getElementById('nav-demo')?.classList.add('active');
    }
  }

  goBack(targetId, e) {
    const event = e || window.event;
    if (event && typeof event.preventDefault === 'function') event.preventDefault();
    this.showScreen(targetId);
  }

  goNext(targetId, e) {
    const event = e || window.event;
    if (event && typeof event.preventDefault === 'function') event.preventDefault();
    if (this.currentScreen === 'screen-intake') {
      if (!this.validateInputs(['patient_age', 'geographic_region'])) return;
    }
    this.showScreen(targetId);
  }

  // Highlights required fields missing
  validateInputs(fieldIds) {
    let isValid = true;
    fieldIds.forEach(id => {
      const el = document.getElementById(id);
      if (!el.value.trim()) {
        el.classList.add('input-error');
        isValid = false;
      } else {
        el.classList.remove('input-error');
      }
      el.addEventListener('input', () => el.classList.remove('input-error'), { once: true });
    });
    
    if (!isValid) alert("Please complete all required fields highlighted in red.");
    return isValid;
  }

  // --- HTML Sanitizer ---
  sanitizeEscape(str) {
      if (!str) return "";
      if (typeof str !== 'string') str = String(str);
      return str.replace(/[&<>"']/g, function(m) {
          switch (m) {
              case '&': return '&amp;';
              case '<': return '&lt;';
              case '>': return '&gt;';
              case '"': return '&quot;';
              case "'": return '&#039;';
          }
      });
  }

  // Converts raw AI prompt text into HTML Lists and Headers
  formatStructuredHTML(text) {
      const escapedText = this.sanitizeEscape(text);
      
      // Basic structured formatting: detect standard prompt headers (e.g. "Possible Diagnoses:")
      // and turn them into <h4> tags. Map dashed lines into simple unordered lists.
      
      const lines = escapedText.split('\n');
      let html = '';
      let inList = false;

       for (let i = 0; i < lines.length; i++) {
           let line = lines[i].trim();
           if (line === '') continue;

           // Detect if it's a list item BEFORE stripping noise
           const isListItem = line.startsWith('-') || line.startsWith('*');
           
           // Aggressively strip bolding stars (**) and leftover markdown residue
           line = line.replace(/\*\*/g, '').trim();

           // Skip noise lines that are just markdown residue or repeating headers
           if (line === '*' || line === '-' || line === '---' || /^[A-Z\s]{10,}:?$/.test(line)) continue;

           if (line.endsWith(':')) {
               if (inList) { html += '</ul>'; inList = false; }
               html += `<h4>${line}</h4>`;
           } else if (isListItem) {
               // Remove list marker for content but keep list structure
               const content = line.replace(/^[-*]\s?/, '').replace(/\*$/, '').trim();
               if (content !== '') {
                    if (!inList) { html += '<ul>'; inList = true; }
                    html += `<li>${content}</li>`;
               }
           } else {
               if (inList) { html += '</ul>'; inList = false; }
               html += `<p>${line}</p>`;
           }
       }
      
      if (inList) html += '</ul>';
      return html;
  }

  // --- API Analysis ---
  async analyzeCase() {
    if (!this.validateInputs(['complaint'])) return;

    // Preserve existing ID or other metadata if present
    const existingData = this.currentCasePayload || {};
    
    this.currentCasePayload = {
      ...existingData,
      case_id: existingData.case_id || 'case_' + Date.now(),
      timestamp: existingData.timestamp || new Date().toISOString(),
      patient_age: parseInt(document.getElementById('patient_age').value),
      geographic_region: document.getElementById('geographic_region').value,
      skin_phototype: document.getElementById('skin_phototype').value || "UNKNOWN",
      occupation: document.getElementById('occupation').value || "Unknown",
      complaint: document.getElementById('complaint').value,
      lesion: document.getElementById('lesion').value || "None provided",
      symptoms: document.getElementById('symptoms').value || "None stated",
      tests: document.getElementById('tests').value || "None",
    };

    const btn = document.getElementById('analyze-btn');
    const loading = document.getElementById('loading');
    const statusText = document.getElementById('analysis-status');
    const progressBar = document.getElementById('analysis-progress');
    
    btn.disabled = true;
    loading.style.display = 'flex';
    progressBar.style.width = '0%';
    
    const statusMessages = [
      { text: "Processing patient data...", progress: 20 },
      { text: "Evaluating possible diagnoses...", progress: 45 },
      { text: "Generating clinical reasoning...", progress: 70 },
      { text: "Finalizing recommendation...", progress: 90 }
    ];

    let messageIndex = 0;
    const intervalId = setInterval(() => {
      if (messageIndex < statusMessages.length) {
        statusText.innerText = statusMessages[messageIndex].text;
        progressBar.style.width = statusMessages[messageIndex].progress + '%';
        messageIndex++;
      }
    }, 2000);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 min timeout

    try {
      const hostname = window.location.hostname || "127.0.0.1";
      const apiEndpoint = `http://${hostname}:8000/diagnosis`;

      const res = await fetch(apiEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.currentCasePayload),
        signal: controller.signal
      });
      
      if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.detail || `Server error: ${res.status}`);
      }

      const data = await res.json();
      
      // Map the new structured JSON fields to our state
      // Expected fields: { diagnoses: [], reasoning: "", soap: "", triage: "" }
      this.currentCasePayload.diagnoses_list = data.diagnoses || [];
      this.currentCasePayload.reasoning = data.reasoning || "";
      this.currentCasePayload.soap_note = data.soap || "";
      this.currentCasePayload.triage = data.triage || "Routine";
      this.currentCasePayload.tests_list = data.tests || [];
      this.currentCasePayload.referral_list = data.referral || [];
      this.currentCasePayload.treatment_list = data.treatment || [];
      
      this.currentCasePayload.status = "completed";

      // Display the results
      this.parseAIResponse(data);
      this.showScreen('screen-diagnosis');

    } catch (error) {
      console.error("Analysis Failed:", error);
      
      let errorMsg = error.message;
      if (error.name === 'AbortError') errorMsg = "AI processing timed out. Please retry.";

      // Show error in the UI with a Retry button
      const resultDiv = document.getElementById('diagnosis-result');
      resultDiv.innerHTML = `
        <div class="clinical-alert alert-danger" style="background:var(--error-bg); color:var(--error-text); padding:1rem; border-radius:8px;">
            <p><strong>⚠️ Analysis Failed</strong></p>
            <p>${this.sanitizeEscape(errorMsg)}</p>
            <button onclick="window.app.analyzeCase()" class="btn btn-primary btn-small" style="margin-top:1rem; background:var(--error-text);">Retry Analysis</button>
        </div>
      `;
      
      document.getElementById('diagnosis-fallback').style.display = 'block';
      document.getElementById('diagnosis-structured').style.display = 'none';
      
      this.currentCasePayload.status = "pending";
      this.showScreen('screen-diagnosis');
      
    } finally {
      clearInterval(intervalId);
      clearTimeout(timeoutId);
      btn.disabled = false;
      loading.style.display = 'none';
      
      if (this.currentCasePayload) {
         await saveCase(this.currentCasePayload);
      }
    }
  }

  parseAIResponse(data) {
    if (!data || typeof data !== 'object') return;

    // Use direct JSON mapping instead of text parsing
    const diagnoses = Array.isArray(data.diagnoses) ? data.diagnoses.join('\n') : "";
    const reasoning = data.reasoning || "";
    const tests = Array.isArray(data.tests) ? data.tests.join('\n') : "";
    const referral = Array.isArray(data.referral) ? data.referral.join('\n') : "";
    const treatment = Array.isArray(data.treatment) ? data.treatment.join('\n') : "";
    const triageValue = (data.triage || "Routine").toLowerCase();

    // Map to UI boxes using formatStructuredHTML
    document.getElementById('box-diagnoses').innerHTML = this.formatStructuredHTML(diagnoses || "None specified");
    document.getElementById('box-reasoning').innerHTML = this.formatStructuredHTML(reasoning || "None specified");
    document.getElementById('box-tests').innerHTML = this.formatStructuredHTML(tests || "None specified");
    document.getElementById('box-referral').innerHTML = this.formatStructuredHTML(referral || "None specified");
    
    // Update Treatment result
    document.getElementById('treatment-result').innerHTML = this.formatStructuredHTML(treatment || "No treatment suggestions available.");

    // Update SOAP result for immediate visibility
    const soapResult = document.getElementById('soap-result');
    if (soapResult && data.soap) {
        soapResult.innerHTML = this.formatStructuredHTML(data.soap);
    }

    // Handle Triage Alert Display
    const triageBox = document.getElementById('triage-alert');
    const triageText = document.getElementById('triage-text');
    
    if (triageBox && triageText) {
        triageBox.style.display = 'flex';
        triageText.innerText = data.triage;
        
        // Fitzpatrick-aware styling (simplified logic for example)
        triageBox.className = 'clinical-alert'; // reset
        if (triageValue.includes('urgent') || triageValue.includes('high')) {
            triageBox.classList.add('alert-danger');
            triageBox.style.background = '#fee2e2';
            triageBox.style.color = '#b91c1c';
            triageBox.style.borderLeft = '4px solid #ef4444';
        } else if (triageValue.includes('moderate') || triageValue.includes('medium')) {
            triageBox.classList.add('alert-warning');
        } else {
            triageBox.classList.add('alert-info');
        }
    }

    document.getElementById('diagnosis-fallback').style.display = 'none';
    document.getElementById('diagnosis-structured').style.display = 'block';
  }

  // --- Data & State Management ---
  clearForms() {
    document.querySelectorAll('input, select, textarea').forEach(el => {
       if (el.id !== 'skin_phototype') el.value = "";
    });
    this.currentCasePayload = null;
    this.rawAIResponse = "";
  }

  async prepareSOAP() {
    this.showScreen('screen-soap');
    const loading = document.getElementById('soap-loading');
    const resultBox = document.getElementById('soap-result');
    
    // If we already have a SOAP note from the initial diagnosis call, use it
    if (this.currentCasePayload && this.currentCasePayload.soap_note) {
      resultBox.innerHTML = this.formatStructuredHTML(this.currentCasePayload.soap_note);
      return;
    }

    if (!this.currentCasePayload) {
      resultBox.innerHTML = "<p>No case data found to generate SOAP note.</p>";
      return;
    }

    loading.style.display = 'flex';
    resultBox.innerHTML = "";

    try {
      const hostname = window.location.hostname || "127.0.0.1";
      const apiEndpoint = `http://${hostname}:8000/soap`;

      // Construct a full clinical context for the SOAP generator
      const p = this.currentCasePayload;
      const caseContext = `
CHIEF COMPLAINT: ${p.complaint}
PHYSICAL EXAM/LESION: ${p.lesion}
SYMPTOMS: ${p.symptoms}
TESTS: ${p.tests}
      `.trim();

      const res = await fetch(apiEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ case: caseContext })
      });

      if (!res.ok) throw new Error("Failed to generate SOAP note");
      
      const data = await res.json();
      const soapNote = data.soap_note;
      
      this.currentCasePayload.soap_note = soapNote;
      resultBox.innerHTML = this.formatStructuredHTML(soapNote);

    } catch (error) {
      console.error(error);
      resultBox.innerHTML = `<p style="color:var(--error);">Error generating SOAP note: ${error.message}</p>`;
    } finally {
      loading.style.display = 'none';
    }
  }

  copySOAPNote() {
    const text = this.currentCasePayload?.soap_note;
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      alert("SOAP Note copied to clipboard!");
    });
  }

  downloadSOAPNote() {
    const text = this.currentCasePayload?.soap_note;
    if (!text) return;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SOAP_Note_${new Date().getTime()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  downloadSOAPPDF() {
    const p = this.currentCasePayload;
    if (!p?.soap_note) return;

    try {
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();
      let y = 20;

      // Header
      doc.setFont("helvetica", "bold");
      doc.setFontSize(18);
      doc.setTextColor(0, 123, 255); // Medical Blue
      doc.text("DermaCare AI - Clinical Documentation", 15, y);
      y += 10;

      doc.setFontSize(10);
      doc.setTextColor(100, 100, 100);
      doc.setFont("helvetica", "normal");
      doc.text(`Generated on: ${new Date().toLocaleString()}`, 15, y);
      y += 15;

      // Patient Info Section
      doc.setFont("helvetica", "bold");
      doc.setFontSize(12);
      doc.setTextColor(0, 0, 0);
      doc.text("PATIENT INFORMATION", 15, y);
      y += 7;
      
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      doc.text(`Age: ${p.patient_age}`, 15, y);
      doc.text(`Region: ${p.geographic_region}`, 70, y);
      y += 5;
      doc.text(`Skin Phototype: ${p.skin_phototype}`, 15, y);
      doc.text(`Occupation: ${p.occupation}`, 70, y);
      y += 15;

      // SOAP Note Section
      doc.setFont("helvetica", "bold");
      doc.setFontSize(12);
      doc.text("SOAP NOTE", 15, y);
      y += 7;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      
      // Split text into lines that fit the page width
      const splitText = doc.splitTextToSize(p.soap_note, 180);
      
      // Check for page overflow
      splitText.forEach(line => {
        if (y > 280) {
          doc.addPage();
          y = 20;
        }
        doc.text(line, 15, y);
        y += 6;
      });

      doc.save(`Clinical_Record_${p.patient_age}_${new Date().getTime()}.pdf`);
    } catch (err) {
      console.error("PDF generation failed:", err);
      alert("Failed to generate PDF. Check console for details.");
    }
  }

  async checkDrugInteractions() {
    const input = document.getElementById('drug-input').value;
    const drugs = input.split(/[,\n]/).map(d => d.trim()).filter(d => d.length > 0);
    
    if (drugs.length < 2) {
      alert("Please enter at least two medications to check for interactions.");
      return;
    }

    const btn = document.getElementById('check-drug-btn');
    const loading = document.getElementById('drug-loading');
    const resultContainer = document.getElementById('drug-result-container');
    const resultBox = document.getElementById('drug-result');

    btn.disabled = true;
    loading.style.display = 'block';
    resultContainer.style.display = 'none';

    try {
      const hostname = window.location.hostname || "127.0.0.1";
      const apiEndpoint = `http://${hostname}:8000/check-interactions`;

      const res = await fetch(apiEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ drugs: drugs })
      });

      if (!res.ok) throw new Error("Failed to analyze interactions");

      const data = await res.json();
      this.currentDrugAnalysis = data.analysis;
      resultBox.innerHTML = this.formatStructuredHTML(data.analysis);
      resultContainer.style.display = 'block';

    } catch (error) {
      console.error(error);
      alert("Error checking interactions: " + error.message);
    } finally {
      btn.disabled = false;
      loading.style.display = 'none';
    }
  }

  copyDrugAnalysis() {
    if (!this.currentDrugAnalysis) return;
    navigator.clipboard.writeText(this.currentDrugAnalysis).then(() => {
      alert("Analysis copied to clipboard!");
    });
  }

  downloadDrugPDF() {
    if (!this.currentDrugAnalysis) return;
    
    try {
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();
      let y = 20;

      doc.setFont("helvetica", "bold");
      doc.setFontSize(18);
      doc.setTextColor(0, 123, 255);
      doc.text("DermaCare AI - Drug Interaction Report", 15, y);
      y += 10;

      doc.setFontSize(10);
      doc.setTextColor(100, 100, 100);
      doc.setFont("helvetica", "normal");
      doc.text(`Generated on: ${new Date().toLocaleString()}`, 15, y);
      y += 15;

      doc.setFont("helvetica", "bold");
      doc.setFontSize(12);
      doc.setTextColor(0, 0, 0);
      doc.text("INTERACTION ANALYSIS", 15, y);
      y += 7;

      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      const splitText = doc.splitTextToSize(this.currentDrugAnalysis, 180);
      splitText.forEach(line => {
        if (y > 280) { doc.addPage(); y = 20; }
        doc.text(line, 15, y);
        y += 6;
      });

      doc.save(`Drug_Interaction_Report_${new Date().getTime()}.pdf`);
    } catch (err) {
      console.error(err);
      alert("Failed to generate PDF.");
    }
  } // --- Data & State Management ---
  async updateDashboardMetrics() {
    try {
      const cases = await getCases();
      const totalCount = cases.length;
      const completedCount = cases.filter(c => c.status === 'completed').length;
      const pendingCount = cases.filter(c => c.status === 'pending').length;

      document.getElementById('metric-total-cases').innerText = totalCount;
      document.getElementById('metric-completed-cases').innerText = completedCount;
      document.getElementById('metric-pending-cases').innerText = pendingCount;
    } catch (err) {
      console.error("Failed to update metrics:", err);
    }
  }

  clearForms() {
    document.querySelectorAll('input, select, textarea').forEach(el => {
       if (el.id !== 'skin_phototype') el.value = "";
    });
    // payload and raw response cleared only on startNewDiagnosis to allow proper navigation
  }

  async finishCase() {
    if (this.currentCasePayload) {
       await saveCase(this.currentCasePayload);
    }
    this.showScreen('screen-dashboard');
  }

  // --- History Rendering ---
  async showHistory() {
    this.showScreen('screen-history');
    const container = document.getElementById('history-container');
    container.innerHTML = "<p style='color: var(--text-muted);'>Loading offline cases...</p>";
    
    try {
      const cases = await getCases();
      this.historyCache = cases;
      this.renderHistory(cases);
    } catch (error) {
       container.innerHTML = `<p style="color: var(--error);">Failed to load cases from internal database.</p>`;
    }
  }

  renderHistory(cases) {
    const container = document.getElementById('history-container');
    if (cases.length === 0) {
      container.innerHTML = "<p style='color: var(--text-muted);'>No cases found matching your criteria.</p>";
      return;
    }

    container.innerHTML = '';
    cases.forEach(c => {
      const date = new Date(c.timestamp).toLocaleString();
      const statusClass = c.status === 'pending' ? 'pending' : '';
      const complaintSummary = c.complaint.length > 50 ? c.complaint.substring(0, 50) + "..." : c.complaint;
      
      container.innerHTML += `
        <div class="history-card" onclick="window.app.viewCaseDetails('${c.case_id}')">
           <div class="history-card-header">
             <div class="history-date">📅 ${this.sanitizeEscape(date)}</div>
             <div class="history-status ${statusClass}">${this.sanitizeEscape(c.status) || 'unknown'}</div>
           </div>
           <div class="history-desc"><strong>🩺 Complaint:</strong> ${this.sanitizeEscape(complaintSummary)}</div>
           <div class="history-desc"><strong>👤 Patient:</strong> Age ${this.sanitizeEscape(c.patient_age.toString())}, ${this.sanitizeEscape(c.geographic_region)}</div>
        </div>
      `;
    });
  }

  filterHistory() {
    const query = document.getElementById('history-search').value.toLowerCase();
    const filtered = this.historyCache.filter(c => {
      return c.complaint.toLowerCase().includes(query) || 
             c.geographic_region.toLowerCase().includes(query) ||
             c.patient_age.toString().includes(query);
    });
    this.renderHistory(filtered);
  }

  // --- Case Details ---
  viewCaseDetails(id) {
    const caseData = this.historyCache.find(c => c.case_id === id);
    if (!caseData) {
       document.getElementById('history-container').innerHTML = `<p style="color: #ef4444;">Error: Case not found in local cache.</p>`;
       return;
    }

    this.currentViewCaseId = id;
    this.showScreen('screen-case-details');

    const d = new Date(caseData.timestamp).toLocaleString();
    document.getElementById('details-date').innerText = d;

    // Fill Demographics
    document.getElementById('details-demographics').innerHTML = `
        <p><strong>Age:</strong> ${this.sanitizeEscape(caseData.patient_age.toString())}</p>
        <p><strong>Region:</strong> ${this.sanitizeEscape(caseData.geographic_region)}</p>
        <p><strong>Phototype:</strong> ${this.sanitizeEscape(caseData.skin_phototype)}</p>
        <p><strong>Occupation:</strong> ${this.sanitizeEscape(caseData.occupation)}</p>
    `;

    // Fill Assessment
    document.getElementById('details-assessment').innerHTML = `
        <p><strong>Complaint:</strong> ${this.sanitizeEscape(caseData.complaint)}</p>
        <p><strong>Lesion:</strong> ${this.sanitizeEscape(caseData.lesion)}</p>
        <p><strong>Symptoms:</strong> ${this.sanitizeEscape(caseData.symptoms)}</p>
        <p><strong>Tests:</strong> ${this.sanitizeEscape(caseData.tests)}</p>
    `;

    // Check for structured data. Even if one exists, we prefer structured view.
    const hasStructuredData = (caseData.diagnoses && caseData.diagnoses !== "None specified by AI") || 
                              (caseData.reasoning && caseData.reasoning !== "None specified by AI");

    if (hasStructuredData) {
        document.getElementById('details-structured').style.display = 'block';
        if (document.getElementById('details-fallback')) document.getElementById('details-fallback').style.display = 'none';

        document.getElementById('details-diagnoses').innerHTML = this.formatStructuredHTML(caseData.diagnoses || "No specific diagnoses recorded.");
        document.getElementById('details-reasoning').innerHTML = this.formatStructuredHTML(caseData.reasoning || "No clinical reasoning recorded.");
        document.getElementById('details-tests').innerHTML = this.formatStructuredHTML(caseData.tests || "No recommended tests recorded.");
        
        const referralBox = document.getElementById('details-referral');
        if (referralBox) referralBox.innerHTML = this.formatStructuredHTML(caseData.referral || "No specific referral advice.");
    } else {
        document.getElementById('details-structured').style.display = 'none';
        const fallbackBox = document.getElementById('details-fallback');
        if (fallbackBox) {
            fallbackBox.style.display = 'block';
            document.getElementById('details-raw').innerHTML = `<div class="rich-text">${this.formatStructuredHTML(caseData.raw_ai_response || caseData.ai_diagnosis || "No AI analysis data found.")}</div>`;
        }
    }

    // Treatment
    const treatmentList = caseData.treatment_list || [];
    if (treatmentList.length > 0) {
        document.getElementById('details-treatment-box').style.display = 'block';
        document.getElementById('details-treatment').innerHTML = this.formatStructuredHTML(treatmentList.join('\n'));
    } else {
        // Fallback for older cases using raw text
        const treatmentText = caseData.raw_ai_response || caseData.ai_diagnosis || "";
        const treatIdx = treatmentText.toLowerCase().indexOf('treatment suggestions');
        if (treatIdx !== -1) {
            document.getElementById('details-treatment-box').style.display = 'block';
            let endIdx = treatmentText.length;
            const noteIdx = treatmentText.toLowerCase().indexOf('important notice');
            if (noteIdx !== -1) endIdx = noteIdx;
            document.getElementById('details-treatment').innerHTML = this.formatStructuredHTML(treatmentText.substring(treatIdx, endIdx).trim());
        } else {
            document.getElementById('details-treatment-box').style.display = 'none';
        }
    }

    // Pending Re-run capability
    if (caseData.status === 'pending') {
        document.getElementById('details-retry-container').style.display = 'block';
    } else {
        document.getElementById('details-retry-container').style.display = 'none';
    }

    // SOAP Note Display
    if (caseData.soap_note) {
        document.getElementById('details-soap-box').style.display = 'block';
        document.getElementById('details-soap').innerText = caseData.soap_note;
    } else {
        document.getElementById('details-soap-box').style.display = 'none';
    }
  }

  async retryPendingAnalysis() {
    if (!this.currentViewCaseId) return;
    
    const caseData = this.historyCache.find(c => c.case_id === this.currentViewCaseId);
    if (!caseData) return;

    // Load payload directly back into active flow
    this.currentCasePayload = Object.assign({}, caseData);
    
    // Switch to assessment screen invisibly and hit analyze mapping loading spinner beautifully
    this.showScreen('screen-assessment');
    
    // Temporarily replace form values so loading state looks correct to the user visually
    document.getElementById('complaint').value = caseData.complaint;
    document.getElementById('patient_age').value = caseData.patient_age;
    document.getElementById('geographic_region').value = caseData.geographic_region;
    document.getElementById('skin_phototype').value = caseData.skin_phototype;
    document.getElementById('occupation').value = caseData.occupation;
    document.getElementById('lesion').value = caseData.lesion;
    document.getElementById('symptoms').value = caseData.symptoms;
    document.getElementById('tests').value = caseData.tests;

    await this.analyzeCase();
  }

  async copyCaseSummary() {
    if (!this.currentViewCaseId) return;
    const c = this.historyCache.find(x => x.case_id === this.currentViewCaseId);
    if (!c) return;

    const summary = `
CASE SUMMARY: ${new Date(c.timestamp).toLocaleString()}
------------------------------------------
PATIENT: Age ${c.patient_age}, ${c.geographic_region}, ${c.skin_phototype}
COMPLAINT: ${c.complaint}
DIAGNOSES: ${c.diagnoses || "N/A"}
REASONING: ${c.reasoning || "N/A"}
TREATMENT: ${c.treatment || "N/A"}
------------------------------------------
GENERATED BY DERMACARE AI
    `.trim();

    navigator.clipboard.writeText(summary).then(() => {
        alert("Case summary copied to clipboard!");
    });
  }

  async exportCasePDF() {
    if (!this.currentViewCaseId) return;
    const c = this.historyCache.find(x => x.case_id === this.currentViewCaseId);
    if (!c) return;

    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        let y = 20;

        doc.setFont("helvetica", "bold");
        doc.setFontSize(18);
        doc.setTextColor(0, 123, 255);
        doc.text("Clinical Case Report", 15, y);
        y += 10;

        doc.setFontSize(10);
        doc.setTextColor(100, 100, 100);
        doc.setFont("helvetica", "normal");
        doc.text(`Record ID: ${c.case_id}`, 15, y);
        y += 5;
        doc.text(`Date: ${new Date(c.timestamp).toLocaleString()}`, 15, y);
        y += 15;

        // Content Sections
        const sections = [
            { title: "PATIENT DEMOGRAPHICS", content: `Age: ${c.patient_age}\nRegion: ${c.geographic_region}\nPhototype: ${c.skin_phototype}` },
            { title: "CLINICAL FINDINGS", content: `Complaint: ${c.complaint}\nLesion: ${c.lesion || "N/A"}\nSymptoms: ${c.symptoms || "N/A"}` },
            { title: "AI ANALYSIS", content: `Possible Diagnoses:\n${c.diagnoses || "N/A"}\n\nReasoning:\n${c.reasoning || "N/A"}` },
            { title: "SOAP NOTE", content: c.soap_note || "No SOAP note generated for this case." }
        ];

        sections.forEach(s => {
            if (y > 260) { doc.addPage(); y = 20; }
            doc.setFont("helvetica", "bold");
            doc.setFontSize(12);
            doc.setTextColor(0, 0, 0);
            doc.text(s.title, 15, y);
            y += 7;

            doc.setFont("helvetica", "normal");
            doc.setFontSize(10);
            const splitLines = doc.splitTextToSize(s.content, 180);
            splitLines.forEach(line => {
                if (y > 280) { doc.addPage(); y = 20; }
                doc.text(line, 15, y);
                y += 6;
            });
            y += 10;
        });

        doc.save(`Case_Report_${c.case_id.substring(0, 8)}.pdf`);
    } catch (err) {
        console.error(err);
        alert("Failed to export PDF.");
    }
  }

  async deleteCurrentCase() {
    if (!this.currentViewCaseId) return;
    try {
        await deleteCase(this.currentViewCaseId);
        this.currentViewCaseId = null;
        this.showHistory(); // Refresh view actively
    } catch (err) {
        console.error("Deletion failed:", err);
        alert("Failed to delete the case.");
    }
  }


}

// Initialize safely to preserve state during navigation in SPA
window.app = window.app || new AppController();
