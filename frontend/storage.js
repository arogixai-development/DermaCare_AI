const DB_NAME = "DermaCareDB";
const STORE_NAME = "cases";
const DB_VERSION = 1;

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
                // We index timestamp so we can easily sort by newest
                store.createIndex("timestamp", "timestamp", { unique: false });
            }
        };
    });
}

// 1. Save Case (Handles pending vs complete and auto-generates UUID/Timestamp)
async function saveCase(caseData) {
    if (!db) await initDB();
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

// 2. Get Cases (Sorted by newest timestamp)
async function getCases() {
    if (!db) await initDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], "readonly");
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();
        
        request.onsuccess = () => {
            // Sort cases by timestamp mathematically descending
            const cases = request.result.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            resolve(cases);
        };
        request.onerror = () => reject(request.error);
    });
}

// 3. Delete Case
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
