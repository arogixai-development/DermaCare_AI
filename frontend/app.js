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
        'screen-history', 'screen-drug-checker', 'screen-settings'
      ];
      
      this.historyCache = [];

      this.updateDashboardMetrics();
      this.initNetworkMonitoring();
    } catch (err) {
      console.error('AppController init error:', err);
    }
  }

  initNetworkMonitoring() {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    
    const updateStatus = async () => {
      if (!dot || !text) return;
      
      try {
        const hostname = window.location.hostname || "127.0.0.1";
        const ping = await fetch(`http://${hostname}:8007/diagnosis/health`, { method: 'GET', signal: AbortSignal.timeout(3000) });
        if (ping.ok) {
          const health = await ping.json();
          const retryBtn = document.getElementById('retry-btn');
          if (health.ollama_connected) {
            dot.style.background = '#22c55e';
            text.textContent = 'Online / AI Ready';
            if (retryBtn) retryBtn.style.display = 'none';
          } else {
            dot.style.background = '#f59e0b';
            text.textContent = 'Ollama Offline';
            if (retryBtn) retryBtn.style.display = 'flex';
          }
        }
      } catch (err) {
        dot.style.background = '#ef4444';
        text.textContent = 'Offline';
        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) retryBtn.style.display = 'flex';
      }
    };
    
    setInterval(updateStatus, 30000);
    setTimeout(updateStatus, 1000);
  }

  async retryConnection() {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    const retryBtn = document.getElementById('retry-btn');
    
    if (dot) dot.style.background = '#f59e0b';
    if (text) text.textContent = 'Reconnecting...';
    if (retryBtn) retryBtn.style.display = 'none';
    
    try {
      const hostname = window.location.hostname || "127.0.0.1";
      const ping = await fetch(`http://${hostname}:8007/diagnosis/health`, { method: 'GET', signal: AbortSignal.timeout(5000) });
      if (ping.ok) {
        const health = await ping.json();
        if (health.ollama_connected) {
          if (dot) dot.style.background = '#22c55e';
          if (text) text.textContent = 'Online / AI Ready';
          this.showToast('Connected to Ollama successfully!', 'success');
        } else {
          if (dot) dot.style.background = '#f59e0b';
          if (text) text.textContent = 'Ollama Offline';
          if (retryBtn) retryBtn.style.display = 'flex';
        }
      }
    } catch (err) {
      if (dot) dot.style.background = '#ef4444';
      if (text) text.textContent = 'Offline';
      if (retryBtn) retryBtn.style.display = 'flex';
      this.showToast('Cannot connect to backend. Is the server running?', 'error');
    }
  }

  async checkConnection() {
    await this.retryConnection();
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

  startNewDiagnosis(e) {
    const event = e || window.event;
    if (event && typeof event.preventDefault === 'function') event.preventDefault();
    this.currentCasePayload = null;
    this.rawAIResponse = "";
    this.showScreen('screen-intake');
  }

  updateSidebarActive(screenId) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    
    if (screenId === 'screen-dashboard') {
      document.getElementById('nav-dashboard')?.classList.add('active');
    } else if (['screen-intake', 'screen-assessment', 'screen-diagnosis', 'screen-treatment', 'screen-soap'].includes(screenId)) {
      document.getElementById('nav-new')?.classList.add('active');
    } else if (screenId === 'screen-history') {
      document.getElementById('nav-history')?.classList.add('active');
    } else if (screenId === 'screen-drug-checker') {
      document.getElementById('nav-drug')?.classList.add('active');
    } else if (screenId === 'screen-settings') {
      document.getElementById('nav-settings')?.classList.add('active');
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
    
    if (this.currentScreen === 'screen-diagnosis' && targetId === 'screen-treatment') {
      if (!this.currentCasePayload || !this.currentCasePayload.diagnoses_list || this.currentCasePayload.diagnoses_list.length === 0) {
        this.showToast('Please run AI analysis first before proceeding.', 'warning');
        return;
      }
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
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    
    const toast = document.createElement('div');
    toast.className = 'toast';
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
    const uploadArea = document.querySelector('.image-upload');
    
    if (this.uploadedImage) {
      preview.src = this.uploadedImage;
      container.classList.remove('hidden');
      if (uploadArea) uploadArea.style.display = 'none';
    }
  }
  
  removeImage() {
    this.uploadedImage = null;
    const container = document.getElementById('image-preview-container');
    const uploadArea = document.querySelector('.image-upload');
    const input = document.getElementById('lesion-image');
    
    container.classList.add('hidden');
    if (uploadArea) uploadArea.style.display = 'flex';
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

    const existingData = this.currentCasePayload || {};
    
    const symptoms = [];
    document.querySelectorAll('#screen-assessment .checkbox-item input[type="checkbox"]:checked').forEach(cb => {
      symptoms.push(cb.value);
    });
    
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
      symptoms: symptoms.join(', ') || "None stated",
      tests: document.getElementById('tests').value || "None",
      lesion_history: document.getElementById('lesion_history').value || "Not provided",
      history_duration: document.getElementById('history_duration').value || "Unknown",
      change_pattern: document.getElementById('change_pattern').value || "Unknown",
      has_image: !!this.uploadedImage,
      image_data: this.uploadedImage || null
    };

    const btn = document.getElementById('analyze-btn');
    const loading = document.getElementById('loading-state');
    const progressBar = document.getElementById('analysis-progress-bar');
    const progressText = document.getElementById('progress-percent');
    const estTime = document.getElementById('est-time');
    
    btn.disabled = true;
    loading.classList.remove('hidden');
    progressBar.style.width = '0%';
    
    const statusMessages = [
      { text: "Initializing AI model...", progress: 15, time: "~10s" },
      { text: "Processing patient data...", progress: 30, time: "~20s" },
      { text: "Analyzing clinical patterns...", progress: 50, time: "~30s" },
      { text: "Generating treatment recommendations...", progress: 70, time: "~40s" },
      { text: "Finalizing diagnosis report...", progress: 90, time: "~45s" }
    ];

    let messageIndex = 0;
    const intervalId = setInterval(() => {
      if (messageIndex < statusMessages.length) {
        progressText.textContent = `Processing: ${statusMessages[messageIndex].text}`;
        estTime.textContent = `Est. ${statusMessages[messageIndex].time}`;
        progressBar.style.width = statusMessages[messageIndex].progress + '%';
        messageIndex++;
      }
    }, 10000); // Update every 10 seconds for better feedback

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minute timeout for image processing

    try {
      const hostname = window.location.hostname || "127.0.0.1";
      const apiEndpoint = `http://${hostname}:8007/diagnosis`;

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
      
      this.currentCasePayload.diagnoses_list = data.differential_diagnosis || data.diagnoses || [];
      this.currentCasePayload.reasoning = data.clinical_reasoning || data.reasoning || "";
      this.currentCasePayload.soap_note = data.soap_note || data.soap || "";
      this.currentCasePayload.triage = data.triage || "Routine";
      this.currentCasePayload.tests_list = data.tests_list || data.tests || [];
      this.currentCasePayload.referral_list = data.referral_indicators || data.referral || [];
      this.currentCasePayload.treatment_list = data.treatment_plan || data.treatment || [];
      this.currentCasePayload.status = "completed";

      this.parseAIResponse(data);
      this.showScreen('screen-diagnosis');

    } catch (error) {
      console.error("Analysis Failed:", error);
      
      let errorMsg = error.message;
      let isOllamaOffline = errorMsg.includes("503") || errorMsg.includes("Offline") || errorMsg.includes("ollama") || errorMsg.includes("fetch");
      
      if (error.name === 'AbortError') {
        errorMsg = "Request timed out. The AI model may be loading slowly. Please try again.";
      }
      if (isOllamaOffline) {
        errorMsg = "Cannot connect to AI backend. Make sure Ollama is running: `ollama serve`";
      }

      const diagList = document.getElementById('diagnosis-list');
      diagList.innerHTML = `
        <div class="safety-alert" style="background: rgba(245,158,11,0.1); border-color: #f59e0b;">
          <span class="material-icons" style="color: #f59e0b;">error</span>
          <div class="safety-alert-content">
            <span class="safety-alert-title">${isOllamaOffline ? 'AI Backend Offline' : 'Analysis Failed'}</span>
            <span class="safety-alert-text">${this.sanitizeEscape(errorMsg)}</span>
          </div>
        </div>
        <button class="btn btn-primary" onclick="window.app.analyzeCase()" style="margin-top: 1rem;">
          <span class="material-icons">refresh</span> Retry
        </button>
      `;
      
      this.currentCasePayload.status = "pending";
      this.showScreen('screen-diagnosis');
      
    } finally {
      clearInterval(intervalId);
      clearTimeout(timeoutId);
      btn.disabled = false;
      loading.classList.add('hidden');
      
      if (this.currentCasePayload) {
         await saveCase(this.currentCasePayload);
      }
    }
  }

  parseAIResponse(data) {
    if (!data || typeof data !== 'object') {
      console.error('parseAIResponse: Invalid data received', data);
      return;
    }

    // Debug logging to verify data received
    console.log('=== DermaCare AI Response ===');
    console.log('differential_diagnosis:', data.differential_diagnosis?.length || 0, 'items');
    console.log('lesion_analysis:', data.lesion_analysis?.length || 0, 'items');
    console.log('recommended_tests:', data.recommended_tests?.length || 0, 'items');
    console.log('treatment_plan:', data.treatment_plan?.length || 0, 'items');
    console.log('soap_note type:', typeof data.soap_note);
    console.log('clinical_reasoning length:', (data.clinical_reasoning || '').length);

    const diffDx = data.differential_diagnosis || data.diagnoses || [];
    const reasoning = data.clinical_reasoning || data.reasoning || "";
    const soapNote = data.soap_note || data.soap || "";
    const treatmentPlan = data.treatment_plan || data.treatment || [];
    const recommendedTests = data.recommended_tests || data.tests_list || data.tests || [];
    const lesionAnalysis = data.lesion_analysis || [];
    const uncertaintyFlags = data.uncertainty_flags || {};
    const gmuAnalysis = data.gmu_analysis || {};
    const safetyChecks = data.safety_checks || {};

    // Differential Diagnoses
    const diagList = document.getElementById('diagnosis-list');
    if (Array.isArray(diffDx) && diffDx.length > 0) {
      diagList.innerHTML = diffDx.map((d, i) => {
        const probColor = d.probability && (d.probability.includes('90') || d.probability.includes('85') || d.probability.includes('80')) ? '#22c55e' : 
                         d.probability && (d.probability.includes('70') || d.probability.includes('60')) ? '#84cc16' :
                         d.probability && d.probability.includes('50') ? '#eab308' : '#64748b';
        const features = d.supporting_features || d.features || [];
        const exclusions = d.differentials_to_exclude || [];
        return `<div class="diagnosis-item">
          <div class="diagnosis-header">
            <span class="diagnosis-name">${i === 0 ? '<span class="material-icons" style="color: var(--primary);">star</span> ' : ''}${d.condition || 'Unknown'}</span>
            <span class="diagnosis-probability" style="background: ${probColor};">${d.probability || 'N/A'}</span>
          </div>
          <div class="diagnosis-features">${Array.isArray(features) && features.length > 0 ? features.join(' | ') : 'Supporting features available'}</div>
          ${exclusions.length > 0 ? `<div style="margin-top: 0.5rem; font-size: 0.75rem; color: var(--on-surface-variant);"><strong>Differentials to exclude:</strong> ${exclusions.join(', ')}</div>` : ''}
        </div>`;
      }).join('');
    } else {
      diagList.innerHTML = '<p style="color: var(--on-surface-variant);">No specific diagnoses generated.</p>';
    }

    // AI Confidence
    const confText = document.getElementById('ai-confidence-text');
    if (confText) {
      const conf = uncertaintyFlags.overall_confidence || 'MEDIUM';
      const ci = uncertaintyFlags.confidence_interval || [30, 70];
      confText.textContent = `${conf} confidence (Monte Carlo, CI: ${ci[0]}-${ci[1]}%)`;
    }

    // Lesion Analysis
    const lesionList = document.getElementById('lesion-analysis-list');
    if (Array.isArray(lesionAnalysis) && lesionAnalysis.length > 0 && lesionAnalysis[0]) {
      const la = lesionAnalysis[0];
      let html = '';
      if (la.morphology) html += `<div style="margin-bottom: 1rem;"><strong>Morphology:</strong><br>${this.sanitizeEscape(la.morphology)}</div>`;
      if (la.distribution) html += `<div style="margin-bottom: 1rem;"><strong>Distribution:</strong><br>${this.sanitizeEscape(la.distribution)}</div>`;
      if (la.ABCDE_assessment) html += `<div style="margin-bottom: 1rem;"><strong>ABCDE Assessment:</strong><br>${this.sanitizeEscape(la.ABCDE_assessment)}</div>`;
      if (la.color_patterns) {
        const patterns = Array.isArray(la.color_patterns) ? la.color_patterns : [la.color_patterns];
        html += `<div style="margin-bottom: 1rem;"><strong>Color Patterns:</strong><br>${this.sanitizeEscape(patterns.join(', '))}</div>`;
      }
      if (la.dermoscopy_findings) html += `<div style="margin-bottom: 1rem;"><strong>Dermoscopy Findings:</strong><br>${this.sanitizeEscape(la.dermoscopy_findings)}</div>`;
      lesionList.innerHTML = html || '<p style="color: var(--on-surface-variant);">Lesion analysis details pending.</p>';
    } else {
      lesionList.innerHTML = '<p style="color: var(--on-surface-variant);">No detailed lesion analysis available. Please provide clinical description for best results.</p>';
    }

    // Recommended Tests
    const testsList = document.getElementById('recommended-tests-list');
    if (Array.isArray(recommendedTests) && recommendedTests.length > 0) {
      testsList.innerHTML = recommendedTests.map((t, i) => {
        const name = typeof t === 'string' ? t : t.test || t.name || `Test ${i + 1}`;
        return `<div class="analysis-item">
          <span class="material-icons" style="font-size: 1rem; color: var(--secondary);">science</span>
          <div>
            <div style="font-weight: 500;">${this.sanitizeEscape(name)}</div>
          </div>
        </div>`;
      }).join('');
    } else {
      testsList.innerHTML = '<p style="color: var(--on-surface-variant);">No specific tests recommended.</p>';
    }

    // Clinical Reasoning
    const reasoningEl = document.getElementById('clinical-reasoning');
    if (reasoningEl) {
      if (reasoning) {
        reasoningEl.innerHTML = this.sanitizeEscape(reasoning).replace(/\n/g, '<br>');
      } else {
        reasoningEl.innerHTML = '<p style="color: var(--on-surface-variant);">No clinical reasoning provided.</p>';
      }
    }

    // Treatment Plan
    const treatmentList = document.getElementById('treatment-list');
    if (Array.isArray(treatmentPlan) && treatmentPlan.length > 0) {
      treatmentList.innerHTML = treatmentPlan.map((t, i) => {
        const med = typeof t === 'string' ? t : t.medication || t.treatment || `Treatment ${i + 1}`;
        const app = typeof t === 'object' ? (t.application || t.instructions || '') : '';
        const dur = typeof t === 'object' ? (t.duration || '') : '';
        const edu = typeof t === 'object' ? (t.education || '') : '';
        return `<div class="card" style="margin-bottom: 1rem;">
          <div style="display: flex; align-items: flex-start; gap: 1rem;">
            <span class="treatment-number">${i + 1}</span>
            <div style="flex: 1;">
              <h4 style="margin: 0 0 0.5rem; color: var(--on-surface);">${this.sanitizeEscape(med)}</h4>
              ${app ? `<p style="margin: 0 0 0.5rem; font-size: 0.875rem; color: var(--on-surface-variant);">${this.sanitizeEscape(app)}</p>` : ''}
              ${dur ? `<p style="margin: 0 0 0.25rem; font-size: 0.75rem; color: var(--primary); font-weight: 600;">Duration: ${this.sanitizeEscape(dur)}</p>` : ''}
              ${edu ? `<p style="margin: 0; font-size: 0.75rem; color: var(--tertiary-container);">${this.sanitizeEscape(edu)}</p>` : ''}
            </div>
          </div>
        </div>`;
      }).join('');
    } else {
      treatmentList.innerHTML = '<p style="color: var(--on-surface-variant);">No treatment plan available.</p>';
    }

    // SOAP Content
    const soapContent = document.getElementById('soap-content');
    if (soapContent) {
      let s = '', o = '', a = '', p = '';
      
      // Handle soap_note as object with S, O, A, P keys
      if (typeof soapNote === 'object' && soapNote !== null) {
        s = soapNote.S || soapNote.SUBJECTIVE || soapNote.s || soapNote.subjective || '';
        o = soapNote.O || soapNote.OBJECTIVE || soapNote.o || soapNote.objective || '';
        a = soapNote.A || soapNote.ASSESSMENT || soapNote.a || soapNote.assessment || '';
        p = typeof soapNote.P === 'object' ? soapNote.P.join ? soapNote.P.join('<br>') : JSON.stringify(soapNote.P) : 
            (soapNote.P || soapNote.PLAN || soapNote.p || soapNote.plan || '');
      } else if (typeof soapNote === 'string') {
        // Try to extract S, O, A, P from pipe-separated or structured string
        const pipeMatch = soapNote.match(/S:?\s*([^|]+)/i);
        if (pipeMatch) s = pipeMatch[1].trim();
        const oMatch = soapNote.match(/O:?\s*([^|]+)/i);
        if (oMatch) o = oMatch[1].trim();
        const aMatch = soapNote.match(/A:?\s*([^|]+)/i);
        if (aMatch) a = aMatch[1].trim();
        const pMatch = soapNote.match(/P:?\s*(.+?)$/i);
        if (pMatch) p = pMatch[1].trim();
        
        // If no structured format found, show as raw text
        if (!s && !o && !a && !p) {
          s = soapNote;
        }
      }
      
      const clean = (text) => {
        if (!text) return '';
        return text.replace(/\\n/g, '<br>').replace(/\\'/g, "'").replace(/\\\\/g, '').replace(/\\"/g, '"').replace(/[{}[\]]/g, '').trim();
      };
      
      let soapHTML = '';
      if (s) soapHTML += `<div class="soap-section"><div class="soap-label S"><span>S</span>SUBJECTIVE</div><div class="soap-text">${clean(s)}</div></div>`;
      if (o) soapHTML += `<div class="soap-section"><div class="soap-label O"><span>O</span>OBJECTIVE</div><div class="soap-text">${clean(o)}</div></div>`;
      if (a) soapHTML += `<div class="soap-section"><div class="soap-label A"><span>A</span>ASSESSMENT</div><div class="soap-text">${clean(a)}</div></div>`;
      if (p) soapHTML += `<div class="soap-section"><div class="soap-label P"><span>P</span>PLAN</div><div class="soap-text">${clean(p)}</div></div>`;
      
      if (soapHTML) {
        soapContent.innerHTML = soapHTML;
      } else {
        soapContent.innerHTML = '<p style="color: var(--on-surface-variant);">No SOAP note generated.</p>';
      }
    }

    // Store for later use
    if (this.currentCasePayload) {
      this.currentCasePayload.soap_note = typeof soapNote === 'string' ? soapNote : JSON.stringify(soapNote);
    }
  }

  // --- Data & State Management ---
  clearForms() {
    document.querySelectorAll('#screen-intake input, #screen-intake select, #screen-intake textarea').forEach(el => {
       if (el.id !== 'skin_phototype') el.value = "";
    });
    document.querySelectorAll('#screen-assessment input, #screen-assessment select, #screen-assessment textarea').forEach(el => {
       if (el.id !== 'skin_phototype') el.value = "";
    });
    document.querySelectorAll('.checkbox-item input[type="checkbox"]').forEach(el => el.checked = false);
    
    this.uploadedImage = null;
    const container = document.getElementById('image-preview-container');
    const uploadArea = document.querySelector('.image-upload');
    if (container) container.classList.add('hidden');
    if (uploadArea) uploadArea.style.display = 'flex';
    const imageInput = document.getElementById('lesion-image');
    if (imageInput) imageInput.value = '';
    
    this.currentCasePayload = null;
    this.rawAIResponse = "";
  }

  async prepareSOAP() {
    this.showScreen('screen-soap');
    
    const soapContent = document.getElementById('soap-content');
    
    if (this.currentCasePayload && this.currentCasePayload.soap_note) {
      this.parseAIResponse({ soap_note: this.currentCasePayload.soap_note });
      return;
    }

    if (!this.currentCasePayload) {
      soapContent.innerHTML = "<p>No case data found to generate SOAP note.</p>";
      return;
    }

    try {
      const hostname = window.location.hostname || "127.0.0.1";
      const apiEndpoint = `http://${hostname}:8007/soap`;

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
      this.parseAIResponse({ soap_note: soapNote });

    } catch (error) {
      console.error(error);
      soapContent.innerHTML = `<p style="color:var(--error);">Error generating SOAP note: ${error.message}</p>`;
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
      const apiEndpoint = `http://${hostname}:8007/check-interactions`;

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

      // Populate recent cases list
      const recentList = document.getElementById('recent-cases-list');
      if (recentList) {
        const recentCases = cases.slice(-5).reverse();
        if (recentCases.length === 0) {
          recentList.innerHTML = `
            <div class="empty-state" style="padding: 1rem;">
              <span class="material-icons" style="font-size: 2rem; color: var(--outline-variant);">history</span>
              <p>No recent cases</p>
            </div>
          `;
        } else {
          recentList.innerHTML = recentCases.map(c => {
            const date = new Date(c.timestamp).toLocaleDateString();
            const topDx = c.diagnoses_list && c.diagnoses_list[0] ? c.diagnoses_list[0].condition || 'Pending' : 'Pending';
            const conf = c.diagnoses_list && c.diagnoses_list[0] ? c.diagnoses_list[0].probability || '' : '';
            return `
              <div class="recent-case-item" onclick="window.app.showHistory()">
                <div class="recent-case-info">
                  <div class="recent-case-icon">
                    <span class="material-icons">medical_information</span>
                  </div>
                  <div>
                    <div class="recent-case-name">${this.sanitizeEscape(topDx)}</div>
                    <div class="recent-case-meta">${this.sanitizeEscape(date)} • Age ${this.sanitizeEscape(c.patient_age?.toString() || 'N/A')}</div>
                  </div>
                </div>
                ${conf ? `<span class="confidence-badge high">${conf}</span>` : ''}
              </div>
            `;
          }).join('');
        }
      }
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
    const grid = document.getElementById('history-grid');
    const count = document.getElementById('history-count');
    grid.innerHTML = "<p style='color: var(--on-surface-variant); grid-column: 1/-1; text-align: center;'>Loading cases...</p>";
    
    try {
      const cases = await getCases();
      this.historyCache = cases;
      this.renderHistory(cases);
    } catch (error) {
       grid.innerHTML = `<p style="color: var(--error); grid-column: 1/-1; text-align: center;">Failed to load cases.</p>`;
    }
  }

  renderHistory(cases) {
    const grid = document.getElementById('history-grid');
    const count = document.getElementById('history-count');
    
    if (cases.length === 0) {
      grid.innerHTML = "<p style='color: var(--on-surface-variant); grid-column: 1/-1; text-align: center;'>No cases found.</p>";
      if (count) count.textContent = 'Showing 0 clinical cases';
      return;
    }

    grid.innerHTML = '';
    cases.forEach(c => {
      const date = new Date(c.timestamp).toLocaleDateString();
      const complaintSummary = c.complaint && c.complaint.length > 60 ? c.complaint.substring(0, 60) + "..." : (c.complaint || 'No complaint');
      const topDx = c.diagnoses_list && c.diagnoses_list[0] ? c.diagnoses_list[0].condition || 'Unknown' : 'Pending';
      
      grid.innerHTML += `
        <div class="history-card" onclick="window.app.loadCase('${c.case_id}')">
          <div class="history-card-header">
            <span class="history-date">${this.sanitizeEscape(date)}</span>
            <span class="history-status ${c.status === 'pending' ? 'pending' : ''}">${this.sanitizeEscape(c.status) || 'unknown'}</span>
          </div>
          <div class="history-complaint">${this.sanitizeEscape(complaintSummary)}</div>
          <div class="history-diagnosis">
            <span class="material-icons" style="font-size: 1rem;">medical_information</span>
            ${this.sanitizeEscape(topDx)}
          </div>
          <div class="history-meta">
            <span>Age ${this.sanitizeEscape(c.patient_age?.toString() || 'N/A')}</span>
            <span>${this.sanitizeEscape(c.geographic_region || 'Unknown')}</span>
          </div>
        </div>
      `;
    });
    
    if (count) count.textContent = `Showing ${cases.length} clinical case${cases.length !== 1 ? 's' : ''}`;
  }

  loadCase(caseId) {
    const caseData = this.historyCache.find(c => c.case_id === caseId);
    if (!caseData) {
      this.showToast('Case not found in local cache.', 'error');
      return;
    }
    
    this.currentCasePayload = caseData;
    this.showScreen('screen-assessment');
    
    document.getElementById('patient_age').value = caseData.patient_age || '';
    document.getElementById('geographic_region').value = caseData.geographic_region || '';
    document.getElementById('skin_phototype').value = caseData.skin_phototype || '';
    document.getElementById('occupation').value = caseData.occupation || '';
    document.getElementById('complaint').value = caseData.complaint || '';
    document.getElementById('lesion').value = caseData.lesion || '';
    document.getElementById('tests').value = caseData.tests || '';
    document.getElementById('lesion_history').value = caseData.lesion_history || '';
    document.getElementById('history_duration').value = caseData.history_duration || '';
    document.getElementById('change_pattern').value = caseData.change_pattern || '';
    
    if (caseData.image_data) {
      this.uploadedImage = caseData.image_data;
      const preview = document.getElementById('image-preview');
      const container = document.getElementById('image-preview-container');
      const uploadArea = document.querySelector('.image-upload');
      if (preview) preview.src = caseData.image_data;
      if (container) container.classList.remove('hidden');
      if (uploadArea) uploadArea.style.display = 'none';
    }
    
    this.showToast('Case loaded. Click "Start AI Analysis" to re-run.', 'info');
  }

  filterHistory() {
    const query = document.getElementById('history-search').value.toLowerCase();
    const filtered = this.historyCache.filter(c => {
      return (c.complaint && c.complaint.toLowerCase().includes(query)) || 
             (c.geographic_region && c.geographic_region.toLowerCase().includes(query)) ||
             (c.patient_age && c.patient_age.toString().includes(query));
    });
    this.renderHistory(filtered);
  }
  
  // --- Settings Methods ---
  async   testAIConnection() {
    const modelName = document.getElementById('settings-model-name')?.value || 'llama3.1';
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
    const savedApiUrl = localStorage.getItem('dermacare-api-url');
    if (savedApiUrl && document.getElementById('settings-api-url')) {
      document.getElementById('settings-api-url').value = savedApiUrl;
    }
    
    const savedModel = localStorage.getItem('dermacare-model');
    if (savedModel && document.getElementById('settings-model-name')) {
      document.getElementById('settings-model-name').value = savedModel;
    }
  }
  
  saveSettings() {
    const apiUrl = document.getElementById('settings-api-url')?.value;
    const modelName = document.getElementById('settings-model-name')?.value;
    
    if (apiUrl) localStorage.setItem('dermacare-api-url', apiUrl);
    if (modelName) localStorage.setItem('dermacare-model', modelName);
    
    this.showToast('Settings saved.', 'success');
    this.showScreen('screen-dashboard');
  }

}

// Initialize safely to preserve state during navigation in SPA
document.addEventListener('DOMContentLoaded', function() {
  if (!window.app) {
    window.app = new AppController();
  }
});

// Fallback initialization if DOMContentLoaded already fired
if (document.readyState === 'complete' || document.readyState === 'interactive') {
  if (!window.app) {
    setTimeout(() => {
      if (!window.app) {
        window.app = new AppController();
      }
    }, 100);
  }
}
