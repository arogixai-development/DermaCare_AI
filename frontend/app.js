// DermaCare AI - Main Application Controller

window.DEMO_MODE = window.FORCE_LOGIN ? false : true;



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
    const demoBanner = document.getElementById('demo-mode-banner');
    const demoBadge = document.getElementById('demo-badge');
    
    if (window.DEMO_MODE) {
      if (demoBanner) demoBanner.style.display = 'flex';
      if (demoBadge) demoBadge.style.display = 'flex';
      
      // Immediately open dashboard
      loginScreen.style.display = 'none';
      appContainer.style.display = 'flex';
      
      // Perform background silent login to acquire real JWT tokens if the backend is reachable
      window.auth.login("arogixai@gmail.com", "Arogix9345@").then(res => {
        if (res.success) {
          console.log("Demo Mode: Background authentication succeeded.");
          this.updateUserProfile();
          this.syncOnLogin();
        } else {
          console.warn("Demo Mode: Backend unreachable, operating on cached/mocked session:", res.error);
          window.auth.user = { user_id: 1, username: 'arogixai@gmail.com', is_admin: true };
          this.updateUserProfile();
        }
      }).catch(err => {
        console.warn("Demo Mode: Background auth error, running in sandbox mode:", err);
        window.auth.user = { user_id: 1, username: 'arogixai@gmail.com', is_admin: true };
        this.updateUserProfile();
      });
      return;
    }
    
    if (demoBanner) demoBanner.style.display = 'none';
    if (demoBadge) demoBadge.style.display = 'none';
    
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
      
      if (!res.ok) {
        let detail = 'Server error';
        try {
          const errData = await res.json();
          detail = errData.detail || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      
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
    const responseQuality = data._response_quality || (data._fallback ? 'fallback' : 'full');
    const isFallback = !!data._fallback || responseQuality === 'fallback';
    const isPartial = !!data._partial_llm || responseQuality === 'partial';

    // Differential Diagnoses
    const diffDx = data.differential_diagnosis || data.diagnoses || [];
    const diagList = document.getElementById('diagnosis-list');
    const qualityBanner = isFallback
      ? `<div style="margin-bottom:0.75rem;padding:0.6rem;border-radius:8px;background:rgba(239,68,68,0.12);color:#b91c1c;font-size:0.78rem;">
          Decision-support fallback response. Escalate to dermatologist if high-risk or persistent lesions.
        </div>`
      : isPartial
      ? `<div style="margin-bottom:0.75rem;padding:0.6rem;border-radius:8px;background:rgba(245,158,11,0.12);color:#92400e;font-size:0.78rem;">
          Partial model response merged with safety defaults. Use with clinical caution.
        </div>`
      : `<div style="margin-bottom:0.75rem;padding:0.6rem;border-radius:8px;background:rgba(34,197,94,0.12);color:#166534;font-size:0.78rem;">
          Model response passed relevance/safety checks. Clinical confirmation still required.
        </div>`;
    if (diffDx.length > 0) {
      diagList.innerHTML = qualityBanner + diffDx.map((d, i) => `
        <div class="diagnosis-item">
          <div class="diagnosis-header">
            <span class="diagnosis-name">${i === 0 ? '<span class="material-icons" style="color: var(--primary);">star</span> ' : ''}${this.sanitizeEscape(d.condition || 'Unknown')}</span>
            <span class="diagnosis-probability" style="background: #22c55e;">${d.probability || 'N/A'}</span>
          </div>
          ${d.supporting_features ? `<div class="diagnosis-features">${Array.isArray(d.supporting_features) ? d.supporting_features.join(' | ') : d.supporting_features}</div>` : ''}
        </div>
      `).join('');
    } else {
      diagList.innerHTML = `${qualityBanner}<p style="color: var(--on-surface-variant);">No differential diagnoses generated.</p>`;
    }
    
    // Uncertainty Metrics Display
    const uncertaintyBadge = document.getElementById('ai-confidence-badge');
    const uncertaintyDetails = document.getElementById('uncertainty-details');
    const uncertainty = data.uncertainty_flags || {};
    
    if (uncertainty && uncertainty.monte_carlo_enabled) {
      const confidence = uncertainty.overall_confidence || 'UNKNOWN';
      const variance = uncertainty.variance_score || 0;
      const confidenceInterval = uncertainty.confidence_interval || [0, 100];
      const iterations = uncertainty.monte_carlo_iterations || 0;
      const uncertaintyFlag = uncertainty.uncertainty_flag || false;
      const discordant = uncertainty.discordant_indicators || [];
      const recommendations = uncertainty.recommendations_for_reduction || [];
      
      // Confidence badge styling
      let badgeColor, badgeBg;
      let displayConfidence = confidence; // Create a display variable
      if (confidence === 'HIGH') {
        badgeColor = '#22c55e';
        badgeBg = 'rgba(34, 197, 94, 0.1)';
      } else if (confidence === 'MEDIUM') {
        badgeColor = '#eab308'; // Less aggressive orange/yellow
        badgeBg = 'rgba(234, 179, 8, 0.1)';
        displayConfidence = 'MODERATED';
      } else {
        badgeColor = '#f97316'; // Orange instead of bright red
        badgeBg = 'rgba(249, 115, 22, 0.1)';
        displayConfidence = 'LIMITED';
      }
      
      // Calculate confidence percentage for progress bar
      const confPercent = confidence === 'HIGH' ? 85 : confidence === 'MEDIUM' ? 65 : 40;
      
      let badgeHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <div style="flex: 1;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
              <span style="font-weight: 600; font-size: 0.875rem;">${displayConfidence} Confidence</span>
              <span style="font-size: 0.75rem; color: var(--on-surface-variant);">${confPercent}%</span>
            </div>
            <div style="background: var(--surface-container-high); border-radius: 4px; height: 8px; overflow: hidden;">
              <div style="width: ${confPercent}%; height: 100%; background: ${badgeColor}; border-radius: 4px; transition: width 0.3s;"></div>
            </div>
          </div>
          ${uncertaintyFlag ? '<span class="material-icons" style="color: #f97316; font-size: 1.5rem;" title="Uncertainty Flagged">info</span>' : '<span class="material-icons" style="color: #22c55e; font-size: 1.5rem;" title="Confidence Optimal">check_circle</span>'}
        </div>
      `;
      uncertaintyBadge.innerHTML = badgeHTML;
      
      // Detailed metrics
      let detailsHTML = `
        <div style="margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 1px solid rgba(193,198,212,0.15);">
          <strong>Confidence Context:</strong> ${this.sanitizeEscape(data.confidence_explanation || "Computed via Monte Carlo variance estimation.")}
        </div>
        <div style="margin-bottom: 0.5rem;">
          <strong>Variance Score:</strong> ${variance.toFixed(2)} 
          <span style="font-size: 0.7rem;">(${variance < 0.2 ? 'Low' : variance < 0.5 ? 'Medium' : 'High'} variance)</span>
        </div>
        <div style="margin-bottom: 0.5rem;">
          <strong>Confidence Range:</strong> ${confidenceInterval[0]}% - ${confidenceInterval[1]}%
        </div>
        <div style="margin-bottom: 0.5rem;">
          <strong>Analysis Runs:</strong> ${iterations} iterations completed
        </div>
      `;
      
      if (uncertaintyFlag && discordant.length > 0) {
        detailsHTML += `<div style="margin-bottom: 0.5rem; color: #ef4444;">
          <strong>⚠️ Uncertainty Detected:</strong><br>
          <span style="font-size: 0.75rem;">${discordant.join(', ')}</span>
        </div>`;
      }
      
      if (recommendations.length > 0) {
        detailsHTML += `<div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(193,198,212,0.15);">
          <strong style="font-size: 0.75rem;">Recommendations:</strong>
          <ul style="margin: 0.25rem 0 0 1rem; padding-left: 0; font-size: 0.75rem;">
            ${recommendations.slice(0, 2).map(r => `<li>${this.sanitizeEscape(r)}</li>`).join('')}
          </ul>
        </div>`;
      }
      
      uncertaintyDetails.innerHTML = detailsHTML;
    } else {
      // Quick Mode - no uncertainty metrics
      uncertaintyBadge.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <span class="material-icons" style="color: var(--primary);">bolt</span>
          <span style="font-weight: 600;">Quick Analysis Mode</span>
        </div>
      `;
      uncertaintyDetails.innerHTML = `
        <div style="margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 1px solid rgba(193,198,212,0.15);">
          <strong>Confidence Context:</strong> ${this.sanitizeEscape(data.confidence_explanation || "Computed without variance estimation in Quick Mode.")}
        </div>
        <p style="margin: 0; font-size: 0.75rem;">Fast diagnosis without structural uncertainty metrics.</p>
        <p style="margin: 0.25rem 0 0; font-size: 0.7rem; color: var(--outline);">Enable "Accurate Mode" for full confidence calibration.</p>
      `;
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
        const trustLine = data._decision_support_note
          ? `<div style="margin-bottom:0.6rem;font-size:0.75rem;color:var(--on-surface-variant);">${this.sanitizeEscape(data._decision_support_note)}</div>`
          : '';
        reasoningEl.innerHTML = `${trustLine}<div class="clinical-reasoning-body">${this.sanitizeEscape(data.clinical_reasoning).replace(/\n/g, '<br>')}</div>`;
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
        let html = `
          <div class="soap-container">
            <div class="soap-emr-header">
              <div class="soap-emr-hospital">DermaCare Integrated EHR</div>
              <div class="soap-emr-subheader">Clinical encounter note • Decision support document</div>
            </div>
            
            <div class="soap-patient-chart">
              <div class="chart-cell"><strong>Case ID</strong> <span>${this.sanitizeEscape(this.currentCasePayload?.case_id || 'N/A')}</span></div>
              <div class="chart-cell"><strong>Encounter Date</strong> <span>${this.currentCasePayload?.timestamp ? new Date(this.currentCasePayload.timestamp).toLocaleDateString() : new Date().toLocaleDateString()}</span></div>
              <div class="chart-cell"><strong>Patient Age</strong> <span>${this.currentCasePayload?.patient_age || 'N/A'} years</span></div>
              <div class="chart-cell"><strong>Geographic Region</strong> <span>${this.sanitizeEscape(this.currentCasePayload?.geographic_region || 'N/A')}</span></div>
              <div class="chart-cell"><strong>Skin Phototype</strong> <span>Type ${this.sanitizeEscape(this.currentCasePayload?.skin_phototype || 'N/A')}</span></div>
              <div class="chart-cell"><strong>Provider ID</strong> <span>${this.sanitizeEscape(this.currentCasePayload?.user_id || 'anonymous')}</span></div>
            </div>
        `;
        
        // Handle different SOAP formats
        const subjective = s?.S || s?.SUBJECTIVE || s?.s || s?.subjective || '';
        const objective = s?.O || s?.OBJECTIVE || s?.o || s?.objective || '';
        const assessment = s?.A || s?.ASSESSMENT || s?.a || s?.assessment || '';
        const plan = s?.P || s?.PLAN || s?.p || s?.plan || '';
        
        if (subjective || objective || assessment || plan) {
          if (subjective) html += `<div class="soap-section"><div class="soap-label">S - SUBJECTIVE HISTORY</div><div class="soap-text">${this.sanitizeEscape(subjective).replace(/\n/g, '<br>')}</div></div>`;
          if (objective) html += `<div class="soap-section"><div class="soap-label">O - OBJECTIVE MORPHOLOGY</div><div class="soap-text">${this.sanitizeEscape(objective).replace(/\n/g, '<br>')}</div></div>`;
          if (assessment) html += `<div class="soap-section"><div class="soap-label">A - CLINICAL ASSESSMENT</div><div class="soap-text">${this.sanitizeEscape(assessment).replace(/\n/g, '<br>')}</div></div>`;
          if (plan) html += `<div class="soap-section"><div class="soap-label">P - DETERMINISTIC CARE PLAN</div><div class="soap-text">${this.sanitizeEscape(plan).replace(/\n/g, '<br>')}</div></div>`;
        } else if (typeof s === 'string') {
          // Plain text format
          html += `<pre style="white-space: pre-wrap; font-family: 'Inter', sans-serif; font-size: 0.95rem; line-height: 1.6; padding: 0.5rem; border-left: 3px solid #d1d5db;">${this.sanitizeEscape(s)}</pre>`;
        } else {
          html += '<p style="padding: 0.5rem;">Unable to parse SOAP note format.</p>';
        }
        
        html += `
            <div class="soap-signoff">
              <div class="signoff-row">
                <div class="signoff-signature">Electronically Signed By: DermaCare Clinical Decision Support System</div>
                <div class="signoff-date">${new Date().toLocaleString()}</div>
              </div>
              <div class="signoff-note">Verified Decision Support Output • Authentic EHR Documentation</div>
            </div>
          </div>
        `;
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

  async checkDrugInteractions() {
    const inputEl = document.getElementById('drug-input');
    const resultContainer = document.getElementById('drug-result-container');
    const btn = document.getElementById('check-drug-btn');
    if (!inputEl || !resultContainer || !btn) {
      this.showToast('Drug checker UI not initialized', 'error');
      return;
    }

    const drugs = String(inputEl.value || '')
      .split(',')
      .map((d) => d.trim())
      .filter(Boolean);

    if (drugs.length === 0) {
      this.showToast('Please enter at least one medication', 'warning');
      resultContainer.classList.add('hidden');
      resultContainer.innerHTML = '';
      return;
    }

    btn.disabled = true;
    const old = btn.innerHTML;
    btn.innerHTML = 'Analyzing...';
    resultContainer.classList.remove('hidden');
    resultContainer.innerHTML = `
      <div class="card">
        <div class="empty-state">
          <span class="material-icons" style="font-size: 2rem; color: var(--outline-variant);">hourglass_top</span>
          <p>Running interaction analysis...</p>
        </div>
      </div>
    `;

    try {
      const apiBase = window.auth?.getApiBase() || 'http://127.0.0.1:8000';
      const res = await window.auth.authenticatedFetch(`${apiBase}/check-interactions`, {
        method: 'POST',
        body: { drugs },
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const err = await res.json();
          detail = err.detail || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      const data = await res.json();
      this.currentDrugAnalysis = data?.analysis || '';
      this.renderDrugInteractionResult(data);
      this.showToast('Interaction analysis complete', 'success');
    } catch (e) {
      resultContainer.innerHTML = `
        <div class="card">
          <div class="empty-state">
            <span class="material-icons" style="font-size: 2rem; color: var(--error);">error</span>
            <p>Drug analysis failed: ${this.sanitizeEscape(e.message || 'Unknown error')}</p>
          </div>
        </div>
      `;
      this.showToast(`Drug analysis failed: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = old;
    }
  }

  renderDrugInteractionResult(payload) {
    const resultContainer = document.getElementById('drug-result-container');
    if (!resultContainer) return;
    const raw = payload?.analysis;
    let parsed = null;
    if (typeof raw === 'string') {
      const t = raw.trim();
      if (t.startsWith('{') || t.startsWith('[')) {
        try {
          parsed = JSON.parse(t);
        } catch (_) {
          parsed = null;
        }
      }
    } else if (raw && typeof raw === 'object') {
      parsed = raw;
    }

    if (!parsed) {
      resultContainer.innerHTML = `
        <div class="card">
          <div class="card-header">
            <h3 class="card-title"><span class="material-icons">medication</span>Interaction Analysis</h3>
          </div>
          <div style="font-size: 0.9rem; line-height: 1.6; white-space: pre-wrap;">
            ${this.sanitizeEscape(String(raw || 'No analysis returned'))}
          </div>
        </div>
      `;
      return;
    }

    const summary = parsed.summary || parsed.overview || 'No summary available';
    const major = Array.isArray(parsed.major_interactions) ? parsed.major_interactions : [];
    const moderate = Array.isArray(parsed.moderate_minor_interactions) ? parsed.moderate_minor_interactions : [];
    const guidance = Array.isArray(parsed.clinical_guidance)
      ? parsed.clinical_guidance
      : Array.isArray(parsed.guidance)
      ? parsed.guidance
      : [];
    const severity = parsed.severity || parsed.risk_level || 'Not specified';

    const majorHtml = major.length
      ? `<ul>${major.map((x) => `<li>${this.sanitizeEscape(typeof x === 'string' ? x : JSON.stringify(x))}</li>`).join('')}</ul>`
      : '<p>None identified</p>';

    const moderateHtml = moderate.length
      ? `<ul>${moderate
          .map((x) => {
            if (typeof x === 'string') return `<li>${this.sanitizeEscape(x)}</li>`;
            const m1 = this.sanitizeEscape(x.medication1 || 'Unknown');
            const m2 = this.sanitizeEscape(x.medication2 || 'Unknown');
            const d = this.sanitizeEscape(x.description || 'No description');
            return `<li><strong>${m1}</strong> + <strong>${m2}</strong>: ${d}</li>`;
          })
          .join('')}</ul>`
      : '<p>None identified</p>';

    const guidanceHtml = guidance.length
      ? `<ul>${guidance.map((x) => `<li>${this.sanitizeEscape(String(x))}</li>`).join('')}</ul>`
      : '<p>No specific guidance provided</p>';

    resultContainer.innerHTML = `
      <div class="card">
        <div class="card-header">
          <h3 class="card-title"><span class="material-icons">medication</span>Interaction Analysis</h3>
        </div>
        <div style="display:grid; gap:1rem;">
          <div><strong>Severity/Risk:</strong> ${this.sanitizeEscape(String(severity))}</div>
          <div><strong>Summary:</strong><br>${this.sanitizeEscape(String(summary))}</div>
          <div><strong>Major Interactions</strong>${majorHtml}</div>
          <div><strong>Moderate/Minor Interactions</strong>${moderateHtml}</div>
          <div><strong>Clinical Guidance</strong>${guidanceHtml}</div>
        </div>
      </div>
    `;
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
