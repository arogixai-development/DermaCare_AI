// DermaCare AI - Main Application Controller

class AppController {
  constructor() {
    this.currentScreen = 'screen-dashboard';
    this.currentCasePayload = null;
    this.rawAIResponse = "";
    this.currentDrugAnalysis = "";
    this.uploadedImage = null;
    this.maxImageSize = 5 * 1024 * 1024;
    this.historyCache = [];
    
    this.validScreens = [
      'screen-dashboard', 'screen-intake', 'screen-assessment',
      'screen-diagnosis', 'screen-treatment', 'screen-soap',
      'screen-history', 'screen-drug-checker', 'screen-settings'
    ];
    
    this.init();
  }
  
  init() {
    this.initAuth();
    this.initButtonHandlers();
    this.updateDashboardMetrics();
    this.initNetworkMonitoring();
  }
  
  initButtonHandlers() {
    document.getElementById('create-account-btn')?.addEventListener('click', () => this.showSignupScreen());
    document.getElementById('back-to-login-btn')?.addEventListener('click', () => this.showLoginScreen());
    
    document.getElementById('monte-carlo-toggle')?.addEventListener('change', (e) => {
      const isOn = e.target.checked;
      document.getElementById('mode-label').textContent = isOn ? 'Accurate Mode' : 'Quick Mode';
      document.getElementById('mode-time').textContent = isOn ? '~45-50s' : '~15-20s';
    });
    
    this.initDataActionHandlers();
  }
  
  initDataActionHandlers() {
    document.addEventListener('click', (e) => {
      const action = e.target.closest('[data-action]')?.dataset.action;
      if (!action) return;
      
      switch(action) {
        case 'nav-dashboard': this.showScreen('screen-dashboard'); break;
        case 'nav-new': this.startNewDiagnosis(); break;
        case 'nav-history': this.showHistory(); break;
        case 'nav-drug': this.showScreen('screen-drug-checker'); break;
        case 'nav-settings': this.showScreen('screen-settings'); break;
        case 'start-diagnosis': this.startNewDiagnosis(); break;
        case 'show-history': this.showHistory(); break;
        case 'go-dashboard': this.showScreen('screen-dashboard'); break;
        case 'go-intake': this.showScreen('screen-intake'); break;
        case 'go-assessment': this.goNext('screen-assessment'); break;
        case 'go-treatment': this.goNext('screen-treatment'); break;
        case 'go-diagnosis': this.showScreen('screen-diagnosis'); break;
        case 'analyze-case': this.analyzeCase(); break;
        case 'generate-soap': this.prepareSOAP(); break;
        case 'copy-soap': this.copySOAPNote(); break;
        case 'download-soap-txt': this.downloadSOAPNote(); break;
        case 'download-soap-pdf': this.downloadSOAPPDF(); break;
        case 'finish-case': this.finishCase(); break;
        case 'check-drugs': this.checkDrugInteractions(); break;
        case 'test-ai': this.testAIConnection(); break;
        case 'save-settings': this.saveSettings(); break;
        case 'logout': this.logout(); break;
        case 'clear-cache': this.clearCache(); break;
        case 'delete-all-cases': this.confirmDeleteAllCases(); break;
        case 'save-draft': this.showScreen('screen-dashboard'); break;
        case 'retry-connection': this.retryConnection(); break;
        default: console.log('Unknown action:', action);
      }
    });
    
    document.getElementById('btn-new-diagnosis')?.addEventListener('click', () => this.startNewDiagnosis());
    document.getElementById('btn-check-connection')?.addEventListener('click', () => this.checkConnection());
    document.getElementById('btn-remove-image')?.addEventListener('click', () => this.removeImage());
    
    document.getElementById('image-upload-area')?.addEventListener('click', () => {
      document.getElementById('lesion-image')?.click();
    });
    
    document.getElementById('lesion-image')?.addEventListener('change', (e) => {
      this.handleImageUpload(e.target);
    });
    
    document.getElementById('history-search')?.addEventListener('input', () => this.filterHistory());
    
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
      });
    });
  }
  
  initAuth() {
    const loginScreen = document.getElementById('login-screen');
    const appContainer = document.getElementById('app-container');
    
    if (!window.auth?.isAuthenticated) {
      loginScreen.style.display = 'flex';
      appContainer.style.display = 'none';
      this.bindLoginForm();
      this.bindSignupForm();
    } else {
      window.auth.getCurrentUser().then(() => {
        if (window.auth.user) {
          loginScreen.style.display = 'none';
          appContainer.style.display = 'flex';
          this.updateUserProfile();
          this.syncOnLogin();
        } else {
          this.showLoginScreen();
        }
      }).catch(() => this.showLoginScreen());
    }
  }
  
  showLoginScreen() {
    const loginScreen = document.getElementById('login-screen');
    const signupScreen = document.getElementById('signup-screen');
    const appContainer = document.getElementById('app-container');
    
    if (signupScreen) signupScreen.style.display = 'none';
    if (loginScreen) {
      loginScreen.style.display = 'flex';
      loginScreen.style.visibility = 'visible';
    }
    if (appContainer) appContainer.style.display = 'none';
    
    document.getElementById('login-error')?.style && (document.getElementById('login-error').style.display = 'none');
  }
  
  showSignupScreen() {
    const loginScreen = document.getElementById('login-screen');
    const signupScreen = document.getElementById('signup-screen');
    
    if (loginScreen) loginScreen.style.display = 'none';
    if (signupScreen) {
      signupScreen.style.display = 'flex';
      signupScreen.style.visibility = 'visible';
      document.getElementById('signup-error').style.display = 'none';
      document.getElementById('signup-form').reset();
      this.bindSignupForm();
    }
  }
  
  bindLoginForm() {
    const form = document.getElementById('login-form');
    if (!form || form.dataset.bound === 'true') return;
    form.dataset.bound = 'true';
    
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const username = document.getElementById('login-email').value.trim();
      const password = document.getElementById('login-password').value;
      const errorEl = document.getElementById('login-error');
      const btn = document.getElementById('login-btn');
      
      if (!username || !password) {
        errorEl.textContent = 'Please enter email and password';
        errorEl.style.display = 'block';
        return;
      }
      
      btn.disabled = true;
      btn.textContent = 'Signing in...';
      errorEl.style.display = 'none';
      
      const result = await window.auth.login(username, password);
      
      if (result.success) {
        await window.auth.getCurrentUser();
        document.getElementById('login-screen').style.display = 'none';
        document.getElementById('app-container').style.display = 'flex';
        this.updateUserProfile();
      } else {
        errorEl.textContent = result.error || 'Login failed';
        errorEl.style.display = 'block';
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons">login</span> Sign In';
      }
    });
  }
  
  bindSignupForm() {
    const form = document.getElementById('signup-form');
    if (!form || form.dataset.bound === 'true') return;
    form.dataset.bound = 'true';
    
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const email = document.getElementById('signup-email').value.trim();
      const password = document.getElementById('signup-password').value;
      const confirm = document.getElementById('signup-confirm').value;
      const errorEl = document.getElementById('signup-error');
      const btn = document.getElementById('signup-btn');
      
      if (!email || !password) {
        errorEl.textContent = 'Please fill in all fields';
        errorEl.style.display = 'block';
        return;
      }
      
      if (password !== confirm) {
        errorEl.textContent = 'Passwords do not match';
        errorEl.style.display = 'block';
        return;
      }
      
      if (password.length < 6) {
        errorEl.textContent = 'Password must be at least 6 characters';
        errorEl.style.display = 'block';
        return;
      }
      
      btn.disabled = true;
      btn.textContent = 'Creating account...';
      errorEl.style.display = 'none';
      
      try {
        const apiBase = window.auth?.getApiBase() || 'http://127.0.0.1:8000';
        const response = await fetch(`${apiBase}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username: email, password: password, email: email })
        });
        
        if (response.ok) {
          this.showToast('Account created! Please sign in.', 'success');
          this.showLoginScreen();
          document.getElementById('login-email').value = email;
        } else {
          const data = await response.json();
          errorEl.textContent = data.detail || 'Registration failed';
          errorEl.style.display = 'block';
        }
      } catch (error) {
        errorEl.textContent = 'Connection error. Is server running?';
        errorEl.style.display = 'block';
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons">how_to_reg</span> Register';
      }
    });
  }
  
  updateUserProfile() {
    const avatar = document.getElementById('user-avatar');
    const name = document.getElementById('user-name');
    const role = document.getElementById('user-role');
    
    if (window.auth?.user) {
      const username = window.auth.user.username || 'User';
      const displayName = username.includes('@') ? username.split('@')[0] : username;
      if (avatar) avatar.textContent = displayName.substring(0, 2).toUpperCase();
      if (name) name.textContent = displayName;
      if (role) role.textContent = window.auth.user.is_admin ? 'Administrator' : 'Clinician';
    }
  }
  
  async logout() {
    await window.auth?.logout();
    this.showLoginScreen();
  }
  
  async checkConnection() {
    const apiBase = window.auth?.getApiBase() || 'http://127.0.0.1:8000';
    try {
      const ping = await fetch(`${apiBase}/health`, { signal: AbortSignal.timeout(3000) });
      if (ping.ok) {
        this.showToast('Backend connection OK', 'success');
      } else {
        this.showToast('Backend error: ' + ping.status, 'error');
      }
    } catch (err) {
      this.showToast('Backend unreachable: ' + err.message, 'error');
    }
  }
  
  async retryConnection() {
    await this.checkConnection();
  }
  
  initNetworkMonitoring() {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    
    const updateStatus = async () => {
      if (!dot || !text) return;
      
      try {
        const apiBase = window.auth?.getApiBase() || 'http://127.0.0.1:8000';
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        
        const ping = await fetch(`${apiBase}/health`, { 
          signal: controller.signal,
          cache: 'no-store'
        });
        clearTimeout(timeoutId);
        
        if (ping.ok) {
          const health = await ping.json();
          if (health.ollama_connected) {
            dot.style.background = '#22c55e';
            text.textContent = 'Online / AI Ready';
          } else {
            dot.style.background = '#f59e0b';
            text.textContent = 'Ollama Offline';
          }
        } else {
          dot.style.background = '#ef4444';
          text.textContent = 'Offline';
        }
      } catch (err) {
        dot.style.background = '#ef4444';
        text.textContent = 'Offline';
      }
    };
    
    window.addEventListener('offline', () => {
      if (dot) dot.style.background = '#ef4444';
      if (text) text.textContent = 'Offline';
    });
    
    window.addEventListener('online', updateStatus);
    
    setInterval(updateStatus, 10000);
    setTimeout(updateStatus, 2000);
  }
  
  showScreen(targetId, e) {
    if (!targetId) return;
    if (e?.preventDefault) e.preventDefault();
    
    if (!this.validScreens.includes(targetId)) return;

    const previousActive = document.querySelector('.screen.active');
    const targetEl = document.getElementById(targetId);
    
    if (targetEl) {
      targetEl.classList.add('active');
      if (previousActive && previousActive !== targetEl) {
        previousActive.classList.remove('active');
      }
    }
    
    this.currentScreen = targetId;
    if (targetId === 'screen-intake') this.clearForms();
    if (targetId === 'screen-dashboard') this.updateDashboardMetrics();
    if (targetId === 'screen-settings') this.loadSettings();
  }
  
  startNewDiagnosis(e) {
    if (e?.preventDefault) e.preventDefault();
    this.currentCasePayload = null;
    this.rawAIResponse = "";
    this.showScreen('screen-intake');
  }
  
  goBack(targetId, e) {
    if (e?.preventDefault) e.preventDefault();
    this.showScreen(targetId);
  }
  
  goNext(targetId, e) {
    if (e?.preventDefault) e.preventDefault();
    
    if (this.currentScreen === 'screen-intake') {
      if (!this.validateInputs(['patient_age', 'geographic_region'])) return;
    }
    
    this.showScreen(targetId);
  }
  
  validateInputs(fieldIds) {
    let isValid = true;
    fieldIds.forEach(id => {
      const el = document.getElementById(id);
      if (!el?.value?.trim()) {
        el?.classList.add('input-error');
        isValid = false;
      }
    });
    return isValid;
  }
  
  showToast(message, type = 'info') {
    document.querySelector('.toast')?.remove();
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.style.cssText = `
      position: fixed; bottom: 20px; right: 20px;
      background: ${type === 'success' ? '#10b981' : type === 'error' ? '#dc3545' : '#005dac'};
      color: white; padding: 12px 20px; border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 1000;
      animation: slideIn 0.3s ease; max-width: 300px;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => { toast.remove(); }, 4000);
  }
  
  handleImageUpload(input) {
    const file = input.files[0];
    if (!file) return;
    
    if (file.size > this.maxImageSize) {
      this.showToast('Image too large. Max 5MB.', 'error');
      return;
    }
    
    const reader = new FileReader();
    reader.onload = (e) => {
      this.uploadedImage = e.target.result;
      document.getElementById('image-preview').src = this.uploadedImage;
      document.getElementById('image-preview-container').classList.remove('hidden');
      document.querySelector('.image-upload').style.display = 'none';
    };
    reader.readAsDataURL(file);
  }
  
  removeImage() {
    this.uploadedImage = null;
    document.getElementById('image-preview-container').classList.add('hidden');
    document.querySelector('.image-upload').style.display = 'flex';
    document.getElementById('lesion-image').value = '';
  }
  
  sanitizeEscape(str) {
    if (!str) return "";
    return String(str).replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    })[m]);
  }
  
  async analyzeCase() {
    if (!this.validateInputs(['complaint'])) return;

    const symptoms = [];
    document.querySelectorAll('#screen-assessment .checkbox-item input:checked').forEach(cb => {
      symptoms.push(cb.value);
    });
    
    const useMonteCarlo = document.getElementById('monte-carlo-toggle')?.checked ?? true;
    
    // Get current user_id for case ownership
    let userId = 'anonymous';
    if (window.auth?.user?.user_id) {
      userId = String(window.auth.user.user_id);
    }
    
    this.currentCasePayload = {
      ...this.currentCasePayload,
      case_id: this.currentCasePayload?.case_id || 'case_' + Date.now(),
      timestamp: this.currentCasePayload?.timestamp || new Date().toISOString(),
      user_id: userId,
      patient_age: parseInt(document.getElementById('patient_age').value),
      geographic_region: document.getElementById('geographic_region').value,
      skin_phototype: document.getElementById('skin_phototype').value || "UNKNOWN",
      complaint: document.getElementById('complaint').value,
      lesion: document.getElementById('lesion').value || "None provided",
      symptoms: symptoms.join(', ') || "None stated",
      tests: document.getElementById('tests').value || "None",
      has_image: !!this.uploadedImage,
      image_data: this.uploadedImage || null,
      monte_carlo: useMonteCarlo
    };

    const btn = document.getElementById('analyze-btn');
    const loading = document.getElementById('loading-state');
    
    btn.disabled = true;
    loading.classList.remove('hidden');

    try {
      const apiBase = window.auth?.getApiBase() || 'http://127.0.0.1:8000';
      const res = await window.auth.authenticatedFetch(`${apiBase}/diagnosis`, {
        method: "POST",
        body: this.currentCasePayload
      });
      
      if (!res.ok) throw new Error('Server error');
      
      const data = await res.json();
      this.currentCasePayload.diagnoses_list = data.differential_diagnosis || [];
      this.currentCasePayload.reasoning = data.clinical_reasoning || "";
      this.currentCasePayload.soap_note = data.soap_note || "";
      this.currentCasePayload.treatment_list = data.treatment_plan || [];
      this.currentCasePayload.lesion_analysis = data.lesion_analysis || [];
      this.currentCasePayload.recommended_tests = data.recommended_tests || [];
      this.currentCasePayload.status = "completed";
      
      this.parseAIResponse(data);
      this.showScreen('screen-diagnosis');
      await saveCase(this.currentCasePayload);

    } catch (error) {
      this.showToast('Analysis failed: ' + error.message, 'error');
      this.currentCasePayload.status = "pending";
    } finally {
      btn.disabled = false;
      loading.classList.add('hidden');
    }
  }
  
  parseAIResponse(data) {
    // Differential Diagnoses
    const diffDx = data.differential_diagnosis || data.diagnoses || [];
    const diagList = document.getElementById('diagnosis-list');
    if (diffDx.length > 0) {
      diagList.innerHTML = diffDx.map((d, i) => `
        <div class="diagnosis-item">
          <div class="diagnosis-header">
            <span class="diagnosis-name">${i === 0 ? '<span class="material-icons" style="color: var(--primary);">star</span> ' : ''}${this.sanitizeEscape(d.condition || 'Unknown')}</span>
            <span class="diagnosis-probability" style="background: #22c55e;">${d.probability || 'N/A'}</span>
          </div>
          ${d.supporting_features ? `<div class="diagnosis-features">${Array.isArray(d.supporting_features) ? d.supporting_features.join(' | ') : d.supporting_features}</div>` : ''}
        </div>
      `).join('');
    } else {
      diagList.innerHTML = '<p style="color: var(--on-surface-variant);">No differential diagnoses generated.</p>';
    }
    
    // Lesion Analysis
    const lesionList = document.getElementById('lesion-analysis-list');
    const lesionAnalysis = data.lesion_analysis || [];
    if (lesionAnalysis.length > 0 && lesionAnalysis[0]) {
      const la = lesionAnalysis[0];
      let lesionHTML = '';
      if (la.morphology) lesionHTML += `<div style="margin-bottom: 0.75rem;"><strong>Morphology:</strong><br>${this.sanitizeEscape(la.morphology)}</div>`;
      if (la.distribution) lesionHTML += `<div style="margin-bottom: 0.75rem;"><strong>Distribution:</strong><br>${this.sanitizeEscape(la.distribution)}</div>`;
      if (la.ABCDE_assessment) lesionHTML += `<div style="margin-bottom: 0.75rem;"><strong>ABCDE Assessment:</strong><br>${this.sanitizeEscape(la.ABCDE_assessment)}</div>`;
      if (la.color_patterns) {
        const patterns = Array.isArray(la.color_patterns) ? la.color_patterns : [la.color_patterns];
        lesionHTML += `<div style="margin-bottom: 0.75rem;"><strong>Color Patterns:</strong><br>${this.sanitizeEscape(patterns.join(', '))}</div>`;
      }
      if (la.dermoscopy_findings) lesionHTML += `<div><strong>Dermoscopy:</strong><br>${this.sanitizeEscape(la.dermoscopy_findings)}</div>`;
      lesionList.innerHTML = lesionHTML || '<p>Analysis available</p>';
    } else {
      lesionList.innerHTML = '<p style="color: var(--on-surface-variant);">No detailed lesion analysis available.</p>';
    }
    
    // Recommended Tests
    const testsList = document.getElementById('recommended-tests-list');
    const tests = data.recommended_tests || data.tests_list || [];
    if (tests.length > 0) {
      testsList.innerHTML = tests.map((t, i) => {
        const testName = typeof t === 'string' ? t : (t.test || t.name || `Test ${i + 1}`);
        return `<div class="analysis-item" style="margin-bottom: 0.5rem;">
          <span class="material-icons" style="font-size: 1rem; color: var(--secondary);">science</span>
          <span>${this.sanitizeEscape(testName)}</span>
        </div>`;
      }).join('');
    } else {
      testsList.innerHTML = '<p style="color: var(--on-surface-variant);">No specific tests recommended.</p>';
    }
    
    // Clinical Reasoning
    const reasoningEl = document.getElementById('clinical-reasoning');
    if (reasoningEl) {
      const reasoningElInner = reasoningEl.querySelector('.empty-state') || reasoningEl;
      if (data.clinical_reasoning) {
        reasoningEl.innerHTML = `<div style="font-size: 0.875rem; line-height: 1.6;">${this.sanitizeEscape(data.clinical_reasoning).replace(/\n/g, '<br>')}</div>`;
      } else {
        reasoningEl.innerHTML = '<p style="color: var(--on-surface-variant);">No clinical reasoning available.</p>';
      }
    }
    
    // Treatment Plan
    const treatmentList = document.getElementById('treatment-list');
    const treatments = data.treatment_plan || [];
    if (treatments.length > 0) {
      treatmentList.innerHTML = treatments.map((t, i) => {
        const med = typeof t === 'string' ? t : (t.medication || t.treatment || `Treatment ${i + 1}`);
        const instructions = typeof t === 'object' ? (t.application || t.instructions || '') : '';
        return `<div class="card" style="margin-bottom: 1rem;">
          <div style="display: flex; align-items: flex-start; gap: 1rem;">
            <span class="treatment-number">${i + 1}</span>
            <div style="flex: 1;">
              <h4 style="margin: 0 0 0.5rem; color: var(--on-surface);">${this.sanitizeEscape(med)}</h4>
              ${instructions ? `<p style="margin: 0; font-size: 0.8rem; color: var(--on-surface-variant);">${this.sanitizeEscape(instructions)}</p>` : ''}
            </div>
          </div>
        </div>`;
      }).join('');
    } else {
      treatmentList.innerHTML = '<p style="color: var(--on-surface-variant);">No treatment plan available.</p>';
    }
  }
  
  clearForms() {
    document.querySelectorAll('#screen-intake input, #screen-intake select, #screen-intake textarea').forEach(el => {
      if (el.id !== 'skin_phototype') el.value = "";
    });
    document.querySelectorAll('#screen-assessment input, #screen-assessment select, #screen-assessment textarea').forEach(el => {
      if (el.id !== 'skin_phototype') el.value = "";
    });
    document.querySelectorAll('.checkbox-item input').forEach(el => el.checked = false);
    this.uploadedImage = null;
  }
  
  async prepareSOAP() {
    this.showScreen('screen-soap');
    const soapContent = document.getElementById('soap-content');
    
    let soapNote = null;
    
    // Check if already in payload
    if (this.currentCasePayload?.soap_note) {
      soapNote = this.currentCasePayload.soap_note;
    }
    
    // If no SOAP note, try to generate it
    if (!soapNote && this.currentCasePayload) {
      try {
        const apiBase = window.auth?.getApiBase() || 'http://127.0.0.1:8000';
        const res = await window.auth.authenticatedFetch(`${apiBase}/soap`, {
          method: 'POST',
          body: {
            case_id: this.currentCasePayload?.case_id || `case_${Date.now()}`,
            complaint: this.currentCasePayload?.complaint || '',
            lesion: this.currentCasePayload?.lesion || '',
            symptoms: this.currentCasePayload?.symptoms || '',
            region: this.currentCasePayload?.geographic_region || '',
            patient_age: this.currentCasePayload?.patient_age || 30,
            diagnoses: this.currentCasePayload?.diagnoses_list || [],
            treatment: this.currentCasePayload?.treatment_list || [],
            tests: []
          }
        });
        
        if (res.ok) {
          const data = await res.json();
          soapNote = data.soap_note;
          if (this.currentCasePayload) {
            this.currentCasePayload.soap_note = soapNote;
          }
        }
      } catch (e) {
        console.error('SOAP generation failed:', e);
      }
    }
    
    // Format and display SOAP
    if (soapNote) {
      const formatSOAP = (s) => {
        let html = '';
        
        // Handle different SOAP formats
        const subjective = s?.S || s?.SUBJECTIVE || s?.s || s?.subjective || '';
        const objective = s?.O || s?.OBJECTIVE || s?.o || s?.objective || '';
        const assessment = s?.A || s?.ASSESSMENT || s?.a || s?.assessment || '';
        const plan = s?.P || s?.PLAN || s?.p || s?.plan || '';
        
        if (subjective || objective || assessment || plan) {
          if (subjective) html += `<div class="soap-section"><div class="soap-label S"><span>S</span>SUBJECTIVE</div><div class="soap-text">${this.sanitizeEscape(subjective).replace(/\n/g, '<br>')}</div></div>`;
          if (objective) html += `<div class="soap-section"><div class="soap-label O"><span>O</span>OBJECTIVE</div><div class="soap-text">${this.sanitizeEscape(objective).replace(/\n/g, '<br>')}</div></div>`;
          if (assessment) html += `<div class="soap-section"><div class="soap-label A"><span>A</span>ASSESSMENT</div><div class="soap-text">${this.sanitizeEscape(assessment).replace(/\n/g, '<br>')}</div></div>`;
          if (plan) html += `<div class="soap-section"><div class="soap-label P"><span>P</span>PLAN</div><div class="soap-text">${this.sanitizeEscape(plan).replace(/\n/g, '<br>')}</div></div>`;
        } else if (typeof s === 'string') {
          // Plain text format
          html = `<pre style="white-space: pre-wrap; font-size: 0.875rem; line-height: 1.6;">${this.sanitizeEscape(s)}</pre>`;
        } else {
          html = '<p>Unable to parse SOAP note format.</p>';
        }
        
        return html;
      };
      
      soapContent.innerHTML = formatSOAP(soapNote);
    } else {
      soapContent.innerHTML = '<div class="empty-state"><span class="material-icons" style="font-size: 2.5rem; color: var(--outline-variant);">description</span><p>No SOAP note available.<br>Please run AI diagnosis first.</p></div>';
    }
  }
  
  async finishCase() {
    if (this.currentCasePayload) {
      await saveCase(this.currentCasePayload);
      const syncResult = await syncCaseToBackend(this.currentCasePayload);
      if (syncResult.success) {
        console.log('Case synced to backend');
      } else {
        console.log('Case saved locally, sync pending');
      }
    }
    this.showScreen('screen-dashboard');
  }
  
  copySOAPNote() {
    const soapContent = document.getElementById('soap-content');
    if (!soapContent) return;
    
    const text = soapContent.innerText || soapContent.textContent;
    if (!text || text.includes('No SOAP note available')) {
      this.showToast('No SOAP note to copy', 'warning');
      return;
    }
    
    navigator.clipboard.writeText(text).then(() => {
      this.showToast('SOAP note copied to clipboard!', 'success');
    }).catch(() => {
      this.showToast('Failed to copy', 'error');
    });
  }
  
  downloadSOAPNote() {
    const soapContent = document.getElementById('soap-content');
    if (!soapContent) return;
    
    const text = soapContent.innerText || soapContent.textContent;
    if (!text || text.includes('No SOAP note available')) {
      this.showToast('No SOAP note to download', 'warning');
      return;
    }
    
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `SOAP_Note_${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    this.showToast('SOAP note downloaded!', 'success');
  }
  
  downloadSOAPPDF() {
    if (typeof window.jspdf === 'undefined') {
      this.showToast('PDF library not loaded', 'error');
      return;
    }
    
    const soapContent = document.getElementById('soap-content');
    if (!soapContent) return;
    
    const text = soapContent.innerText || soapContent.textContent;
    if (!text || text.includes('No SOAP note available')) {
      this.showToast('No SOAP note to export', 'warning');
      return;
    }
    
    try {
      const { jsPDF } = window.jspdf;
      const doc = new jsPDF();
      let y = 20;
      
      doc.setFont("helvetica", "bold");
      doc.setFontSize(18);
      doc.setTextColor(0, 93, 172);
      doc.text("DermaCare AI - SOAP Note", 15, y);
      y += 10;
      
      doc.setFontSize(10);
      doc.setTextColor(100, 100, 100);
      doc.setFont("helvetica", "normal");
      doc.text(`Generated: ${new Date().toLocaleString()}`, 15, y);
      y += 15;
      
      doc.setFontSize(12);
      doc.setTextColor(0, 0, 0);
      doc.setFont("helvetica", "bold");
      doc.text("SOAP NOTE", 15, y);
      y += 8;
      
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      
      const lines = doc.splitTextToSize(text, 180);
      lines.forEach(line => {
        if (y > 280) { doc.addPage(); y = 20; }
        doc.text(line, 15, y);
        y += 6;
      });
      
      doc.save(`SOAP_Note_${new Date().toISOString().slice(0,10)}.pdf`);
      this.showToast('PDF downloaded!', 'success');
    } catch (e) {
      this.showToast('PDF generation failed', 'error');
    }
  }
  
  async showHistory() {
    this.showScreen('screen-history');
    
    // First, try to sync from backend to get latest cases
    await syncFromBackend();
    
    // Then load from local IndexedDB
    const cases = await getCases();
    this.historyCache = cases;
    
    const grid = document.getElementById('history-grid');
    if (cases.length === 0) {
      grid.innerHTML = '<p style="text-align: center; color: var(--on-surface-variant);">No cases found.</p>';
      return;
    }
    
    grid.innerHTML = cases.map(c => `
      <div class="history-card" onclick="window.app.loadCase('${c.case_id}')">
        <div class="history-card-header">
          <span class="history-date">${new Date(c.timestamp).toLocaleDateString()}</span>
          <span class="history-status ${c.status === 'pending' ? 'pending' : ''}">${c.status || 'unknown'}</span>
        </div>
        <div class="history-complaint">${this.sanitizeEscape(c.complaint?.substring(0, 60) || '')}</div>
      </div>
    `).join('');
  }
  
  loadCase(caseId) {
    const caseData = this.historyCache.find(c => c.case_id === caseId);
    if (!caseData) return;
    
    this.currentCasePayload = caseData;
    this.showScreen('screen-assessment');
    
    document.getElementById('patient_age').value = caseData.patient_age || '';
    document.getElementById('geographic_region').value = caseData.geographic_region || '';
    document.getElementById('complaint').value = caseData.complaint || '';
    document.getElementById('lesion').value = caseData.lesion || '';
  }
  
  async updateDashboardMetrics() {
    const cases = await getCases();
    document.getElementById('metric-total-cases').innerText = cases.length;
    document.getElementById('metric-completed-cases').innerText = cases.filter(c => c.status === 'completed').length;
    document.getElementById('metric-pending-cases').innerText = cases.filter(c => c.status === 'pending').length;
  }
  
  async syncOnLogin() {
    try {
      const result = await syncFromBackend();
      if (result.success && result.merged > 0) {
        this.showToast(`Synced ${result.merged} cases from server`, 'success');
        await this.updateDashboardMetrics();
      }
    } catch (e) {
      console.log('Sync on login failed, will use local data');
    }
  }
  
  loadSettings() {
    const savedApiUrl = localStorage.getItem('dermacare-api-url');
    const savedModel = localStorage.getItem('dermacare-model');
    const savedBackendUrl = localStorage.getItem('dermacare-backend-url');
    if (savedApiUrl) document.getElementById('settings-api-url').value = savedApiUrl;
    if (savedModel) document.getElementById('settings-model-name').value = savedModel;
    if (savedBackendUrl) document.getElementById('settings-backend-url').value = savedBackendUrl;
  }
  
  saveSettings() {
    const apiUrl = document.getElementById('settings-api-url')?.value || '';
    const model = document.getElementById('settings-model-name')?.value || '';
    const backendUrl = document.getElementById('settings-backend-url')?.value || '';
    
    localStorage.setItem('dermacare-api-url', apiUrl);
    localStorage.setItem('dermacare-model', model);
    localStorage.setItem('dermacare-backend-url', backendUrl);
    
    if (window.auth) {
      window.auth.setApiBase(backendUrl || 'http://127.0.0.1:8000');
    }
    
    this.showToast('Settings saved. API URL updated.', 'success');
    this.showScreen('screen-dashboard');
  }
  
  async testConnection() {
    const backendUrl = document.getElementById('settings-backend-url')?.value || 'http://127.0.0.1:8000';
    const apiUrl = document.getElementById('settings-api-url')?.value || 'http://localhost:11434';
    
    this.showToast('Testing connections...', 'info');
    
    try {
      const backendRes = await fetch(`${backendUrl}/health`, { signal: AbortSignal.timeout(5000) });
      if (backendRes.ok) {
        this.showToast('Backend connection OK', 'success');
      } else {
        this.showToast('Backend error: ' + backendRes.status, 'error');
      }
    } catch (e) {
      this.showToast('Backend unreachable: ' + e.message, 'error');
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  if (!window.app) window.app = new AppController();
});
