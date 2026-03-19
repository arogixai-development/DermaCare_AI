// Removed module import to allow native offline file:// execution
// We safely rely on storage.js being loaded alongside app.js natively.

class AppController {
  constructor() {
    try {
      this.currentScreen = 'screen-dashboard';
      this.currentCasePayload = null;
      this.rawAIResponse = "";
      this.currentDrugAnalysis = "";
      this.uploadedImage = null;
      this.maxImageSize = 5 * 1024 * 1024;

      this.validScreens = [
        'screen-dashboard', 'screen-intake', 'screen-assessment',
        'screen-diagnosis', 'screen-treatment', 'screen-soap',
        'screen-history', 'screen-case-details', 'screen-drug-checker', 'screen-settings'
      ];
      
      this.historyCache = [];
      this.currentViewCaseId = null;

      this.updateDashboardMetrics();
      this.initNetworkMonitoring();
    } catch (err) {
      console.error('AppController init error:', err);
    }
  }

  initNetworkMonitoring() {
    const el = document.getElementById('network-status');
    if (!el) return;
    
    const updateStatus = async () => {
      if (!el) return;
      
      try {
        const hostname = window.location.hostname || "127.0.0.1";
        const ping = await fetch(`http://${hostname}:8001/diagnosis/health`, { method: 'GET', signal: AbortSignal.timeout(3000) });
        if (ping.ok) {
          const health = await ping.json();
          if (health.ollama_connected) {
            el.innerHTML = 'Status: 🟢 Online (AI Ready)';
            el.style.color = '';
          } else {
            el.innerHTML = 'Status: 🟠 Ollama Offline';
            el.style.color = '#f59e0b';
          }
        }
      } catch (err) {
        el.innerHTML = 'Status: 🔴 Offline';
        el.style.color = '#ef4444';
      }
    };
    
    // Heartbeat every 30 seconds
    setInterval(updateStatus, 30000);
    setTimeout(updateStatus, 2000); // Delay initial check
  }

  // --- HTML DOM Navigation (Core Logic) ---
  showScreen(targetId, e) {
    if (!targetId) return;
    
    if (e && e.preventDefault) {
      e.preventDefault();
      e.stopPropagation();
    }
    
    if (!this.validScreens.includes(targetId)) {
      console.warn(`Invalid screen ID ignored: ${targetId}`);
      return; 
    }

    try {
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
      
      if (targetId === 'screen-settings') {
        this.loadSettings();
      }
    } catch (err) {
      console.error('showScreen error:', err);
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

  // Highlights required fields missing and shows inline error messages
  validateInputs(fieldIds) {
    let isValid = true;
    const errorMessages = [];
    
    // Field display names for better error messages
    const fieldNames = {
      'complaint': 'Chief Complaint',
      'patient_age': 'Patient Age',
      'geographic_region': 'Geographic Region',
      'lesion': 'Lesion Description',
      'symptoms': 'Symptoms'
    };
    
    fieldIds.forEach(id => {
      const el = document.getElementById(id);
      const value = el?.value?.trim();
      
      // Remove previous error state
      this.clearFieldError(id);
      
      if (!value) {
        el.classList.add('input-error');
        this.showFieldError(id, `${fieldNames[id] || id} is required`);
        isValid = false;
        errorMessages.push(fieldNames[id] || id);
      } else if (id === 'patient_age') {
        // Validate age range
        const age = parseInt(value);
        if (isNaN(age) || age < 0 || age > 120) {
          el.classList.add('input-error');
          this.showFieldError(id, 'Age must be between 0 and 120');
          isValid = false;
          errorMessages.push('Patient Age (invalid range)');
        }
      } else {
        el.classList.remove('input-error');
      }
      
      // Remove error on input
      if (el) {
        el.addEventListener('input', () => this.clearFieldError(id), { once: true });
      }
    });
    
    if (!isValid) {
      this.showToast(`Please complete: ${errorMessages.join(', ')}`, 'warning');
    }
    return isValid;
  }
  
  showFieldError(fieldId, message) {
    const el = document.getElementById(fieldId);
    if (!el) return;
    
    // Remove any existing error message
    this.clearFieldError(fieldId);
    
    // Create error message element
    const errorEl = document.createElement('div');
    errorEl.className = 'field-error';
    errorEl.style.cssText = 'color: #dc3545; font-size: 0.8rem; margin-top: 4px;';
    errorEl.textContent = message;
    
    // Insert after the input wrapper
    el.parentNode.appendChild(errorEl);
  }
  
  clearFieldError(fieldId) {
    const el = document.getElementById(fieldId);
    if (!el) return;
    el.classList.remove('input-error');
    
    // Remove error message
    const parent = el.parentNode;
    const existingError = parent.querySelector('.field-error');
    if (existingError) existingError.remove();
  }
  
  showToast(message, type = 'info') {
    // Remove existing toasts
    const existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();
    
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    const bgColors = {
      'info': 'var(--medical-blue)',
      'warning': '#f59e0b',
      'error': 'var(--error-text)',
      'success': '#10b981'
    };
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: ${bgColors[type] || bgColors.info};
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      z-index: 1000;
      animation: slideIn 0.3s ease;
      max-width: 300px;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Auto remove after 4 seconds
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
  
  // --- Image Upload Handling ---
  handleImageUpload(input) {
    const file = input.files[0];
    if (!file) return;
    
    // Check file size
    if (file.size > this.maxImageSize) {
      this.showToast('Image too large. Maximum size is 5MB.', 'error');
      input.value = ''; // Reset input
      return;
    }
    
    // Check file type
    if (!file.type.startsWith('image/')) {
      this.showToast('Please select a valid image file.', 'error');
      input.value = '';
      return;
    }
    
    // Read and convert to base64
    const reader = new FileReader();
    reader.onload = (e) => {
      this.uploadedImage = e.target.result;
      this.displayImagePreview(file);
      
      // Add image description to lesion field
      const lesionField = document.getElementById('lesion');
      if (lesionField && !lesionField.value.includes('[Image attached]')) {
        lesionField.value += '\n[Image attached]';
      }
    };
    reader.onerror = () => {
      this.showToast('Failed to read image file.', 'error');
    };
    reader.readAsDataURL(file);
  }
  
  displayImagePreview(file) {
    const preview = document.getElementById('image-preview');
    const container = document.getElementById('image-preview-container');
    const info = document.getElementById('image-info');
    const uploadArea = document.getElementById('image-upload-area');
    
    if (this.uploadedImage) {
      preview.src = this.uploadedImage;
      container.style.display = 'block';
      uploadArea.style.display = 'none';
      
      // Show file info
      const sizeKB = (file.size / 1024).toFixed(1);
      const sizeDisplay = sizeKB > 1024 ? `${(sizeKB / 1024).toFixed(1)} MB` : `${sizeKB} KB`;
      info.textContent = `${file.name} (${sizeDisplay})`;
    }
  }
  
  removeImage() {
    this.uploadedImage = null;
    const container = document.getElementById('image-preview-container');
    const uploadArea = document.getElementById('image-upload-area');
    const input = document.getElementById('lesion-image');
    
    container.style.display = 'none';
    uploadArea.style.display = 'block';
    if (input) input.value = '';
    
    // Remove image indicator from lesion field
    const lesionField = document.getElementById('lesion');
    if (lesionField) {
      lesionField.value = lesionField.value.replace('\n[Image attached]', '');
    }
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
      // Include image data if uploaded
      has_image: !!this.uploadedImage,
      image_data: this.uploadedImage || null
    };

    const btn = document.getElementById('analyze-btn');
    const loading = document.getElementById('loading');
    const statusText = document.getElementById('analysis-status');
    const progressBar = document.getElementById('analysis-progress');
    
    btn.disabled = true;
    loading.style.display = 'flex';
    progressBar.style.width = '0%';
    
    const statusMessages = [
      { text: "Processing patient data...", progress: 15, time: "5-10 seconds" },
      { text: "Connecting to AI model...", progress: 25, time: "10-20 seconds" },
      { text: "Evaluating clinical patterns...", progress: 50, time: "20-40 seconds" },
      { text: "Generating differential diagnoses...", progress: 70, time: "40-50 seconds" },
      { text: "Finalizing recommendations...", progress: 90, time: "50-60 seconds" }
    ];

    let messageIndex = 0;
    const intervalId = setInterval(() => {
      if (messageIndex < statusMessages.length) {
        statusText.innerText = statusMessages[messageIndex].text;
        progressBar.style.width = statusMessages[messageIndex].progress + '%';
        document.getElementById('estimated-time').textContent = 
          `Estimated time remaining: ${statusMessages[messageIndex].time}`;
        messageIndex++;
      }
    }, 12000); // Update every 12 seconds

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 min timeout

    try {
      const hostname = window.location.hostname || "127.0.0.1";
      const apiEndpoint = `http://${hostname}:8001/diagnosis`;

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
      let isOllamaOffline = errorMsg.includes("503") || errorMsg.includes("Offline") || errorMsg.includes("ollama");
      
      if (error.name === 'AbortError') errorMsg = "AI processing timed out. Please retry.";
      if (isOllamaOffline) {
        errorMsg = "Ollama is not running. Please start Ollama in a terminal: `ollama serve`";
      }

      // Show error in the UI with helpful message
      const resultDiv = document.getElementById('diagnosis-result');
      resultDiv.innerHTML = `
        <div class="clinical-alert ${isOllamaOffline ? 'alert-warning' : 'alert-danger'}" 
             style="background:${isOllamaOffline ? 'rgba(245,158,11,0.1)' : 'var(--error-bg)'}; 
                    color:${isOllamaOffline ? '#d97706' : 'var(--error-text)'}; 
                    padding:1rem; border-radius:8px; border-left: 4px solid ${isOllamaOffline ? '#f59e0b' : '#dc3545'};">
            <p><strong>⚠️ ${isOllamaOffline ? 'AI Backend Offline' : 'Analysis Failed'}</strong></p>
            <p>${this.sanitizeEscape(errorMsg)}</p>
            ${isOllamaOffline ? '<p style="margin-top:0.5rem;font-size:0.85rem;">Open a terminal and run: <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px;">ollama serve</code></p>' : ''}
            <button onclick="window.app.analyzeCase()" class="btn btn-primary btn-small" style="margin-top:1rem;">Retry Analysis</button>
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

    // Map new field names (differential_diagnosis) or legacy (diagnoses)
    const diffDx = data.differential_diagnosis || data.diagnoses || [];
    const reasoning = data.clinical_reasoning || data.reasoning || "";
    const soapNote = data.soap_note || data.soap || "";
    const treatmentPlan = data.treatment_plan || data.treatment || [];
    const referralIndicators = data.referral_indicators || data.referral || [];
    const followUp = data.follow_up || "";
    const recommendedTests = data.tests_list || data.tests || [];
    const triageValue = (data.triage || "Routine").toLowerCase();

    // Format differential diagnosis for display
    let diagnosesHTML = "";
    if (Array.isArray(diffDx)) {
      diagnosesHTML = diffDx.map((d, i) => {
        if (typeof d === 'string') return `<div style="padding:12px;background:#334155;border-radius:8px;color:#f1f5f9;margin-bottom:10px;"><strong>${d}</strong></div>`;
        const probColor = d.probability && (d.probability.includes('90') || d.probability.includes('85') || d.probability.includes('80')) ? '#22c55e' : 
                         d.probability && (d.probability.includes('70') || d.probability.includes('60')) ? '#84cc16' :
                         d.probability && d.probability.includes('50') ? '#eab308' : '#64748b';
        return `<div style="padding:14px;background:#334155;border-radius:10px;border-left:4px solid ${probColor};margin-bottom:12px;color:#f1f5f9;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <strong style="color:#ffffff;font-size:1rem;">${i === 0 ? '⭐ ' : ''}${d.condition || 'Unknown'}</strong>
            <span style="background:${probColor};color:white;padding:3px 12px;border-radius:12px;font-size:0.8rem;font-weight:600;">${d.probability || 'N/A'}</span>
          </div>
          <div style="font-size:0.85rem;color:#cbd5e1;">${(d.supporting_features || []).join(' | ')}</div>
        </div>`;
      }).join('');
    } else {
      diagnosesHTML = `<div style="padding:12px;background:#334155;border-radius:8px;color:#f1f5f9;">${diffDx}</div>`;
    }

    // Format treatment plan for display
    let treatmentHTML = "";
    if (Array.isArray(treatmentPlan)) {
      treatmentHTML = treatmentPlan.map((t, i) => {
        if (typeof t === 'string') return `<div style="padding:12px;background:#334155;border-radius:8px;margin-bottom:8px;color:#f1f5f9;">${t}</div>`;
        return `<div style="padding:14px;background:#334155;border-radius:10px;border:1px solid #475569;margin-bottom:10px;color:#f1f5f9;">
          <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px;">
            <span style="background:#007bff;color:white;width:24px;height:24px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:bold;">${i + 1}</span>
            <strong style="color:#60a5fa;font-size:1rem;">${t.medication || 'Treatment'}</strong>
          </div>
          <div style="margin-left:34px;">
            <div style="margin-bottom:4px;color:#94a3b8;">Application: <span style="color:#e2e8f0;">${t.application || 'N/A'}</span></div>
            <div style="margin-bottom:4px;color:#94a3b8;">Duration: <span style="color:#22c55e;font-weight:600;">${t.duration || 'N/A'}</span></div>
            ${t.education ? `<div style="margin-top:8px;padding:8px;background:#fef3c7;border-radius:6px;font-size:0.85rem;color:#92400e;">&#9432; ${t.education}</div>` : ''}
          </div>
        </div>`;
      }).join('');
    } else {
      treatmentHTML = `<div style="padding:12px;background:#334155;border-radius:8px;color:#f1f5f9;">${treatmentPlan}</div>`;
    }

    // Format SOAP note - Simple clean format
    let soapHTML = '<div style="font-family:system-ui,sans-serif;line-height:1.8;">';
    
    let s = '', o = '', a = '', p = '';
    
    if (typeof soapNote === 'object' && soapNote !== null) {
      s = soapNote.S || soapNote.SUBJECTIVE || soapNote.s || '';
      o = soapNote.O || soapNote.OBJECTIVE || soapNote.o || '';
      a = soapNote.A || soapNote.ASSESSMENT || soapNote.a || '';
      p = typeof soapNote.P === 'object' ? JSON.stringify(soapNote.P) : (soapNote.P || soapNote.PLAN || soapNote.p || '');
    } else if (typeof soapNote === 'string' && soapNote) {
      // Simple approach: find content between quotes after each key
      // Pattern: 'S': 'content' or "S": "content"
      const getValue = (str, key) => {
        const patterns = [
          new RegExp(`'${key}':\\s*'([^']*)'`, 'i'),
          new RegExp(`"${key}":\\s*"([^"]*)"`, 'i'),
          new RegExp(`${key}:\\s*(.+?)(?=,\\s*(?:'|$))`, 'i')
        ];
        for (const p of patterns) {
          const m = str.match(p);
          if (m && m[1]) return m[1].trim();
        }
        return '';
      };
      
      s = getValue(soapNote, 'S');
      o = getValue(soapNote, 'O');
      a = getValue(soapNote, 'A');
      p = getValue(soapNote, 'P');
    }
    
    // Clean up text
    const clean = (text) => {
      if (!text) return '';
      return text.replace(/\\n/g, '<br>')
                 .replace(/\\'/g, "'")
                 .replace(/\\\\/g, '')
                 .replace(/\\"/g, '"')
                 .replace(/\\+/g, '')
                 .replace(/[{}[\]]/g, '')
                 .trim();
    };
    
    // Only show sections with content
    if (s) {
      soapHTML += `<div style="margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
          <span style="background:#8b5cf6;color:white;padding:6px 14px;border-radius:8px;font-weight:700;font-size:1rem;">S</span>
          <span style="font-weight:700;font-size:1.1rem;color:#8b5cf6;">SUBJECTIVE</span>
        </div>
        <div style="margin-left:52px;padding:14px 18px;background:#1e1b4b;border-radius:10px;border-left:5px solid #8b5cf6;font-size:0.95rem;line-height:1.7;color:#e2e8f0;">${clean(s)}</div>
      </div>`;
    }
    if (o) {
      soapHTML += `<div style="margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
          <span style="background:#0891b2;color:white;padding:6px 14px;border-radius:8px;font-weight:700;font-size:1rem;">O</span>
          <span style="font-weight:700;font-size:1.1rem;color:#0891b2;">OBJECTIVE</span>
        </div>
        <div style="margin-left:52px;padding:14px 18px;background:#083344;border-radius:10px;border-left:5px solid #0891b2;font-size:0.95rem;line-height:1.7;color:#e2e8f0;">${clean(o)}</div>
      </div>`;
    }
    if (a) {
      soapHTML += `<div style="margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
          <span style="background:#059669;color:white;padding:6px 14px;border-radius:8px;font-weight:700;font-size:1rem;">A</span>
          <span style="font-weight:700;font-size:1.1rem;color:#059669;">ASSESSMENT</span>
        </div>
        <div style="margin-left:52px;padding:14px 18px;background:#022c22;border-radius:10px;border-left:5px solid #059669;font-size:0.95rem;line-height:1.7;color:#e2e8f0;">${clean(a)}</div>
      </div>`;
    }
    if (p) {
      soapHTML += `<div style="margin-bottom:16px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
          <span style="background:#dc2626;color:white;padding:6px 14px;border-radius:8px;font-weight:700;font-size:1rem;">P</span>
          <span style="font-weight:700;font-size:1.1rem;color:#dc2626;">PLAN</span>
        </div>
        <div style="margin-left:52px;padding:14px 18px;background:#450a0a;border-radius:10px;border-left:5px solid #dc2626;font-size:0.95rem;line-height:1.7;color:#e2e8f0;">${clean(p)}</div>
      </div>`;
    }
    
    soapHTML += '</div>';
    
    // Check if SOAP was parsed successfully (has content in sections)
    const hasValidSOAP = s || o || a || p;
    
    // Update UI elements
    document.getElementById('box-diagnoses').innerHTML = diagnosesHTML;
    document.getElementById('box-reasoning').innerHTML = `<div style="padding:12px 16px;background:#1e293b;border-radius:8px;line-height:1.7;font-size:0.9rem;color:#f1f5f9;">${reasoning.replace(/\n/g, '<br>')}</div>`;
    
    // Recommended Tests - white theme compatible
    if (followUp) {
      document.getElementById('box-tests').innerHTML = `<div style="padding:12px 16px;background:#1e293b;border-radius:8px;line-height:1.7;font-size:0.9rem;color:#f1f5f9;">${followUp}</div>`;
    } else if (Array.isArray(recommendedTests) && recommendedTests.length > 0) {
      document.getElementById('box-tests').innerHTML = `<div style="display:flex;flex-direction:column;gap:8px;">${recommendedTests.map((t, i) => `<div style="display:flex;align-items:flex-start;gap:8px;padding:8px 12px;background:#1e293b;border-radius:6px;"><span style="background:#f59e0b;color:white;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:bold;flex-shrink:0;">${i + 1}</span><span style="color:#f1f5f9;font-size:0.9rem;">${t}</span></div>`).join('')}</div>`;
    } else {
      document.getElementById('box-tests').innerHTML = '<div style="padding:12px 16px;background:#1e293b;border-radius:8px;text-align:center;color:#94a3b8;font-size:0.9rem;">Follow-up as recommended</div>';
    }
    
    // Referral Advice - white theme compatible
    if (referralIndicators.length > 0) {
      document.getElementById('box-referral').innerHTML = `<div style="display:flex;flex-direction:column;gap:8px;">${referralIndicators.map(r => `<div style="display:flex;align-items:flex-start;gap:8px;padding:10px 14px;background:#1e293b;border-radius:6px;border-left:4px solid #ef4444;"><span style="color:#ef4444;font-size:0.9rem;font-weight:600;">⚠️</span><span style="color:#f1f5f9;font-size:0.9rem;">${r}</span></div>`).join('')}</div>`;
    } else {
      document.getElementById('box-referral').innerHTML = '<div style="padding:12px 16px;background:#1e293b;border-radius:8px;text-align:center;color:#94a3b8;font-size:0.9rem;">No referral indicators</div>';
    }
    
    // Update Treatment result with better formatting
    document.getElementById('treatment-result').innerHTML = treatmentHTML;

    // Update SOAP result
    const soapResult = document.getElementById('soap-result');
    if (soapResult) {
      // If SOAP parsing failed, show fallback structured format
      if (!hasValidSOAP && soapNote) {
        soapResult.innerHTML = `<div style="padding:16px;background:#f8fafc;border-radius:10px;font-family:monospace;white-space:pre-wrap;font-size:0.9rem;line-height:1.6;color:#334155;border:1px solid #e2e8f0;">${soapNote}</div>`;
      } else {
        soapResult.innerHTML = soapHTML;
      }
    }

    // Store soap_note for later use
    if (this.currentCasePayload) {
      this.currentCasePayload.soap_note = soapNote;
    }

    // Handle Triage Alert Display
    const triageBox = document.getElementById('triage-alert');
    const triageText = document.getElementById('triage-text');
    
    if (triageBox && triageText) {
        triageBox.style.display = 'flex';
        triageText.innerText = data.triage;
        
        triageBox.className = 'clinical-alert';
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
    // Clear uploaded image
    this.uploadedImage = null;
    const container = document.getElementById('image-preview-container');
    const uploadArea = document.getElementById('image-upload-area');
    if (container) container.style.display = 'none';
    if (uploadArea) uploadArea.style.display = 'block';
    const imageInput = document.getElementById('lesion-image');
    if (imageInput) imageInput.value = '';
    
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
      const apiEndpoint = `http://${hostname}:8001/soap`;

      // Send full case data for fresh SOAP generation
      const p = this.currentCasePayload;
      const soapRequest = {
        case_id: p.case_id || `case_${Date.now()}`,
        complaint: p.complaint,
        lesion: p.lesion,
        symptoms: p.symptoms,
        duration: p.duration || "",
        medical_history: p.medical_history || "",
        region: p.geographic_region,
        patient_age: p.patient_age,
        diagnoses: p.diagnoses_list || [],
        treatment: p.treatment_list || [],
        tests: p.tests_list || []
      };

      const res = await fetch(apiEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(soapRequest)
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
    if (!p?.soap_note) {
      this.showToast('No SOAP note available to export.', 'warning');
      return;
    }
    
    // Check if jsPDF is loaded
    if (typeof window.jspdf === 'undefined') {
      this.showToast('PDF library not loaded. Check your internet connection.', 'error');
      return;
    }

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
      const apiEndpoint = `http://${hostname}:8001/check-interactions`;

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
      this.showToast('Failed to generate PDF. Try copying the text instead.', 'error');
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
  
  // --- Settings Methods ---
  async testAIConnection() {
    const modelName = document.getElementById('settings-model-name')?.value || 'llama3:8b';
    const apiUrl = document.getElementById('settings-api-url')?.value || 'http://127.0.0.1:11434';
    
    try {
      const response = await fetch(`${apiUrl}/api/tags`, { signal: AbortSignal.timeout(5000) });
      if (response.ok) {
        const data = await response.json();
        const models = data.models?.map(m => m.name).join(', ') || 'None';
        this.showToast(`Connected! Available models: ${models}`, 'success');
      } else {
        this.showToast('Connection failed. Check URL and ensure Ollama is running.', 'error');
      }
    } catch (err) {
      this.showToast('Cannot connect to Ollama. Is it running?', 'error');
    }
  }
  
  toggleDarkMode(checkbox) {
    if (checkbox.checked) {
      document.body.classList.add('dark-mode');
      localStorage.setItem('dermacare-theme', 'dark');
    } else {
      document.body.classList.remove('dark-mode');
      localStorage.setItem('dermacare-theme', 'light');
    }
  }
  
  async exportAllCases() {
    try {
      const cases = await getCases();
      if (cases.length === 0) {
        this.showToast('No cases to export.', 'warning');
        return;
      }
      
      const blob = new Blob([JSON.stringify(cases, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dermacare_cases_export_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      this.showToast(`Exported ${cases.length} cases successfully.`, 'success');
    } catch (err) {
      console.error('Export failed:', err);
      this.showToast('Failed to export cases.', 'error');
    }
  }
  
  async clearCache() {
    if (confirm('Clear the AI response cache? This will not delete your cases.')) {
      try {
        await fetch('http://127.0.0.1:8001/diagnosis/cache', { method: 'DELETE' });
        this.showToast('Cache cleared successfully.', 'success');
      } catch (err) {
        this.showToast('Cache cleared locally.', 'info');
      }
    }
  }
  
  confirmDeleteAllCases() {
    if (confirm('Are you sure you want to delete ALL cases? This cannot be undone.')) {
      if (confirm('This will permanently delete all stored cases. Continue?')) {
        this.deleteAllCases();
      }
    }
  }
  
  async deleteAllCases() {
    try {
      const cases = await getCases();
      for (const c of cases) {
        await deleteCase(c.case_id);
      }
      this.showToast('All cases deleted.', 'success');
      this.updateDashboardMetrics();
    } catch (err) {
      console.error('Delete all failed:', err);
      this.showToast('Failed to delete all cases.', 'error');
    }
  }
  
  loadSettings() {
    // Load dark mode preference
    const theme = localStorage.getItem('dermacare-theme');
    const darkModeCheckbox = document.getElementById('settings-dark-mode');
    if (theme === 'dark') {
      document.body.classList.add('dark-mode');
      if (darkModeCheckbox) darkModeCheckbox.checked = true;
    }
    
    // Load API URL
    const savedApiUrl = localStorage.getItem('dermacare-api-url');
    if (savedApiUrl && document.getElementById('settings-api-url')) {
      document.getElementById('settings-api-url').value = savedApiUrl;
    }
    
    // Load model name
    const savedModel = localStorage.getItem('dermacare-model');
    if (savedModel && document.getElementById('settings-model-name')) {
      document.getElementById('settings-model-name').value = savedModel;
    }
    
    // Update case count
    this.updateCaseCount();
  }
  
  async updateCaseCount() {
    try {
      const cases = await getCases();
      const el = document.getElementById('case-count');
      if (el) {
        el.textContent = `${cases.length} cases stored`;
      }
    } catch (err) {
      const el = document.getElementById('case-count');
      if (el) el.textContent = 'Unable to load';
    }
  }
  
  saveSettings() {
    const apiUrl = document.getElementById('settings-api-url')?.value;
    const modelName = document.getElementById('settings-model-name')?.value;
    
    if (apiUrl) localStorage.setItem('dermacare-api-url', apiUrl);
    if (modelName) localStorage.setItem('dermacare-model', modelName);
    
    this.showToast('Settings saved.', 'success');
  }

}

// Initialize safely to preserve state during navigation in SPA
window.app = window.app || new AppController();
