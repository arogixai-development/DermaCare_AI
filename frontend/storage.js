const DB_NAME = "DermaCareDB";
const STORE_NAME = "cases";
const DB_VERSION = 2;

let db;

// Internal function to initialize DB
async function initDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        
        request.onerror = (event) => {
            console.error("IndexedDB error:", event.target.error);
            reject(event.target.error);
        };
        
        request.onsuccess = (event) => {
            db = event.target.result;
            resolve(db);
        };
        
        request.onupgradeneeded = (event) => {
            db = event.target.result;
            // Create ObjectStore with UUID keyPath
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                const store = db.createObjectStore(STORE_NAME, { keyPath: "case_id" });
                // Index timestamp for sorting
                store.createIndex("timestamp", "timestamp", { unique: false });
                // Index user_id for filtering by user
                store.createIndex("user_id", "user_id", { unique: false });
            } else if (event.oldVersion < 2) {
                // Migration: add user_id index to existing database
                const store = request.transaction.objectStore(STORE_NAME);
                if (!store.indexNames.contains("user_id")) {
                    store.createIndex("user_id", "user_id", { unique: false });
                }
            }
        };
    });
}

// Get current user ID
function getCurrentUserId() {
    if (window.auth?.user?.user_id) {
        return String(window.auth.user.user_id);
    }
    return 'anonymous';
}

// 1. Save Case (Handles pending vs complete and auto-generates UUID/Timestamp)
async function saveCase(caseData) {
    if (!db) await initDB();
    
    // Ensure user_id is set
    if (!caseData.user_id) {
        caseData.user_id = getCurrentUserId();
    }
    
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], "readwrite");
        const store = transaction.objectStore(STORE_NAME);
        
        if (!caseData.case_id) {
            caseData.case_id = crypto.randomUUID();
        }
        if (!caseData.timestamp) {
            caseData.timestamp = new Date().toISOString();
        }
        
        const request = store.put(caseData);
        
        request.onsuccess = () => resolve(caseData);
        request.onerror = () => reject(request.error);
    });
}

// 2. Get Cases for current user (Sorted by newest timestamp)
async function getCases() {
    if (!db) await initDB();
    
    const currentUserId = getCurrentUserId();
    
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], "readonly");
        const store = transaction.objectStore(STORE_NAME);
        const userIndex = store.index("user_id");
        const request = userIndex.getAll(currentUserId);
        
        request.onsuccess = () => {
            // Sort cases by timestamp descending
            const cases = request.result.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            resolve(cases);
        };
        request.onerror = () => reject(request.error);
    });
}

// 3. Get ALL cases (admin function - use with caution)
async function getAllCasesRaw() {
    if (!db) await initDB();
    
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], "readonly");
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();
        
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

// 4. Delete Case
async function deleteCase(caseId) {
    if (!db) await initDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], "readwrite");
        const store = transaction.objectStore(STORE_NAME);
        const request = store.delete(caseId);
        
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
    });
}

// 5. Get Backend URL from settings
function getBackendUrl() {
    return localStorage.getItem('dermacare-backend-url') || 'http://127.0.0.1:8000';
}

// 6. Get Auth Token
function getAuthToken() {
    return localStorage.getItem('auth-token');
}

// 7. Sync single case to backend
async function syncCaseToBackend(caseData) {
    const token = getAuthToken();
    if (!token) {
        console.log('No auth token, skipping sync');
        return { success: false, reason: 'no_token' };
    }

    try {
        const response = await fetch(`${getBackendUrl()}/api/cases`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(caseData)
        });

        if (response.ok) {
            return { success: true };
        } else {
            console.error('Sync failed:', response.status);
            return { success: false, reason: 'http_error', status: response.status };
        }
    } catch (error) {
        console.error('Sync error:', error);
        return { success: false, reason: 'network_error', error };
    }
}

// 8. Fetch all cases from backend for current user
async function fetchCasesFromBackend() {
    const token = getAuthToken();
    if (!token) {
        return { success: false, reason: 'no_token', cases: [] };
    }

    try {
        const response = await fetch(`${getBackendUrl()}/api/cases`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (response.ok) {
            const data = await response.json();
            return { success: true, cases: data.cases || [] };
        } else {
            return { success: false, reason: 'http_error', status: response.status, cases: [] };
        }
    } catch (error) {
        console.error('Fetch error:', error);
        return { success: false, reason: 'network_error', error, cases: [] };
    }
}

// 9. Sync all local cases to backend
async function syncAllCasesToBackend() {
    const token = getAuthToken();
    if (!token) {
        console.log('No auth token, skipping sync');
        return { synced: 0, failed: 0 };
    }

    const localCases = await getCases();
    let synced = 0;
    let failed = 0;

    for (const caseData of localCases) {
        const result = await syncCaseToBackend(caseData);
        if (result.success) {
            synced++;
        } else {
            failed++;
        }
    }

    return { synced, failed };
}

// 10. Merge backend cases into IndexedDB (only for current user)
async function mergeBackendCasesToLocal(backendCases) {
    if (!db) await initDB();
    
    const currentUserId = getCurrentUserId();
    let merged = 0;
    
    for (const backendCase of backendCases) {
        // Only import cases for current user
        if (backendCase.user_id !== currentUserId) {
            continue;
        }
        
        const existing = await getCaseById(backendCase.case_id);
        if (!existing) {
            await saveCase(backendCase);
            merged++;
        }
    }
    return merged;
}

// 11. Get single case by ID
async function getCaseById(caseId) {
    if (!db) await initDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], "readonly");
        const store = transaction.objectStore(STORE_NAME);
        const request = store.get(caseId);
        
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

// 12. Sync from backend (pull and merge)
async function syncFromBackend() {
    const result = await fetchCasesFromBackend();
    if (result.success && result.cases.length > 0) {
        const merged = await mergeBackendCasesToLocal(result.cases);
        console.log(`Synced ${merged} cases from backend`);
        return { success: true, merged };
    }
    return { success: false, reason: result.reason };
}

// 13. Delete case from backend
async function deleteCaseFromBackend(caseId) {
    const token = getAuthToken();
    if (!token) {
        return { success: false, reason: 'no_token' };
    }

    try {
        const response = await fetch(`${getBackendUrl()}/api/cases/${caseId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        return { success: response.ok || response.status === 404 };
    } catch (error) {
        console.error('Delete error:', error);
        return { success: false, reason: 'network_error' };
    }
}

// 14. Clear all cases for current user (local only)
async function clearUserCases() {
    if (!db) await initDB();
    
    const currentUserId = getCurrentUserId();
    const cases = await getCases();
    
    for (const c of cases) {
        await deleteCase(c.case_id);
    }
    
    return { cleared: cases.length };
}
